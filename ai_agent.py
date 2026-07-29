import json
import os

from logic_utils import (
    get_available_facts,
    select_fallback_fact,
    render_fallback_clue,
)

CLUE_MAX_CHARS = 300
COACH_MAX_CHARS = 600
DEFAULT_MODEL = "claude-haiku-4-5"


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


def generate_detective_clue(secret, guess, low, high, revealed_fact_keys, client=None, model=DEFAULT_MODEL):
    """
    Analyze (Python): compute which true facts about secret are still unrevealed.
    Tool Call (Python): get_available_facts already verified each fact against secret.
    Refine & Output (Claude): pick one unused fact_key and phrase it as a clue.
    """
    available = get_available_facts(secret, low, high, revealed_fact_keys)

    if not available:
        return {"clue_text": render_fallback_clue(None, secret), "fact_key": None, "source": "fallback"}

    fallback_fact = select_fallback_fact(available)

    if client is None:
        client = get_client()

    if client is None:
        return {
            "clue_text": render_fallback_clue(fallback_fact, secret),
            "fact_key": fallback_fact["fact_key"],
            "source": "fallback",
        }

    allowed_keys = [f["fact_key"] for f in available]

    try:
        response = client.messages.create(
            model=model,
            max_tokens=150,
            system=(
                "You are a Game Master Detective narrating a number-guessing mystery. "
                "Pick exactly one fact_key from the allowed list and phrase it as a short, "
                "thematic 'case file' clue. Never reveal the secret number itself."
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
                    f"The player just guessed {guess}. Allowed fact_keys: {allowed_keys}. "
                    "Choose exactly one and write the clue."
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
        return {
            "clue_text": render_fallback_clue(fallback_fact, secret),
            "fact_key": fallback_fact["fact_key"],
            "source": "fallback",
        }


def _fallback_coach_text(stats):
    efficiency = stats.get("efficiency_pct", 0)
    if efficiency >= 80:
        return "Excellent work — your guesses closed in on the target efficiently."
    if efficiency >= 50:
        return "Solid effort, though a few guesses drifted further than they needed to."
    return "You got there eventually, but there's plenty of room to narrow your search faster."


def generate_coach_review(stats, client=None, model=DEFAULT_MODEL):
    if client is None:
        client = get_client()

    if client is None:
        return {"text": _fallback_coach_text(stats), "source": "fallback"}

    try:
        response = client.messages.create(
            model=model,
            max_tokens=150,
            system=(
                "You are an encouraging game coach. Write 2-3 sentences of feedback "
                "based only on the stats provided. Do not invent numbers."
            ),
            messages=[{
                "role": "user",
                "content": f"Stats: {json.dumps(stats)}",
            }],
        )
        text = _extract_text(response)
        if not text or not text.strip() or len(text) > COACH_MAX_CHARS:
            raise ValueError("invalid coach text")
        return {"text": text.strip(), "source": "llm"}
    except Exception:
        return {"text": _fallback_coach_text(stats), "source": "fallback"}
