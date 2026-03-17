"""Prediction Agent for March Madness Bracket Predictor.

Synthesizes all sub-agent outputs into a weighted prediction for a single matchup.

Requirements: 8.1, 8.2, 8.3, 8.4, 13.2
"""

import logging

from strands import tool

from src.models.enums import Region, RoundName
from src.models.prediction import Prediction
from src.models.team import Team
from src.utils.seed_history import get_seed_win_rate
from src.utils.weights import redistribute_weights

logger = logging.getLogger(__name__)

# Categories that require non-empty input dicts to be considered available
_DICT_BACKED_CATEGORIES = {
    "efficiency_margin": "analytics",
    "matchup_factors": "matchup",
    "momentum_form": "team_stats",
    "location_advantage": "matchup",
    "player_injury": "players",
    "qualitative": "qualitative",
}

# seed_history and experience_pedigree are always available (computed internally)
_ALWAYS_AVAILABLE = {"seed_history", "experience_pedigree"}


def _determine_available_categories(
    team_stats: dict,
    qualitative: dict,
    analytics: dict,
    matchup: dict,
    players: dict,
) -> list[str]:
    """Return the list of categories that have data available."""
    input_map = {
        "team_stats": team_stats,
        "qualitative": qualitative,
        "analytics": analytics,
        "matchup": matchup,
        "players": players,
    }

    available = list(_ALWAYS_AVAILABLE)
    for category, input_key in _DICT_BACKED_CATEGORIES.items():
        if input_map[input_key]:
            # location_advantage and matchup_factors both depend on matchup dict
            # but are separate categories — add each only once
            if category not in available:
                available.append(category)

    return available


def _score_efficiency(team_a: str, analytics: dict) -> float:
    """Score team_a efficiency vs team_b using adj efficiency margins.

    Returns a score in [0.0, 1.0] for team_a.
    """
    a_data = analytics.get(team_a, {})
    b_data = analytics.get("team_b_analytics", {})

    # Support both keyed-by-name and keyed-by-role dicts
    if not a_data:
        return 0.5
    if not b_data:
        # Try to find the other team's data as the second key
        keys = [k for k in analytics if k != team_a]
        b_data = analytics.get(keys[0], {}) if keys else {}

    def margin(d: dict) -> float:
        off = d.get("adj_offensive_efficiency", 0.0)
        def_ = d.get("adj_defensive_efficiency", 0.0)
        return off - def_

    margin_a = margin(a_data)
    margin_b = margin(b_data)

    if margin_a == margin_b:
        return 0.5

    # Normalize to [0, 1] using a linear approach
    diff = margin_a - margin_b
    # Clamp to reasonable range (±30 points is extreme)
    clamped = max(-30.0, min(30.0, diff))
    return 0.5 + clamped / 60.0


def _score_matchup_factors(team_a: str, matchup: dict) -> float:
    """Score team_a matchup factors using seed_baseline_win_rate."""
    rate = matchup.get("seed_baseline_win_rate")
    if rate is None:
        return 0.5

    # seed_baseline_win_rate is the win rate for the lower seed number (better seed)
    # We need to know if team_a is the lower seed — use location_advantage_score as proxy
    location_scores = matchup.get("location_advantage_score", {})
    team_a_score = location_scores.get(team_a)

    # If team_a appears as the favoured team in the matchup report, use rate directly
    # Otherwise invert. Fall back to 0.5 if we can't determine.
    if team_a_score is not None:
        # The matchup report's seed_baseline_win_rate is for the lower seed number.
        # We infer team_a's role from whether their location score >= 0.5.
        # This is a heuristic; the orchestrator should pass structured data.
        return rate if team_a_score >= 0.5 else 1.0 - rate

    return 0.5


def _score_momentum(team_a: str, team_stats: dict, analytics: dict | None = None) -> float:
    """Score team_a momentum using scoring_offense and historical improvement.

    If historical improvement_score is available (from ESPN year-over-year
    comparison), it's blended with the scoring offense comparison for a
    more robust momentum signal.
    """
    a_data = team_stats.get(team_a, {})
    keys = [k for k in team_stats if k != team_a]
    b_data = team_stats.get(keys[0], {}) if keys else {}

    off_a = a_data.get("scoring_offense", 0.0)
    off_b = b_data.get("scoring_offense", 0.0)

    if abs(off_a - off_b) < 1e-9 or (off_a < 1e-9 and off_b < 1e-9):
        offense_score = 0.5
    else:
        total = off_a + off_b
        offense_score = off_a / total if total > 0 else 0.5

    # Blend with historical improvement score if available
    if analytics:
        imp_a = analytics.get(team_a, {}).get("improvement_score", 0.5) if isinstance(analytics.get(team_a), dict) else 0.5
        team_b_name = keys[0] if keys else ""
        imp_b = analytics.get(team_b_name, {}).get("improvement_score", 0.5) if isinstance(analytics.get(team_b_name), dict) else 0.5

        if imp_a != 0.5 or imp_b != 0.5:
            # Normalize improvement scores to a 0-1 scale for team_a
            imp_total = imp_a + imp_b
            improvement_score = imp_a / imp_total if imp_total > 0 else 0.5
            # Blend: 60% offense comparison, 40% improvement trend
            return 0.6 * offense_score + 0.4 * improvement_score

    return offense_score


