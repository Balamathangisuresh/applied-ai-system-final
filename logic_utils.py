import math

# ---------------------------------------------------------------------------
# Shared parsing / comparison primitives
# ---------------------------------------------------------------------------

def parse_guess(raw: str):
    """
    Parse user input into an int guess.

    Returns: (ok: bool, guess_int: int | None, error_message: str | None)
    """
    if raw is None:
        return False, None, "Enter a guess."

    if raw == "":
        return False, None, "Enter a guess."

    try:
        if "." in raw:
            value = int(float(raw))
        else:
            value = int(raw)
    except Exception:
        return False, None, "That is not a number."

    return True, value, None


def check_guess(guess, secret):
    """
    Compare guess to secret and return (outcome, message).

    outcome examples: "Win", "Too High", "Too Low"
    """
    if guess == secret:
        return "Win", "🎉 Correct!"
    try:
        if guess > secret:
            return "Too High", "📉 Go LOWER!"
        else:
            return "Too Low", "📈 Go HIGHER!"
    except TypeError:
        g = str(guess)
        if g == secret:
            return "Win", "🎉 Correct!"
        if int(g) > int(secret):
            return "Too High", "📉 Go LOWER!"
        else:
            return "Too Low", "📈 Go HIGHER!"


def calculate_boss_score(damage_dealt_total: int, attempts: int, defeated: bool):
    """Score for Boss Fight mode: reward total damage, penalize wasted attempts."""
    score = damage_dealt_total - 3 * attempts
    if defeated:
        score += 50
    return max(score, 0)


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

_DETECTIVE_TIERS = {
    "Rookie Case": {"low": 1, "high": 30, "max_attempts": 8},
    "Detective Case": {"low": 1, "high": 75, "max_attempts": 8},
    "Master Case": {"low": 1, "high": 150, "max_attempts": 7},
}

_BOSS_TIERS = {
    # max_attempts is per round: each round is its own mini guessing game
    # against a fresh secret; boss_hp carries over between rounds.
    "Goblin": {"low": 1, "high": 20, "max_hp": 50, "max_attempts": 8},
    "Knight": {"low": 1, "high": 50, "max_hp": 80, "max_attempts": 8},
    "Dragon": {"low": 1, "high": 100, "max_hp": 120, "max_attempts": 7},
}

DETECTIVE_DEFAULT_TIER = "Detective Case"
BOSS_DEFAULT_TIER = "Knight"


def get_detective_tier_config(tier_name: str):
    return dict(_DETECTIVE_TIERS.get(tier_name, _DETECTIVE_TIERS[DETECTIVE_DEFAULT_TIER]))


def get_boss_tier_config(tier_name: str):
    return dict(_BOSS_TIERS.get(tier_name, _BOSS_TIERS[BOSS_DEFAULT_TIER]))


def detective_tier_names():
    return list(_DETECTIVE_TIERS.keys())


def boss_tier_names():
    return list(_BOSS_TIERS.keys())


# ---------------------------------------------------------------------------
# Boss Fight combat — each round is its own mini number-guessing game against
# the current secret; damage is a fixed function of how close the guess was.
# ---------------------------------------------------------------------------

def compute_boss_attack(guess: int, secret: int):
    """Return (damage: int, is_critical: bool, flavor_text: str) for one attack."""
    error = abs(guess - secret)

    if error == 0:
        return 20, True, "🎯 Critical hit! The attack strikes true!"
    if error == 1:
        return 10, False, "🔥 Massive damage! That was incredibly close!"
    if error == 2:
        return 5, False, "⚔️ Solid hit — some good damage there."
    if error <= 5:
        return 1, False, "🤏 A grazing hit. Little damage."
    return 0, False, "💨 Complete miss! The attack does nothing."


# ---------------------------------------------------------------------------
# Detective clue facts (the deterministic "tool call" layer)
# ---------------------------------------------------------------------------

def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(math.isqrt(n)) + 1):
        if n % i == 0:
            return False
    return True


def _is_perfect_square(n: int) -> bool:
    if n < 0:
        return False
    root = math.isqrt(n)
    return root * root == n


def _digit_sum(n: int) -> int:
    return sum(int(d) for d in str(abs(n)))


