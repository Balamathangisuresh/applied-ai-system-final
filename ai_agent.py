import json
import os
import random

from logic_utils import (
    get_available_facts,
    get_unrevealed_true_facts,
    select_fallback_fact,
    render_fallback_clue,
    generate_comparative_hint,
)

CLUE_MAX_CHARS = 400
DEFAULT_MODEL = "claude-haiku-4-5"

_DIRECTION_HINTS = {
    "Too High": "too high — the safe's true number is lower than that",
    "Too Low": "too low — the safe's true number is higher than that",
}


def get_client(api_key=None):
    """Resolve an Anthropic client, or None if no API key is configured anywhere."""
    if api_key is None:
        try:
            import streamlit as st
            api_key = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return None

    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _extract_text(response):
    for block in response.content:
        if block.type == "text":
            return block.text
    return None


def _format_guess_history(guess_history):
    numeric = [g for g in (guess_history or []) if isinstance(g, int)]
    if not numeric:
        return "none yet — this is their first guess"
    return ", ".join(str(g) for g in numeric)


COMPARATIVE_HINT_CHANCE = 0.8  # most hints should react to the current guess


def _build_fallback_clue(guess, secret, direction, available):
    """
    Mostly favor an endless, guess-relative comparative hint over a one-time
    static fact, so clue variety and order aren't fixed game to game — the
    same static fact pool no longer always plays out even/odd, then digits,
    then factors in the same sequence, and most attempts react to this guess.
    """
    if not available or random.random() < COMPARATIVE_HINT_CHANCE:
        return {"clue_text": generate_comparative_hint(guess, secret, direction), "fact_key": None, "source": "fallback"}
    fact = select_fallback_fact(available)
    return {"clue_text": render_fallback_clue(fact, secret), "fact_key": fact["fact_key"], "source": "fallback"}


def generate_detective_clue(
    secret, guess, low, high, revealed_fact_keys,
    guess_history=None, direction=None,
    client=None, model=DEFAULT_MODEL,
):
    """
    Analyze (Python): compute which true facts about secret are still unrevealed,
    plus the player's guess history and whether this guess was too high/low.
    Tool Call (Python): get_unrevealed_true_facts already verified every fact
    against secret — Python owns 100% of the math, so the LLM can only ever
    choose among facts that are actually true.
    Refine & Output (Claude): acting as a noir Game Master, react to the guess
    and the run so far, pick exactly one fact_key from the pool, and write
    original atmospheric narration around it — no canned template phrasing.
    """
    available = get_available_facts(secret, low, high, revealed_fact_keys)

    if not available:
        # The one-time fact pool is dry, but a comparative hint never runs out
        # — it's relative to this guess, not a fixed fact about the secret —
        # so the player still gets useful, non-repetitive guidance every attempt.
        return {"clue_text": generate_comparative_hint(guess, secret, direction), "fact_key": None, "source": "fallback"}

    if client is None:
        client = get_client()

    if client is None:
        return _build_fallback_clue(guess, secret, direction, available)

    facts = get_unrevealed_true_facts(secret, low, high, revealed_fact_keys)
    allowed_keys = [f["fact_key"] for f in facts]
    fact_lines = "\n".join(f"- {f['fact_key']}: {f['description']}" for f in facts)
    direction_text = _DIRECTION_HINTS.get(direction, "unknown relative to the target")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=180,
            system=(
                "You are the Game Master of a 1940s noir detective mystery. The player is "
                "cracking a safe by guessing its combination. React in character to how their "
                "guess and prior attempts are going, then pick exactly one fact_key from the "
                "list you're given and build a short, original clue around it. Never invent a "
                "fact that wasn't given to you, and never state or imply the exact secret "
                "number. Write 1-2 sentences — no canned phrasing, no repeating previous clues."
            ),
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "fact_key": {"type": "string", "enum": allowed_keys},
                            "clue_text": {"type": "string"},
                        },
                        "required": ["fact_key", "clue_text"],
                        "additionalProperties": False,
                    },
                }
            },
            messages=[{
                "role": "user",
                "content": (
                    f"The player just guessed {guess}, which was {direction_text}. "
                    f"Their guesses so far this case: {_format_guess_history(guess_history)}.\n\n"
                    f"Verified true facts still available to reveal (choose exactly one):\n{fact_lines}\n\n"
                    "Write the atmospheric clue now."
                ),
            }],
        )
        text = _extract_text(response)
        data = json.loads(text)
        fact_key = data["fact_key"]
        clue_text = data["clue_text"]

        if fact_key not in allowed_keys:
            raise ValueError("fact_key not in allowed pool")
        if not clue_text or len(clue_text) > CLUE_MAX_CHARS:
            raise ValueError("invalid clue length")
        if str(secret) in clue_text:
            raise ValueError("clue leaks secret")

        return {"clue_text": clue_text, "fact_key": fact_key, "source": "llm"}

    except Exception:
        return _build_fallback_clue(guess, secret, direction, available)
