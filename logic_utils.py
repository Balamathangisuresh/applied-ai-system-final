import math
import random

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


def _digits(n: int) -> str:
    return str(abs(n))


def _tens_digit_is_double_units(n: int) -> bool:
    d = _digits(n)
    if len(d) != 2:
        return False
    tens, units = int(d[0]), int(d[1])
    return units != 0 and tens == 2 * units


def _contains_digit_7(n: int) -> bool:
    return "7" in _digits(n)


def _all_digits_identical(n: int) -> bool:
    d = _digits(n)
    return len(d) > 1 and len(set(d)) == 1


_FACT_REGISTRY = [
    {
        "fact_key": "is_even",
        "coarseness": 1,
        "predicate": lambda secret, low, high: secret % 2 == 0,
        "description": "The number is even.",
        "template": "Case update: The safe lock's number is even.",
    },
    {
        "fact_key": "is_odd",
        "coarseness": 1,
        "predicate": lambda secret, low, high: secret % 2 != 0,
        "description": "The number is odd.",
        "template": "Case update: The safe lock's number is odd.",
    },
    {
        "fact_key": "upper_half",
        "coarseness": 2,
        "predicate": lambda secret, low, high: secret > (low + high) / 2,
        "description": "The number lies in the upper half of the suspect range.",
        "template": "Case update: The safe lock's number falls in the upper half of the suspect range.",
    },
    {
        "fact_key": "lower_half",
        "coarseness": 2,
        "predicate": lambda secret, low, high: secret <= (low + high) / 2,
        "description": "The number lies in the lower half of the suspect range.",
        "template": "Case update: The safe lock's number falls in the lower half of the suspect range.",
    },
    {
        "fact_key": "divisible_by_3",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 3 == 0,
        "description": "The number is divisible by 3.",
        "template": "Case update: The safe lock's number divides evenly by 3.",
    },
    {
        "fact_key": "divisible_by_4",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 4 == 0,
        "description": "The number is divisible by 4.",
        "template": "Case update: The safe lock's number divides evenly by 4.",
    },
    {
        "fact_key": "divisible_by_5",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 5 == 0,
        "description": "The number is divisible by 5.",
        "template": "Case update: The safe lock's number divides evenly by 5.",
    },
    {
        "fact_key": "divisible_by_6",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 6 == 0,
        "description": "The number is divisible by 6.",
        "template": "Case update: The safe lock's number divides evenly by 6.",
    },
    {
        "fact_key": "divisible_by_7",
        "coarseness": 3,
        "predicate": lambda secret, low, high: secret % 7 == 0,
        "description": "The number is divisible by 7.",
        "template": "Case update: The safe lock's number divides evenly by 7.",
    },
    {
        "fact_key": "digit_sum_even",
        "coarseness": 2,
        "predicate": lambda secret, low, high: _digit_sum(secret) % 2 == 0,
        "description": "The digits add up to an even sum.",
        "template": "Case update: The safe lock's digits add up to an even sum.",
    },
    {
        "fact_key": "digit_sum_odd",
        "coarseness": 2,
        "predicate": lambda secret, low, high: _digit_sum(secret) % 2 != 0,
        "description": "The digits add up to an odd sum.",
        "template": "Case update: The safe lock's digits add up to an odd sum.",
    },
    {
        "fact_key": "is_prime",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _is_prime(secret),
        "description": "The number is prime.",
        "template": "Case update: The safe lock's number is prime.",
    },
    {
        "fact_key": "is_perfect_square",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _is_perfect_square(secret),
        "description": "The number is a perfect square.",
        "template": "Case update: The safe lock's number is a perfect square.",
    },
    {
        "fact_key": "digit_sum",
        "coarseness": 5,
        "predicate": lambda secret, low, high: True,
        "description": "The digits sum to {value}.",
        "template": "Case update: The sum of the digits on the safe lock equals {value}.",
        "value_fn": _digit_sum,
    },
    {
        "fact_key": "digit_count",
        "coarseness": 1,
        "predicate": lambda secret, low, high: True,
        "description": "The number has {value} digit(s).",
        "template": "Case update: The safe lock's number has {value} digit(s).",
        "value_fn": lambda n: len(str(abs(n))),
    },
    {
        "fact_key": "tens_digit_double_units",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _tens_digit_is_double_units(secret),
        "description": "The tens digit is double the units digit.",
        "template": "Case update: The safe lock's tens digit is double its units digit.",
    },
    {
        "fact_key": "contains_digit_7",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _contains_digit_7(secret),
        "description": "It contains the digit 7 at least once.",
        "template": "Case update: The safe lock's number contains the digit 7 at least once.",
    },
    {
        "fact_key": "all_digits_identical",
        "coarseness": 4,
        "predicate": lambda secret, low, high: _all_digits_identical(secret),
        "description": "All of its digits are identical.",
        "template": "Case update: All of the safe lock's digits are identical.",
    },
]


