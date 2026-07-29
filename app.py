import random

import streamlit as st

from logic_utils import (
    parse_guess,
    check_guess,
    calculate_boss_score,
    get_detective_tier_config,
    get_boss_tier_config,
    detective_tier_names,
    boss_tier_names,
    compute_boss_attack,
    compute_stats,
    compute_efficiency,
    compute_boss_run_stats,
    compute_boss_efficiency,
)
from ai_agent import generate_detective_clue, generate_coach_review
from theme import inject_theme, theme_image, theme_tagline

st.set_page_config(page_title="Mystery & Mayhem", page_icon="🎮")

MODE_LABELS = {"detective": "🕵️ Detective Mystery", "boss_fight": "⚔️ Boss Fight"}

if "mode" not in st.session_state:
    st.session_state.mode = "detective"
if "game_started" not in st.session_state:
    st.session_state.game_started = False

st.sidebar.header("Settings")
mode = st.sidebar.selectbox(
    "Game Mode",
    options=list(MODE_LABELS.keys()),
    format_func=lambda m: MODE_LABELS[m],
    index=list(MODE_LABELS.keys()).index(st.session_state.mode),
)

if mode == "detective":
    tier = st.sidebar.selectbox("Case Complexity", detective_tier_names())
    tier_config = get_detective_tier_config(tier)
else:
    tier = st.sidebar.selectbox("Boss Tier", boss_tier_names())
    tier_config = get_boss_tier_config(tier)

low, high = tier_config["low"], tier_config["high"]
max_attempts = tier_config["max_attempts"]

st.sidebar.caption(f"Range: {low} to {high}")
if mode == "boss_fight":
    st.sidebar.caption(f"Attempts allowed per round: {max_attempts}")
else:
    st.sidebar.caption(f"Attempts allowed: {max_attempts}")

inject_theme(mode)


def reset_game(mode, tier):
    st.session_state.mode = mode
    st.session_state.tier = tier
    st.session_state.secret = random.randint(low, high)
    st.session_state.attempts = 0
    st.session_state.history = []
    st.session_state.status = "playing"
    st.session_state.score = 0
    st.session_state.revealed_fact_keys = []
    st.session_state.clue_history = []
    st.session_state.boss_hp = tier_config.get("max_hp", 0)
    st.session_state.total_damage = 0
    st.session_state.total_attempts = 0
    st.session_state.round_number = 1
    st.session_state.rounds_won = 0
    st.session_state.attack_log = []
    st.session_state.last_damage = None
    st.session_state.last_crit = False
    st.session_state.coach_review = None
    st.session_state.case_number = random.randint(1, 999)


# --- Start / menu screen ------------------------------------------------------
if not st.session_state.game_started:
    st.title("Mystery & Mayhem")
    st.caption("Pick your game: crack a case, or take down a boss.")
    st.divider()

    left, right = st.columns([1, 2])
    with left:
        st.image(theme_image(mode), width=180)
    with right:
        st.subheader(MODE_LABELS[mode])
        st.write(theme_tagline(mode))
        st.write(f"**Range:** {low} to {high}")
        if mode == "boss_fight":
            st.write(f"**Boss HP:** {tier_config['max_hp']}  |  **Attempts per round:** {max_attempts}")
        else:
            st.write(f"**Attempts:** {max_attempts}")
        st.caption("Change the mode and tier from the sidebar, then start when you're ready.")

    st.divider()
    if st.button("Start Game", type="primary"):
        reset_game(mode, tier)
        st.session_state.game_started = True
        st.rerun()

    st.stop()

# --- Active game screen --------------------------------------------------------
if st.session_state.mode != mode or st.session_state.tier != tier:
    reset_game(mode, tier)

st.title("Mystery & Mayhem")

img_col, header_col = st.columns([1, 3])
with img_col:
    st.image(theme_image(mode), width=120)
with header_col:
    # Placeholders reserve their spot at the top of the page now, but are filled
    # in further down — after this run's guess has been processed — so they always
    # show the up-to-date attempts/HP instead of lagging one guess behind.
    if mode == "detective":
        st.subheader(f"🕵️ Case #{st.session_state.case_number:03d}")
        info_placeholder = st.empty()
    else:
        st.subheader("Boss Fight")
        round_info_placeholder = st.empty()
        hp_bar_placeholder = st.empty()
        hp_caption_placeholder = st.empty()

