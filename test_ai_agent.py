"""
Tests for the Claude-backed agentic clue layer.

Every test passes an explicit `client=` (a fake stub, or None) — none of them
rely on the ambient absence of ANTHROPIC_API_KEY as their only safeguard, so
this suite is safe to run even if a real key happens to be exported.
"""
import json
from types import SimpleNamespace

from ai_agent import generate_detective_clue


def _text_response(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.call_count = 0
        self.last_kwargs = None

        class _Messages:
            def create(_self, **kwargs):
                self.call_count += 1
                self.last_kwargs = kwargs
                if self._exception:
                    raise self._exception
                return self._response

        self.messages = _Messages()


# --- generate_detective_clue: happy path -------------------------------------

def test_generate_detective_clue_happy_path_uses_llm_response():
    secret = 36
    available_keys = ["is_even", "digit_count"]
    response = _text_response(json.dumps({"fact_key": "is_even", "clue_text": "It's even."}))
    client = FakeClient(response=response)

    result = generate_detective_clue(secret, guess=10, low=1, high=75, revealed_fact_keys=[], client=client)

    assert result["source"] == "llm"
    assert result["fact_key"] in available_keys
    assert result["clue_text"] == "It's even."
    assert client.call_count == 1


# --- generate_detective_clue: fallback paths ---------------------------------

def test_generate_detective_clue_no_client_configured_falls_back():
    # Fallback now randomly blends a static fact with a comparative hint, so
    # fact_key may legitimately be None (comparative branch) — only source
    # and the no-leak guarantee are invariant here.
    result = generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=[], client=None)
    assert result["source"] == "fallback"
    assert "36" not in result["clue_text"]


def test_generate_detective_clue_api_exception_falls_back():
    client = FakeClient(exception=RuntimeError("connection error"))
    result = generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=[], client=client)
    assert result["source"] == "fallback"


def test_generate_detective_clue_disallowed_fact_key_falls_back():
    response = _text_response(json.dumps({"fact_key": "totally_made_up", "clue_text": "Nope."}))
    client = FakeClient(response=response)
    result = generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=[], client=client)
    assert result["source"] == "fallback"


def test_generate_detective_clue_leaked_secret_falls_back():
    response = _text_response(json.dumps({"fact_key": "is_even", "clue_text": "The number is 36."}))
    client = FakeClient(response=response)
    result = generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=[], client=client)
    assert result["source"] == "fallback"
    assert "36" not in result["clue_text"]


def test_generate_detective_clue_malformed_json_falls_back():
    response = _text_response("not json at all")
    client = FakeClient(response=response)
    result = generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=[], client=client)
    assert result["source"] == "fallback"


def test_generate_detective_clue_prompt_includes_guess_history_and_direction():
    response = _text_response(json.dumps({"fact_key": "is_even", "clue_text": "It's even."}))
    client = FakeClient(response=response)

    generate_detective_clue(
        36, guess=61, low=1, high=75, revealed_fact_keys=[],
        guess_history=[10, 45], direction="Too High",
        client=client,
    )

    prompt_text = json.dumps(client.last_kwargs["messages"])
    assert "61" in prompt_text
    assert "10" in prompt_text and "45" in prompt_text
    assert "too high" in prompt_text.lower()


def test_generate_detective_clue_prompt_lists_fact_descriptions_not_just_keys():
    response = _text_response(json.dumps({"fact_key": "is_even", "clue_text": "It's even."}))
    client = FakeClient(response=response)

    generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=[], client=client)

    prompt_text = json.dumps(client.last_kwargs["messages"])
    # 36 is even -> the plain description "The number is even." should be
    # present in the prompt material, not just the bare fact_key.
    assert "is even" in prompt_text.lower()


def test_generate_detective_clue_exhausted_pool_short_circuits_before_any_api_call():
    from logic_utils import get_available_facts

    all_keys = [f["fact_key"] for f in get_available_facts(36, 1, 75, [])]
    client = FakeClient(response=_text_response(json.dumps({"fact_key": "x", "clue_text": "y"})))

    result = generate_detective_clue(36, guess=10, low=1, high=75, revealed_fact_keys=all_keys, client=client)

    assert result["source"] == "fallback"
    assert client.call_count == 0


def test_generate_detective_clue_exhausted_pool_gives_comparative_hint_instead_of_dead_end():
    from logic_utils import get_available_facts

    all_keys = [f["fact_key"] for f in get_available_facts(36, 1, 75, [])]
    client = FakeClient(response=_text_response(json.dumps({"fact_key": "x", "clue_text": "y"})))

    result = generate_detective_clue(
        36, guess=61, low=1, high=75, revealed_fact_keys=all_keys,
        direction="Too High", client=client,
    )

    assert result["source"] == "fallback"
    assert result["fact_key"] is None
    assert client.call_count == 0
    assert result["clue_text"] != "No more clues available — trust your deductions, detective."
    assert "36" not in result["clue_text"]
