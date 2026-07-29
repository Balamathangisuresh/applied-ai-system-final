from logic_utils import (
    check_guess,
    parse_guess,
    calculate_boss_score,
    get_detective_tier_config,
    get_boss_tier_config,
    compute_boss_attack,
    get_available_facts,
    select_fallback_fact,
    render_fallback_clue,
    compute_stats,
    compute_efficiency,
    compute_boss_run_stats,
    compute_boss_efficiency,
)


def test_winning_guess():
    # If the secret is 50 and guess is 50, it should be a win
    outcome, _ = check_guess(50, 50)
    assert outcome == "Win"

def test_guess_too_high():
    # If secret is 50 and guess is 60, hint should be "Too High"
    outcome, _ = check_guess(60, 50)
    assert outcome == "Too High"

def test_guess_too_low():
    # If secret is 50 and guess is 40, hint should be "Too Low"
    outcome, _ = check_guess(40, 50)
    assert outcome == "Too Low"


# FIX line 34: hint messages should match the direction the player needs to go
def test_too_high_message_says_go_lower():
    outcome, message = check_guess(60, 50)
    assert outcome == "Too High"
    assert "LOWER" in message

def test_too_low_message_says_go_higher():
    outcome, message = check_guess(40, 50)
    assert outcome == "Too Low"
    assert "HIGHER" in message


# FIX line 44: string secret comparison should be numeric, not lexicographic
def test_string_secret_too_low_numeric():
    # 9 < 10 numerically, but "9" > "10" lexicographically — must use int comparison
    outcome, message = check_guess(9, "10")
    assert outcome == "Too Low"

def test_string_secret_too_high_numeric():
    # 11 > 10 both numerically and lexicographically — sanity check
    outcome, message = check_guess(11, "10")
    assert outcome == "Too High"

def test_string_secret_win():
    outcome, message = check_guess(10, "10")
    assert outcome == "Win"


# --- parse_guess -----------------------------------------------------------

def test_parse_guess_valid_int():
    ok, value, err = parse_guess("42")
    assert ok is True
    assert value == 42
    assert err is None

def test_parse_guess_valid_float_string():
    ok, value, err = parse_guess("50.0")
    assert ok is True
    assert value == 50

def test_parse_guess_empty_string():
    ok, value, err = parse_guess("")
    assert ok is False
    assert err is not None

def test_parse_guess_none():
    ok, value, err = parse_guess(None)
    assert ok is False
    assert err is not None

def test_parse_guess_non_numeric():
    ok, value, err = parse_guess("banana")
    assert ok is False
    assert err is not None

def test_parse_guess_negative_number():
    ok, value, err = parse_guess("-5")
    assert ok is True
    assert value == -5


# --- calculate_boss_score ---------------------------------------------------

def test_calculate_boss_score_more_damage_scores_higher():
    low_damage = calculate_boss_score(damage_dealt_total=20, attempts=4, defeated=False)
    high_damage = calculate_boss_score(damage_dealt_total=80, attempts=4, defeated=False)
    assert high_damage > low_damage

def test_calculate_boss_score_defeating_boss_scores_higher():
    same_attempts_loss = calculate_boss_score(damage_dealt_total=80, attempts=4, defeated=False)
    same_attempts_win = calculate_boss_score(damage_dealt_total=80, attempts=4, defeated=True)
    assert same_attempts_win > same_attempts_loss

def test_calculate_boss_score_never_negative():
    assert calculate_boss_score(damage_dealt_total=0, attempts=50, defeated=False) == 0


# --- tier configs ------------------------------------------------------------

def test_detective_tier_rookie_case():
    config = get_detective_tier_config("Rookie Case")
    assert config["low"] == 1
    assert config["high"] == 30
    assert config["max_attempts"] == 8

def test_detective_tier_master_case():
    config = get_detective_tier_config("Master Case")
    assert config["low"] == 1
    assert config["high"] == 150

def test_detective_tier_unknown_falls_back():
    config = get_detective_tier_config("Nonsense Tier")
    assert config["low"] == 1
    assert config["high"] > 0

def test_boss_tier_goblin():
    config = get_boss_tier_config("Goblin")
    assert config["low"] == 1
    assert config["high"] == 20
    assert config["max_hp"] == 50

def test_boss_tier_dragon_is_hardest():
    goblin = get_boss_tier_config("Goblin")
    dragon = get_boss_tier_config("Dragon")
    assert dragon["max_hp"] > goblin["max_hp"]
    assert dragon["high"] > goblin["high"]