if mode == "detective":
    clues_placeholder = st.container()

# A form binds the text input and its submit button into one atomic action —
# without it, a fast click can fire before the typed value finishes syncing,
# which reads as "have to click Submit twice" and skipped attempt counts.
with st.form(key=f"guess_form_{mode}_{tier}", clear_on_submit=True):
    raw_guess = st.text_input("Enter your guess:")
    submit = st.form_submit_button("Submit Guess")

col1, col2, col3 = st.columns(3)
with col1:
    new_game = st.button("New Game")
with col2:
    back_to_menu = st.button("Back to Menu")
with col3:
    show_hint = st.checkbox("Show hint", value=True)

if new_game:
    reset_game(mode, tier)
    st.success("New game started.")
    st.rerun()

if back_to_menu:
    st.session_state.game_started = False
    st.rerun()

if st.session_state.status == "playing":
    if submit:
        ok, guess_int, err = parse_guess(raw_guess)

        if not ok:
            # Invalid input doesn't cost an attempt.
            st.session_state.history.append(raw_guess)
            st.error(err)
        else:
            st.session_state.attempts += 1
            st.session_state.history.append(guess_int)
            secret = st.session_state.secret

            if mode == "detective":
                outcome, _ = check_guess(guess_int, secret)

                if outcome == "Win":
                    st.balloons()
                    st.session_state.status = "won"
                    st.success(f"🎉 Case solved! The combination was {secret}.")
                else:
                    clue_result = generate_detective_clue(
                        secret, guess_int, low, high, st.session_state.revealed_fact_keys
                    )
                    if clue_result["fact_key"]:
                        st.session_state.revealed_fact_keys.append(clue_result["fact_key"])
                    st.session_state.clue_history.append(clue_result["clue_text"])
                    if show_hint:
                        st.warning(clue_result["clue_text"])

                    if st.session_state.attempts >= max_attempts:
                        st.session_state.status = "lost"
                        st.error(f"Case unsolved. The combination was {secret}.")

            else:  # boss_fight — each round is its own mini number-guessing game
                outcome, hint_message = check_guess(guess_int, secret)
                damage, is_crit, flavor = compute_boss_attack(guess_int, secret)

                st.session_state.boss_hp -= damage
                st.session_state.total_damage += damage
                st.session_state.total_attempts += 1
                st.session_state.attack_log.append({"error": abs(guess_int - secret)})
                st.session_state.last_damage = damage
                st.session_state.last_crit = is_crit

                if show_hint:
                    st.warning(f"{hint_message} {flavor}")

                if st.session_state.boss_hp <= 0:
                    st.session_state.status = "won"
                    st.session_state.score = calculate_boss_score(
                        st.session_state.total_damage, st.session_state.total_attempts, defeated=True
                    )
                    st.balloons()
                    st.success(
                        f"🐉 Boss defeated in round {st.session_state.round_number}! "
                        f"Score: {st.session_state.score}"
                    )
                elif outcome == "Win":
                    st.session_state.rounds_won += 1
                    st.session_state.round_number += 1
                    st.session_state.attempts = 0
                    st.session_state.secret = random.randint(low, high)
                    st.success(
                        f"✅ Round cleared! The boss braces itself — "
                        f"round {st.session_state.round_number} begins."
                    )
                elif st.session_state.attempts >= max_attempts:
                    st.session_state.status = "lost"
                    st.session_state.score = calculate_boss_score(
                        st.session_state.total_damage, st.session_state.total_attempts, defeated=False
                    )
                    st.error(
                        f"Out of attempts this round! The boss defeats you. "
                        f"Boss HP remaining: {max(0, st.session_state.boss_hp)} / {tier_config['max_hp']}."
                    )

        if st.session_state.status != "playing" and st.session_state.coach_review is None:
            if mode == "detective":
                stats = compute_stats(st.session_state.history, st.session_state.secret)
                stats["attempts"] = st.session_state.attempts
                stats["efficiency_pct"] = compute_efficiency(high - low, st.session_state.attempts)
            else:
                boss_stats = compute_boss_run_stats(st.session_state.attack_log)
                rounds_played = st.session_state.rounds_won + 1
                stats = {
                    "attempts": st.session_state.total_attempts,
                    "average_error": boss_stats["average_error"],
                    "best_guess": boss_stats["best_error"],
                    "efficiency_pct": compute_boss_efficiency(
                        high - low, rounds_played, st.session_state.total_attempts
                    ),
                }
            st.session_state.coach_review = generate_coach_review(stats)