_FACT_REGISTRY = [
    {
        "fact_key": "is_even",
        "coarseness": 1,
        "predicate": lambda secret, low, high: secret % 2 == 0,
        "template": "Case file update: the safe's number is even.",
    },
    {
        "fact_key": "is_odd",
        "coarseness": 1,
        "predicate": lambda secret, low, high: secret % 2 != 0,
        "template": "Case file update: the safe's number is odd.",
    },
    {
        "fact_key": "upper_half",
        "coarseness": 2,
        "predicate": lambda secret, low, high: secret > (low + high) / 2,
        "template": "Case file update: the number lies in the upper half of the suspect range.",
    },
    {
        "fact_key": "lower_half",
        "coarseness": 2,
        "predicate": lambda secret, low, high: secret <= (low + high) / 2,
        "template": "Case file update: the number lies in the lower half of the suspect range.",
    },
    {
        "fact_key": "divisible_by_3",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 3 == 0,
        "template": "Case file update: the number is divisible by 3.",
    },
    {
        "fact_key": "divisible_by_4",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 4 == 0,
        "template": "Case file update: the number is divisible by 4.",
    },
    {
        "fact_key": "is_prime",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _is_prime(secret),
        "template": "Case file update: the number is prime.",
    },
    {
        "fact_key": "is_perfect_square",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _is_perfect_square(secret),
        "template": "Case file update: the number is a perfect square.",
    },
    {
        "fact_key": "digit_sum",
        "coarseness": 5,
        "predicate": lambda secret, low, high: True,
        "template": "Case file update: the sum of the safe's combination digits is {value}.",
        "value_fn": _digit_sum,
    },
    {
        "fact_key": "digit_count",
        "coarseness": 1,
        "predicate": lambda secret, low, high: True,
        "template": "Case file update: the safe's number has {value} digit(s).",
        "value_fn": lambda n: len(str(abs(n))),
    },
]


def get_available_facts(secret: int, low: int, high: int, revealed_fact_keys):
    """Return true, not-yet-revealed facts about secret, sorted by coarseness (vaguest first)."""
    revealed = set(revealed_fact_keys or [])
    available = []
    for fact in _FACT_REGISTRY:
        if fact["fact_key"] in revealed:
            continue
        if fact["predicate"](secret, low, high):
            available.append(fact)
    return sorted(available, key=lambda f: f["coarseness"])


def select_fallback_fact(available_facts):
    """Deterministically pick the least-revealing available fact, or None if empty."""
    if not available_facts:
        return None
    return available_facts[0]


def render_fallback_clue(fact, secret: int):
    """Render a canned, secret-leak-free clue string for a fact dict."""
    if fact is None:
        return "No more clues available — trust your deductions, detective."
    template = fact["template"]
    if "value_fn" in fact:
        return template.format(value=fact["value_fn"](secret))
    return template


# ---------------------------------------------------------------------------
# Stats / efficiency (shared by both modes)
# ---------------------------------------------------------------------------

def compute_stats(history, secret: int):
    """history: list of int guesses (non-numeric entries are ignored)."""
    numeric_guesses = [g for g in history if isinstance(g, int)]
    if not numeric_guesses:
        return {"average_error": 0, "best_guess": None}

    errors = [abs(g - secret) for g in numeric_guesses]
    average_error = sum(errors) / len(errors)
    best_guess = min(numeric_guesses, key=lambda g: abs(g - secret))
    return {"average_error": average_error, "best_guess": best_guess}


def compute_efficiency(range_span: int, attempts_used: int):
    """Efficiency % relative to an information-theoretic binary-search ideal."""
    if attempts_used <= 0:
        return 0
    ideal_guesses = max(1, math.ceil(math.log2(max(1, range_span))))
    return min(100, round(100 * ideal_guesses / attempts_used))


def compute_boss_run_stats(attack_log):
    """attack_log: list of {"error": int} dicts, one per attack across the whole fight."""
    errors = [entry["error"] for entry in attack_log]
    if not errors:
        return {"average_error": 0, "best_error": None}
    return {"average_error": sum(errors) / len(errors), "best_error": min(errors)}


def compute_boss_efficiency(range_span: int, rounds_played: int, total_attempts: int):
    """Efficiency % across a whole boss fight (possibly several rounds)."""
    if total_attempts <= 0:
        return 0
    ideal_per_round = max(1, math.ceil(math.log2(max(1, range_span))))
    ideal_total = ideal_per_round * max(1, rounds_played)
    return min(100, round(100 * ideal_total / total_attempts))
