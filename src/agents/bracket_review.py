"""Bracket Review Agent for March Madness Bracket Predictor.

Calibrates a full round of predictions against historical norms and flags
matchups that require re-evaluation before the Orchestrator finalises the round.

Review checks performed:
  1. Upset count vs historical average (5-7 for Round of 64)
  2. Confidence calibration against seed-history win rates
  3. Cinderella candidate identification (winner seed >= 11)
  4. Path analysis notes for later rounds
  5. Contradiction detection (same team winning multiple matchups in one round)

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

from strands import tool

from src.utils.seed_history import get_seed_win_rate

# Historical first-round upset range (Requirements 9.2)
_R64_UPSET_MIN = 5
_R64_UPSET_MAX = 7

# Maximum allowed deviation between actual confidence and seed-history-derived
# expected confidence before a calibration warning is raised (Requirement 9.3)
_CALIBRATION_THRESHOLD = 20


def _expected_confidence(seed_win_rate: float) -> int:
    """Convert a seed-history win rate to an expected confidence score.

    Uses the same linear mapping as the Prediction Agent:
        confidence = 50 + (win_rate - 0.5) * 98

    The result is clamped to [50, 99].
    """
    raw = 50 + (seed_win_rate - 0.5) * 98
    return max(50, min(99, int(raw)))


def _get_seed_win_rate_for_prediction(prediction: dict, seed_history: dict) -> float | None:
    """Return the seed-history win rate for the higher-seeded team in a prediction.

    Looks up the canonical key (lower_seed_vs_higher_seed) from seed_history.
    Returns None when the pairing is not present in seed_history (e.g. later
    rounds where seeds are not standard first-round pairings).
    """
    seed_a = prediction.get("team_a", {}).get("seed")
    seed_b = prediction.get("team_b", {}).get("seed")

    if seed_a is None or seed_b is None:
        return None

    lower = min(seed_a, seed_b)
    higher = max(seed_a, seed_b)
    key = f"{lower}_vs_{higher}"

    entry = seed_history.get(key)
    if entry is None:
        return None

    return float(entry.get("higher_seed_wins", 0.5))


@tool
def review_round(round_name: str, predictions: list[dict], seed_history: dict) -> dict:
    """Review a completed round of predictions and flag matchups for re-evaluation.

    Performs five calibration checks:
      1. Upset count vs historical average (5-7 for Round of 64)
      2. Confidence calibration against seed-history win rates
      3. Cinderella candidate identification (winner seed >= 11)
      4. Path analysis notes for later rounds
      5. Contradiction detection (same team winning multiple matchups)

    Args:
        round_name: Tournament round name (e.g. "Round of 64").
        predictions: List of Prediction.to_dict() results for the round.
        seed_history: Full seed history dict loaded from seed_history.json.

    Returns:
        A ReviewResult dict with keys:
          - flagged_matchups: list[dict] — predictions flagged for re-evaluation,
            each augmented with a "review_feedback" key.
          - cinderella_candidates: list[str] — winner team names with seed >= 11.
          - upset_count: int — number of upsets detected in the round.
          - review_notes: list[str] — high-level notes about the round.
          - calibration_warnings: list[str] — per-matchup calibration issues.

    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
    """
    review_notes: list[str] = []
    calibration_warnings: list[str] = []
    cinderella_candidates: list[str] = []
    flagged_matchups: list[dict] = []

    # ------------------------------------------------------------------ #
    # 1. Count upsets (Requirement 9.2)                                   #
    # ------------------------------------------------------------------ #
    upset_count = sum(1 for p in predictions if p.get("upset_alert", False))

    if round_name == "Round of 64":
        if upset_count < _R64_UPSET_MIN:
            note = (
                f"Upset count ({upset_count}) is below the historical average "
                f"of {_R64_UPSET_MIN}-{_R64_UPSET_MAX} for the Round of 64. "
                "Consider re-evaluating lower-seeded favourites."
            )
            review_notes.append(note)
        elif upset_count > _R64_UPSET_MAX:
            note = (
                f"Upset count ({upset_count}) exceeds the historical average "
                f"of {_R64_UPSET_MIN}-{_R64_UPSET_MAX} for the Round of 64. "
                "Consider re-evaluating predicted upsets."
            )
            review_notes.append(note)

    # ------------------------------------------------------------------ #
    # 2. Confidence calibration (Requirement 9.3)                         #
    # ------------------------------------------------------------------ #
    calibration_flagged_winners: set[str] = set()

    for prediction in predictions:
        winner = prediction.get("winner", "Unknown")
        actual_confidence = prediction.get("confidence", 50)

        seed_win_rate = _get_seed_win_rate_for_prediction(prediction, seed_history)
        if seed_win_rate is None:
            # Pairing not in seed_history — skip calibration for this matchup
            continue

        # Determine whether the winner is the lower-seeded (favoured) team
        seed_a = prediction.get("team_a", {}).get("seed", 0)
        seed_b = prediction.get("team_b", {}).get("seed", 0)
        team_a_name = prediction.get("team_a", {}).get("name", "")
        lower_seed = min(seed_a, seed_b)
        winner_seed = seed_a if winner == team_a_name else seed_b

        # Expected confidence is from the perspective of the predicted winner
        if winner_seed == lower_seed:
            expected = _expected_confidence(seed_win_rate)
        else:
            # Winner is the underdog — expected confidence is the upset probability
            expected = _expected_confidence(1.0 - seed_win_rate)

        deviation = abs(actual_confidence - expected)
        if deviation > _CALIBRATION_THRESHOLD:
            warning = (
                f"{winner} confidence {actual_confidence} deviates {deviation} points "
                f"from seed-history expected {expected} "
                f"(seed {winner_seed} vs seed {lower_seed if winner_seed != lower_seed else max(seed_a, seed_b)})."
            )
            calibration_warnings.append(warning)
            calibration_flagged_winners.add(winner)

    # ------------------------------------------------------------------ #
    # 3. Cinderella candidates (Requirement 9.4)                          #
    # ------------------------------------------------------------------ #
    for prediction in predictions:
        winner = prediction.get("winner", "")
        seed_a = prediction.get("team_a", {}).get("seed", 0)
        seed_b = prediction.get("team_b", {}).get("seed", 0)
        team_a_name = prediction.get("team_a", {}).get("name", "")
        winner_seed = seed_a if winner == team_a_name else seed_b

        if winner_seed >= 11 and winner not in cinderella_candidates:
            cinderella_candidates.append(winner)

    # ------------------------------------------------------------------ #
    # 4. Path analysis for later rounds (Requirement 9.5)                 #
    # ------------------------------------------------------------------ #
    if round_name != "Round of 64":
        for prediction in predictions:
            winner = prediction.get("winner", "Unknown")
            review_notes.append(
                f"Path analysis: {winner} advancing from {round_name}."
            )

    # ------------------------------------------------------------------ #
    # 5. Contradiction check (Requirement 9.6)                            #
    # ------------------------------------------------------------------ #
    winner_counts: dict[str, int] = {}
    for prediction in predictions:
        winner = prediction.get("winner", "")
        if winner:
            winner_counts[winner] = winner_counts.get(winner, 0) + 1

    contradiction_flagged_winners: set[str] = set()
    for winner, count in winner_counts.items():
        if count > 1:
            note = (
                f"Contradiction detected: {winner} appears as winner in "
                f"{count} matchups within {round_name}."
            )
            review_notes.append(note)
            contradiction_flagged_winners.add(winner)

    # ------------------------------------------------------------------ #
    # 6. Build flagged_matchups list (Requirement 9.7)                    #
    # ------------------------------------------------------------------ #
    # Determine which predictions are flagged by upset-count issues
    upset_issue = round_name == "Round of 64" and (
        upset_count < _R64_UPSET_MIN or upset_count > _R64_UPSET_MAX
    )

    for prediction in predictions:
        winner = prediction.get("winner", "")
        feedback_parts: list[str] = []

        if winner in calibration_flagged_winners:
            # Find the matching warning for this winner
            matching = [w for w in calibration_warnings if w.startswith(winner)]
            feedback_parts.extend(matching)

        if winner in contradiction_flagged_winners:
            feedback_parts.append(
                f"{winner} appears as winner in multiple matchups — verify bracket logic."
            )

        if upset_issue and prediction.get("upset_alert", False):
            feedback_parts.append(
                f"Round upset count ({upset_count}) is outside historical range "
                f"{_R64_UPSET_MIN}-{_R64_UPSET_MAX}; re-evaluate this upset pick."
            )

        if feedback_parts:
            flagged = dict(prediction)
            flagged["review_feedback"] = " | ".join(feedback_parts)
            flagged_matchups.append(flagged)

    return {
        "flagged_matchups": flagged_matchups,
        "cinderella_candidates": cinderella_candidates,
        "upset_count": upset_count,
        "review_notes": review_notes,
        "calibration_warnings": calibration_warnings,
    }