elif mode == "detective":
    if st.session_state.status == "won":
        st.success("✅ Case already solved. Start a new game to try another.")
    else:
        st.error("❌ Case unsolved. Start a new game to try again.")
else:
    if st.session_state.status == "won":
        st.success("You already defeated this boss. Start a new game to fight again.")
    else:
        st.error("Boss battle over. Start a new game to try again.")

# Fill the reserved placeholders now that this run's guess (if any) has been
# fully processed, so attempts-left / HP always reflect the current state.
if mode == "detective":
    info_placeholder.info(
        f"A safe combination between {low} and {high} needs cracking. "
        f"Attempts left: {max_attempts - st.session_state.attempts}"
    )
    with clues_placeholder:
        for clue in st.session_state.clue_history:
            st.caption(f"🗂️ {clue}")
else:
    round_info_placeholder.info(
        f"Round {st.session_state.round_number} — guess a number between {low} and {high}. "
        f"Attempts left this round: {max_attempts - st.session_state.attempts}"
    )
    hp_fraction = max(0, st.session_state.boss_hp) / tier_config["max_hp"]
    hp_bar_placeholder.progress(hp_fraction)
    hp_caption_placeholder.caption(
        f"Boss HP: {max(0, st.session_state.boss_hp)} / {tier_config['max_hp']} "
        f"— Rounds cleared: {st.session_state.rounds_won}"
    )

if st.session_state.status != "playing":
    st.subheader("📊 Game Summary")
    c1, c2, c3, c4 = st.columns(4)

    if mode == "detective":
        stats = compute_stats(st.session_state.history, st.session_state.secret)
        efficiency_pct = compute_efficiency(high - low, st.session_state.attempts)
        c1.metric("Attempts", st.session_state.attempts)
        c2.metric("Average Error", f"{stats['average_error']:.1f}")
        c3.metric("Best Guess", stats["best_guess"] if stats["best_guess"] is not None else "—")
        c4.metric("Efficiency", f"{efficiency_pct}%")
    else:
        boss_stats = compute_boss_run_stats(st.session_state.attack_log)
        c1.metric("Total Attempts", st.session_state.total_attempts)
        c2.metric("Average Error", f"{boss_stats['average_error']:.1f}")
        c3.metric(
            "Closest Hit",
            boss_stats["best_error"] if boss_stats["best_error"] is not None else "—",
        )
        c4.metric("Rounds Cleared", st.session_state.rounds_won)

    if st.session_state.coach_review:
        st.info(f"**AI Coach:** {st.session_state.coach_review['text']}")

with st.expander("Developer Debug Info"):
    st.write("Mode:", mode)
    st.write("Tier:", tier)
    st.write("Secret:", st.session_state.secret)
    st.write("Status:", st.session_state.status)
    st.write("History:", st.session_state.history)
    if mode == "detective":
        st.write("Attempts:", st.session_state.attempts)
        st.write("Revealed facts:", st.session_state.revealed_fact_keys)
    else:
        st.write("Round:", st.session_state.round_number)
        st.write("Attempts this round:", st.session_state.attempts)
        st.write("Total attempts:", st.session_state.total_attempts)
        st.write("Rounds cleared:", st.session_state.rounds_won)
        st.write("Boss HP:", st.session_state.boss_hp)
        st.write("Score:", st.session_state.score)
    if st.session_state.coach_review:
        st.write("Coach review source:", st.session_state.coach_review["source"])

st.divider()
st.caption("Built with a locally-verified agentic clue engine and an AI coach — both degrade gracefully without an API key.")