def _score_seed_history(seed_a: int, seed_b: int) -> float:
    """Score team_a using historical seed win rates.

    Returns the win probability for team_a (the team with seed_a).
    """
    lower_seed = min(seed_a, seed_b)
    rate = get_seed_win_rate(seed_a, seed_b)  # win rate for lower seed number

    if seed_a == lower_seed:
        return rate
    return 1.0 - rate


def _score_location(team_a: str, matchup: dict) -> float:
    """Score team_a location advantage."""
    location_scores = matchup.get("location_advantage_score", {})
    score = location_scores.get(team_a)
    if score is None:
        return 0.5
    return float(score)


def _predict_total_score(
    team_a: str,
    team_b: str,
    team_stats: dict,
    analytics: dict,
) -> dict:
    """Predict the total combined final score for a Championship game.

    Uses scoring offense averages from both teams, adjusted for
    tournament context (Championship games tend to be ~5% lower scoring
    due to elite defense and slower pace).

    Returns a dict with predicted_total, team_a_score, team_b_score.
    """
    a_data = team_stats.get(team_a, {})
    b_data = {}
    for k in team_stats:
        if k != team_a:
            b_data = team_stats[k]
            break

    ppg_a = float(a_data.get("scoring_offense", 0.0))
    ppg_b = float(b_data.get("scoring_offense", 0.0))

    # If no scoring data, use a reasonable NCAA tournament average
    if ppg_a < 1.0:
        ppg_a = 72.0
    if ppg_b < 1.0:
        ppg_b = 72.0

    # Championship adjustment: ~5% lower scoring due to elite matchup
    championship_factor = 0.95
    score_a = round(ppg_a * championship_factor)
    score_b = round(ppg_b * championship_factor)

    return {
        "predicted_total": score_a + score_b,
        "team_a_predicted_score": score_a,
        "team_b_predicted_score": score_b,
        "methodology": "Based on season PPG averages with 5% championship-game adjustment",
    }


def _build_rationale(
    team_a: str,
    team_b: str,
    winner: str,
    weights: dict[str, float],
    missing_categories: list[str],
    seed_a: int,
    seed_b: int,
) -> str:
    """Build a 2+ sentence rationale string."""
    loser = team_b if winner == team_a else team_a

    # Primary sentence: overall winner reasoning
    top_cats = sorted(weights.keys(), key=lambda c: weights[c], reverse=True)[:2]
    top_labels = [c.replace("_", " ") for c in top_cats]
    sentence1 = (
        f"{winner} is predicted to defeat {loser} based on superior performance "
        f"in {top_labels[0]} and {top_labels[1]}."
    )

    # Secondary sentence: seed context
    lower_seed = min(seed_a, seed_b)
    higher_seed = max(seed_a, seed_b)
    seed_rate = get_seed_win_rate(seed_a, seed_b)
    winner_seed = seed_a if winner == team_a else seed_b
    sentence2 = (
        f"Historically, the #{lower_seed} seed defeats the #{higher_seed} seed "
        f"{seed_rate * 100:.1f}% of the time, and {winner} (#{winner_seed}) "
        f"aligns with this baseline."
    )

    rationale = f"{sentence1} {sentence2}"

    if missing_categories:
        missing_str = ", ".join(c.replace("_", " ") for c in missing_categories)
        rationale += (
            f" Note: weights were redistributed because data was unavailable for: "
            f"{missing_str}."
        )

    return rationale


def _resolve_region(region_str: str) -> Region:
    """Parse a region string to a Region enum, defaulting to EAST on failure."""
    try:
        return Region(region_str)
    except ValueError:
        logger.warning("Unrecognized region '%s'; defaulting to East", region_str)
        return Region.EAST


