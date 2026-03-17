"""Structured Data Agent for March Madness Bracket Predictor.

Retrieves quantitative team statistics from multiple APIs:
- NCAA API (ncaa-api.henrygd.me) via httpx
- CBBpy (ESPN scraper)
- CBBD (CollegeBasketballData.com)

Uses TeamDataCache to avoid redundant API calls and RateLimiter to
respect API constraints.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import logging
from datetime import datetime

import httpx
from strands import tool

from src.models.agent_outputs import TeamStats
from src.utils.cache import TeamDataCache


def _current_season() -> int:
    """Return the current NCAA season year. The season spans two calendar years;
    March Madness in March 2026 is the 2025-26 season, referred to as 2026."""
    now = datetime.now()
    return now.year if now.month >= 8 else now.year
from src.utils.cbbd_client import CBBD_HTTP_Client
from src.utils.rate_limiter import MonthlyQuotaTracker, RateLimiter

logger = logging.getLogger(__name__)

# Module-level singletons shared across all calls within a CLI execution
_cache = TeamDataCache()
_quota_tracker = MonthlyQuotaTracker(monthly_limit=1000)
_rate_limiter = RateLimiter(requests_per_second=5.0)

_NCAA_API_BASE = "https://ncaa-api.henrygd.me/v1/teams"


def _fetch_ncaa_api(team_name: str) -> dict | None:
    """Fetch team stats from the NCAA API (henrygd.me).

    Enforces the 5 req/sec rate limit via the module-level RateLimiter.
    Returns the parsed JSON dict on success, or None on any error.

    Requirements: 3.2, 3.3
    """
    _rate_limiter.acquire()

    url = f"{_NCAA_API_BASE}/{team_name}/stats"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error("NCAA API error for team '%s': %s", team_name, exc)
        return None


def _fetch_cbbpy(team_name: str) -> dict | None:
    """Fetch team schedule/stats via CBBpy (ESPN scraper).

    Returns the raw schedule DataFrame converted to a list of dicts,
    or None on any error.

    Requirements: 3.2
    """
    try:
        import cbbpy.mens_scraper as cbb  # type: ignore[import]

        data = cbb.get_team_schedule(team_name)
        if data is not None and hasattr(data, "to_dict"):
            return {"schedule": data.to_dict(orient="records")}
        return None
    except Exception as exc:
        logger.error("CBBpy error for team '%s': %s", team_name, exc)
        return None


def _fetch_cbbd(team_name: str) -> dict | None:
    """Fetch team season stats from CBBD (CollegeBasketballData.com).

    Uses CBBD_HTTP_Client with direct httpx calls.
    Returns a normalized dict or None on any error.

    Requirements: 3.2, 3.4
    """
    client = CBBD_HTTP_Client()
    return client.get_team_season_stats(team_name, _current_season())


def _build_team_stats(
    team_name: str,
    ncaa_data: dict | None,
    cbbpy_data: dict | None,
    cbbd_data: dict | None,
) -> TeamStats:
    """Merge data from all available sources into a TeamStats object.

    Fields that cannot be populated from any source are set to sensible
    defaults and their names are added to ``missing_fields``.

    Requirements: 3.1, 3.6
    """
    missing_fields: list[str] = []
    data_sources: list[str] = []

    if ncaa_data:
        data_sources.append("ncaa_api")
    if cbbpy_data:
        data_sources.append("cbbpy")
    if cbbd_data:
        data_sources.append("cbbd")

    def _get(*sources_keys: tuple[dict | None, str], default=None):
        """Try each (source_dict, key) pair in order; return first hit."""
        for src, key in sources_keys:
            if src and key in src and src[key] is not None:
                return src[key]
        return default

    # --- season_record ---
    season_record = _get(
        (ncaa_data, "season_record"),
        (cbbd_data, "season_record"),
        (cbbpy_data, "season_record"),
    )
    if season_record is None:
        missing_fields.append("season_record")
        season_record = "N/A"

    # --- conference_record ---
    conference_record = _get(
        (ncaa_data, "conference_record"),
        (cbbd_data, "conference_record"),
    )
    if conference_record is None:
        missing_fields.append("conference_record")
        conference_record = "N/A"

    # --- scoring_offense ---
    scoring_offense = _get(
        (ncaa_data, "scoring_offense"),
        (cbbd_data, "points_per_game"),
        (cbbd_data, "scoring_offense"),
    )
    if scoring_offense is None:
        missing_fields.append("scoring_offense")
        scoring_offense = 0.0
    scoring_offense = float(scoring_offense)

    # --- scoring_defense ---
    scoring_defense = _get(
        (ncaa_data, "scoring_defense"),
        (cbbd_data, "opponent_points_per_game"),
        (cbbd_data, "scoring_defense"),
    )
    if scoring_defense is None:
        missing_fields.append("scoring_defense")
        scoring_defense = 0.0
    scoring_defense = float(scoring_defense)

    # --- rebounding_margin ---
    rebounding_margin = _get(
        (ncaa_data, "rebounding_margin"),
        (cbbd_data, "rebounding_margin"),
    )
    if rebounding_margin is None:
        missing_fields.append("rebounding_margin")
        rebounding_margin = 0.0
    rebounding_margin = float(rebounding_margin)

    # --- turnover_margin ---
    turnover_margin = _get(
        (ncaa_data, "turnover_margin"),
        (cbbd_data, "turnover_margin"),
    )
    if turnover_margin is None:
        missing_fields.append("turnover_margin")
        turnover_margin = 0.0
    turnover_margin = float(turnover_margin)

    # --- free_throw_pct ---
    free_throw_pct = _get(
        (ncaa_data, "free_throw_pct"),
        (cbbd_data, "free_throw_pct"),
        (cbbd_data, "ft_pct"),
    )
    if free_throw_pct is None:
        missing_fields.append("free_throw_pct")
        free_throw_pct = 0.0
    free_throw_pct = float(free_throw_pct)

    # --- three_point_pct ---
    three_point_pct = _get(
        (ncaa_data, "three_point_pct"),
        (cbbd_data, "three_point_pct"),
        (cbbd_data, "three_pt_pct"),
    )
    if three_point_pct is None:
        missing_fields.append("three_point_pct")
        three_point_pct = 0.0
    three_point_pct = float(three_point_pct)

    # --- field_goal_pct ---
    field_goal_pct = _get(
        (ncaa_data, "field_goal_pct"),
        (cbbd_data, "field_goal_pct"),
        (cbbd_data, "fg_pct"),
    )
    if field_goal_pct is None:
        missing_fields.append("field_goal_pct")
        field_goal_pct = 0.0
    field_goal_pct = float(field_goal_pct)

    # --- tournament_history ---
    tournament_history = _get(
        (ncaa_data, "tournament_history"),
        (cbbd_data, "tournament_history"),
    )
    if tournament_history is None:
        missing_fields.append("tournament_history")
        tournament_history = []

    # --- conference_tourney_result ---
    conference_tourney_result = _get(
        (ncaa_data, "conference_tourney_result"),
        (cbbd_data, "conference_tourney_result"),
    )
    if conference_tourney_result is None:
        missing_fields.append("conference_tourney_result")
        conference_tourney_result = "N/A"

    # --- strength_of_schedule ---
    strength_of_schedule = _get(
        (ncaa_data, "strength_of_schedule"),
        (cbbd_data, "strength_of_schedule"),
        (cbbd_data, "sos"),
    )
    if strength_of_schedule is None:
        missing_fields.append("strength_of_schedule")
        strength_of_schedule = 0.0
    strength_of_schedule = float(strength_of_schedule)

    # --- quadrant_record ---
    quadrant_record = _get(
        (ncaa_data, "quadrant_record"),
        (cbbd_data, "quadrant_record"),
    )
    if quadrant_record is None:
        missing_fields.append("quadrant_record")
        quadrant_record = {"Q1": "N/A", "Q2": "N/A", "Q3": "N/A", "Q4": "N/A"}

    return TeamStats(
        team_name=team_name,
        season_record=season_record,
        conference_record=conference_record,
        scoring_offense=scoring_offense,
        scoring_defense=scoring_defense,
        rebounding_margin=rebounding_margin,
        turnover_margin=turnover_margin,
        free_throw_pct=free_throw_pct,
        three_point_pct=three_point_pct,
        field_goal_pct=field_goal_pct,
        tournament_history=tournament_history,
        conference_tourney_result=conference_tourney_result,
        strength_of_schedule=strength_of_schedule,
        quadrant_record=quadrant_record,
        data_sources=data_sources,
        missing_fields=missing_fields,
    )


@tool
def get_team_data(team_name: str) -> dict:
    """Retrieve comprehensive statistics for a tournament team.

    Queries the NCAA API, CBBpy, and CBBD in sequence. If any source
    fails, the error is logged and the remaining sources are still
    attempted. Fields that could not be populated from any source are
    listed in the returned dict under ``missing_fields``.

    Results are cached by team name so that subsequent rounds do not
    trigger redundant API calls (Requirement 3.5).

    Args:
        team_name: The team name as it appears in the bracket (e.g. "Duke").

    Returns:
        A JSON-compatible dict matching the TeamStats schema.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
    """
    # Requirement 3.5 — return cached result if available
    if _cache.has(team_name, "stats"):
        logger.debug("Cache hit for team '%s' stats.", team_name)
        return _cache.get(team_name, "stats")  # type: ignore[return-value]

    logger.info("Fetching structured data for team '%s'.", team_name)

    # Requirement 3.2, 3.3 — NCAA API with rate limiting
    ncaa_data = _fetch_ncaa_api(team_name)

    # Requirement 3.2 — CBBpy
    cbbpy_data = _fetch_cbbpy(team_name)

    # Requirement 3.2, 3.4 — CBBD with monthly quota tracking
    cbbd_data = _fetch_cbbd(team_name)

    # Requirement 3.1, 3.6 — build TeamStats from whatever succeeded
    stats = _build_team_stats(team_name, ncaa_data, cbbpy_data, cbbd_data)

    if stats.missing_fields:
        logger.warning(
            "Team '%s': missing fields from all sources: %s",
            team_name,
            stats.missing_fields,
        )

    result_dict = stats.to_dict()

    # Requirement 3.5 — cache before returning
    _cache.set(team_name, "stats", result_dict)

    return result_dict