def _render_text(text: str, fact: dict, secret: int) -> str:
    if "value_fn" in fact:
        return text.format(value=fact["value_fn"](secret))
    return text


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


def get_unrevealed_true_facts(secret: int, low: int, high: int, revealed_fact_keys):
    """
    Raw, unformatted true-fact material for the LLM to reason over and choose
    from — plain statements ("The number is even."), not in-theme clue text.
    Python still does 100% of the math: every entry here is already verified
    true about secret, so the LLM can never hallucinate a false fact.
    """
    available = get_available_facts(secret, low, high, revealed_fact_keys)
    facts = [
        {
            "fact_key": fact["fact_key"],
            "description": _render_text(fact["description"], fact, secret),
        }
        for fact in available
    ]
    random.shuffle(facts)  # presentation order only — doesn't affect which facts are true
    return facts


def select_fallback_fact(available_facts):
    """Randomly pick one of the available facts, or None if empty — keeps clue
    order varied across games instead of always the same vaguest-first order."""
    if not available_facts:
        return None
    return random.choice(available_facts)


def render_fallback_clue(fact, secret: int):
    """Render a canned, secret-leak-free clue string for a fact dict."""
    if fact is None:
        return "No more clues available — trust your deductions, detective."
    return _render_text(fact["template"], fact, secret)


_TOO_HIGH_PHRASINGS = [
    "Case update: That guess runs too high — the true number is lower.",
    "Case update: The dial's reading too high, detective. Aim lower.",
    "Case update: You've overshot the mark — the number is lower than that.",
    "Case update: Too high. Trust your gut and try a lower number.",
]

_TOO_LOW_PHRASINGS = [
    "Case update: That guess runs too low — the true number is higher.",
    "Case update: The dial's reading too low, detective. Aim higher.",
    "Case update: You've undershot the mark — the number is higher than that.",
    "Case update: Too low. Trust your gut and try a higher number.",
]

_COMPARATIVE_DIVISORS = (2, 3, 4, 5, 6, 7)


def _comparative_candidates(guess: int, secret: int, direction: str):
    """Every true, secret-leak-safe statement comparing guess to secret —
    parity, small-divisor overlap, digit sum, and the too-high/low direction."""
    candidates = []

    if direction == "Too High":
        candidates.extend(_TOO_HIGH_PHRASINGS)
    elif direction == "Too Low":
        candidates.extend(_TOO_LOW_PHRASINGS)

    guess_even, secret_even = guess % 2 == 0, secret % 2 == 0
    if guess_even == secret_even:
        parity = "even" if secret_even else "odd"
        candidates.append(
            f"Case update: You're on the right track — like your guess, the safe lock's number is {parity}."
        )
    else:
        guess_parity = "even" if guess_even else "odd"
        secret_parity = "even" if secret_even else "odd"
        candidates.append(
            f"Case update: Not quite — your guess was {guess_parity}, but the safe lock's number is {secret_parity}."
        )

    for d in _COMPARATIVE_DIVISORS:
        guess_div, secret_div = guess % d == 0, secret % d == 0
        if guess_div and secret_div:
            candidates.append(
                f"Case update: You're on the right track — like your guess, the safe lock's number divides evenly by {d}."
            )
        elif secret_div and not guess_div:
            candidates.append(
                f"Case update: The safe lock's number divides evenly by {d}, but your guess doesn't — worth another look."
            )
        elif guess_div and not secret_div:
            candidates.append(
                f"Case update: Your guess divides evenly by {d}, but the safe lock's number does not."
            )

    guess_digit_sum, secret_digit_sum = _digit_sum(guess), _digit_sum(secret)
    if guess_digit_sum == secret_digit_sum:
        candidates.append(
            f"Case update: You're on the right track — the safe lock's digits add up to {secret_digit_sum}, just like your guess!"
        )
    elif secret_digit_sum > guess_digit_sum:
        candidates.append("Case update: The safe lock's digits add up to more than your guess's do.")
    else:
        candidates.append("Case update: The safe lock's digits add up to less than your guess's do.")

    return candidates


def generate_comparative_hint(guess: int, secret: int, direction: str = None):
    """
    Endless, guess-relative hint source: compares the current guess against
    the secret (parity, small-divisor overlap, digit sum) plus the
    too-high/too-low direction, then randomly picks one true comparison.
    Unlike the one-time facts in _FACT_REGISTRY, this never runs dry — it's
    relative to *this* guess, not a fixed fact about the secret — so it can
    be given every attempt without ever repeating the exact same line twice
    in a row by coincidence alone.
    """
    candidates = _comparative_candidates(guess, secret, direction)
    if not candidates:
        return "No more clues available — trust your deductions, detective."
    return random.choice(candidates)


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