def test_boss_tier_unknown_falls_back():
    config = get_boss_tier_config("Nonsense Tier")
    assert config["max_hp"] > 0


# --- compute_boss_attack -------------------------------------------------------

def test_compute_boss_attack_exact_guess_is_critical():
    damage, is_critical, _ = compute_boss_attack(guess=25, secret=25)
    assert is_critical is True
    assert damage == 20

def test_compute_boss_attack_off_by_one_deals_lots_of_damage():
    damage, is_critical, _ = compute_boss_attack(guess=26, secret=25)
    assert damage == 10
    assert is_critical is False

def test_compute_boss_attack_off_by_two_deals_some_damage():
    damage, is_critical, _ = compute_boss_attack(guess=27, secret=25)
    assert damage == 5
    assert is_critical is False

def test_compute_boss_attack_off_by_a_few_deals_little_damage():
    for offset in (3, 4, 5):
        damage, is_critical, _ = compute_boss_attack(guess=25 + offset, secret=25)
        assert damage == 1
        assert is_critical is False

def test_compute_boss_attack_far_off_is_a_complete_miss():
    damage, is_critical, _ = compute_boss_attack(guess=25 + 6, secret=25)
    assert damage == 0
    assert is_critical is False


# --- compute_boss_run_stats / compute_boss_efficiency -------------------------

def test_compute_boss_run_stats_average_and_best_error():
    stats = compute_boss_run_stats([{"error": 5}, {"error": 1}, {"error": 3}])
    assert stats["best_error"] == 1
    assert stats["average_error"] == 3

def test_compute_boss_run_stats_empty_log():
    stats = compute_boss_run_stats([])
    assert stats["best_error"] is None
    assert stats["average_error"] == 0

def test_compute_boss_efficiency_scales_with_rounds_played():
    # ideal_per_round for range_span=99 is 7; two rounds -> ideal_total=14
    assert compute_boss_efficiency(range_span=99, rounds_played=2, total_attempts=14) == 100
    assert compute_boss_efficiency(range_span=99, rounds_played=2, total_attempts=28) == 50

def test_compute_boss_efficiency_zero_attempts():
    assert compute_boss_efficiency(range_span=99, rounds_played=1, total_attempts=0) == 0


# --- fact registry / clue fallback -------------------------------------------

def test_get_available_facts_only_returns_true_facts():
    facts = get_available_facts(secret=36, low=1, high=75, revealed_fact_keys=[])
    fact_keys = {f["fact_key"] for f in facts}
    assert "is_even" in fact_keys
    assert "is_odd" not in fact_keys

def test_get_available_facts_excludes_revealed():
    facts = get_available_facts(secret=36, low=1, high=75, revealed_fact_keys=["is_even"])
    fact_keys = {f["fact_key"] for f in facts}
    assert "is_even" not in fact_keys

def test_get_available_facts_empty_when_exhausted():
    all_keys = [f["fact_key"] for f in get_available_facts(36, 1, 75, [])]
    facts = get_available_facts(secret=36, low=1, high=75, revealed_fact_keys=all_keys)
    assert facts == []

def test_select_fallback_fact_returns_none_for_empty_list():
    assert select_fallback_fact([]) is None

def test_render_fallback_clue_never_leaks_secret():
    facts = get_available_facts(secret=137, low=1, high=150, revealed_fact_keys=[])
    for fact in facts:
        clue = render_fallback_clue(fact, secret=137)
        assert "137" not in clue


# --- stats / efficiency -------------------------------------------------------

def test_compute_stats_average_error_and_best_guess():
    stats = compute_stats(history=[10, 40, 48], secret=50)
    assert stats["best_guess"] == 48
    assert stats["average_error"] > 0

def test_compute_stats_ignores_non_numeric_entries():
    stats = compute_stats(history=["banana", 45], secret=50)
    assert stats["best_guess"] == 45

def test_compute_stats_empty_history():
    stats = compute_stats(history=[], secret=50)
    assert stats["best_guess"] is None
    assert stats["average_error"] == 0

def test_compute_efficiency_clamped_at_100():
    # range 1-100 -> ideal is 7 guesses; using fewer than ideal must clamp at 100
    assert compute_efficiency(range_span=99, attempts_used=3) == 100

def test_compute_efficiency_known_value():
    # ideal_guesses for range_span=99 is ceil(log2(99)) = 7
    assert compute_efficiency(range_span=99, attempts_used=7) == 100
    assert compute_efficiency(range_span=99, attempts_used=14) == 50