@tool
def predict_matchup(
    team_a: str,
    team_b: str,
    seed_a: int,
    seed_b: int,
    round_name: str,
    team_stats: dict,
    qualitative: dict,
    analytics: dict,
    matchup: dict,
    players: dict,
    region_a: str = "East",
    region_b: str = "East",
) -> dict:
    """Predict the winner of a single tournament matchup using a weighted framework.

    Applies the following weight framework (redistributed when data is missing):
      - Efficiency Margin:    25%
      - Matchup Factors:      20%
      - Momentum / Form:      15%
      - Seed History:         10%
      - Location Advantage:   10%
      - Player / Injury:      10%
      - Experience / Pedigree: 5%
      - Qualitative:           5%

    Args:
        team_a: Name of the first team.
        team_b: Name of the second team.
        seed_a: Seed number for team_a (1-16).
        seed_b: Seed number for team_b (1-16).
        round_name: Tournament round name (e.g. "Round of 64").
        team_stats: Dict of team statistics keyed by team name (may be empty).
        qualitative: Dict of qualitative research keyed by team name (may be empty).
        analytics: Dict of advanced analytics keyed by team name (may be empty).
        matchup: Dict containing matchup report data (may be empty).
        players: Dict of player/injury assessments keyed by team name (may be empty).
        region_a: Region string for team_a (e.g. "East", "West"). Defaults to "East".
        region_b: Region string for team_b (e.g. "East", "West"). Defaults to "East".

    Returns:
        Prediction serialized as a dict via Prediction.to_dict().

    Requirements: 8.1, 8.2, 8.3, 8.4, 13.2
    """
    all_categories = [
        "efficiency_margin",
        "matchup_factors",
        "momentum_form",
        "seed_history",
        "location_advantage",
        "player_injury",
        "experience_pedigree",
        "qualitative",
    ]

    available_categories = _determine_available_categories(
        team_stats, qualitative, analytics, matchup, players
    )

    missing_categories = [c for c in all_categories if c not in available_categories]

    # Get redistributed weights for available categories
    weights = redistribute_weights(available_categories)

    # Compute per-category scores for team_a (0.0 = team_b wins, 1.0 = team_a wins)
    scores: dict[str, float] = {}

    if "efficiency_margin" in available_categories:
        scores["efficiency_margin"] = _score_efficiency(team_a, analytics)

    if "matchup_factors" in available_categories:
        scores["matchup_factors"] = _score_matchup_factors(team_a, matchup)

    if "momentum_form" in available_categories:
        scores["momentum_form"] = _score_momentum(team_a, team_stats, analytics)

    # seed_history is always available
    scores["seed_history"] = _score_seed_history(seed_a, seed_b)

    if "location_advantage" in available_categories:
        scores["location_advantage"] = _score_location(team_a, matchup)

    # player_injury, experience_pedigree, qualitative default to neutral 0.5
    if "player_injury" in available_categories:
        scores["player_injury"] = 0.5

    scores["experience_pedigree"] = 0.5

    if "qualitative" in available_categories:
        scores["qualitative"] = 0.5

    # Compute weighted score for team_a
    weighted_score_a = sum(
        weights[cat] * scores[cat] for cat in available_categories if cat in scores
    )

    # Determine winner
    winner = team_a if weighted_score_a >= 0.5 else team_b

    # Confidence: scale abs deviation from 0.5 to range [50, 99]
    confidence = int(50 + abs(weighted_score_a - 0.5) * 98)
    confidence = max(50, min(99, confidence))

    # Key factors: top 3 categories by weight
    key_factors = [
        cat.replace("_", " ").title()
        for cat in sorted(available_categories, key=lambda c: weights.get(c, 0), reverse=True)[:3]
    ]

    # Build rationale (2+ sentences)
    rationale = _build_rationale(
        team_a, team_b, winner, weights, missing_categories, seed_a, seed_b
    )

    # Build Team objects for the Prediction model
    # Region is resolved from the provided region_a/region_b parameters
    team_a_obj = Team(name=team_a, seed=seed_a, region=_resolve_region(region_a))
    team_b_obj = Team(name=team_b, seed=seed_b, region=_resolve_region(region_b))

    # Resolve round name
    try:
        round_enum = RoundName(round_name)
    except ValueError:
        round_enum = RoundName.ROUND_OF_64

    # Weight adjustments to surface in output when redistribution occurred
    weight_adjustments: dict[str, float] | None = None
    if missing_categories:
        weight_adjustments = weights

    prediction = Prediction(
        team_a=team_a_obj,
        team_b=team_b_obj,
        winner=winner,
        confidence=confidence,
        rationale=rationale,
        key_factors=key_factors,
        upset_alert=False,  # recalculated in __post_init__
        round_name=round_enum,
        weight_adjustments=weight_adjustments,
    )

    result = prediction.to_dict()

    # For Championship games, predict the total combined final score
    if round_enum == RoundName.CHAMPIONSHIP:
        result["predicted_total_score"] = _predict_total_score(
            team_a, team_b, team_stats, analytics
        )

    return result
