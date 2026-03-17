"""Historical Stats Agent for March Madness Bracket Predictor.

Fetches previous season statistics from ESPN to provide year-over-year
trend analysis. Compares current season performance against the prior
season to identify improving/declining teams.

Uses the ESPN public API (no auth required).
"""

import logging
from datetime import datetime

from strands import tool

from src.utils.cache import TeamDataCache
from src.utils.espn_client import get_team_stats, get_team_info

logger = logging.getLogger(__name__)

_cache = TeamDataCache()


def _current_season_year() -> int:
    """Return the ESPN season year for the current season."""
    now = datetime.now()
    return now.year if now.month >= 8 else now.year


def _previous_season_year() -> int:
    """Return the ESPN season year for the previous season."""
    return _current_season_year() - 1


def _compute_trend(current: float, previous: float) -> str:
    """Return a trend indicator comparing current to previous value."""
    if previous == 0.0:
        return "N/A"
    pct_change = ((current - previous) / abs(previous)) * 100
    if pct_change > 5:
        return f"↑ +{pct_change:.1f}%"
    elif pct_change < -5:
        return f"↓ {pct_change:.1f}%"
    return f"→ {pct_change:+.1f}%"


@tool
def get_historical_comparison(team_name: str) -> dict:
    """Fetch current and previous season stats from ESPN and compute trends.

    Returns a dict with:
      - current_season: dict of current season stats
      - previous_season: dict of previous season stats
      - trends: dict of stat name -> trend string (↑/↓/→)
      - improvement_score: float 0-1 indicating overall improvement
      - data_source: "espn"

    Falls back gracefully if either season's data is unavailable.
    """
    # Check cache
    if _cache.has(team_name, "historical"):
        logger.debug("Cache hit for team '%s' historical.", team_name)
        return _cache.get(team_name, "historical")

    logger.info("Fetching historical comparison for team '%s'.", team_name)

    current_year = _current_season_year()
    previous_year = _previous_season_year()

    current = get_team_stats(team_name, season=current_year)
    previous = get_team_stats(team_name, season=previous_year)
    info = get_team_info(team_name)

    # Compute trends for key metrics
    trends: dict[str, str] = {}
    trend_metrics = [
        "scoring_offense", "field_goal_pct", "three_point_pct",
        "free_throw_pct", "rebounds_per_game", "assists_per_game",
        "turnovers_per_game", "assist_turnover_ratio",
    ]

    positive_trends = 0
    total_trends = 0

    if current and previous:
        for metric in trend_metrics:
            curr_val = current.get(metric, 0.0)
            prev_val = previous.get(metric, 0.0)
            # For turnovers, lower is better
            if metric == "turnovers_per_game":
                trend = _compute_trend(-curr_val, -prev_val)
            else:
                trend = _compute_trend(curr_val, prev_val)
            trends[metric] = trend
            if prev_val != 0.0:
                total_trends += 1
                if "↑" in trend:
                    positive_trends += 1

    improvement_score = positive_trends / total_trends if total_trends > 0 else 0.5

    result = {
        "team_name": team_name,
        "current_season": current or {},
        "previous_season": previous or {},
        "current_season_year": current_year,
        "previous_season_year": previous_year,
        "trends": trends,
        "improvement_score": round(improvement_score, 3),
        "team_info": info or {},
        "data_source": "espn",
        "data_available": bool(current or previous),
    }

    _cache.set(team_name, "historical", result)
    return result
