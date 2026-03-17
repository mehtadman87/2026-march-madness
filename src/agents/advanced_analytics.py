"""Advanced Analytics Agent for March Madness Bracket Predictor.

Retrieves and computes tempo-free efficiency metrics for tournament teams:
- CBBD (CollegeBasketballData.com) for adjusted efficiency and NET rankings
- BartTorvik for tempo-free stats
- CBBpy box scores for computed metrics

Uses TeamDataCache to avoid redundant API calls.

Validates: Requirements 5.1, 5.2, 5.3
"""

import logging
from datetime import datetime

import httpx
from strands import tool

from src.models.agent_outputs import AdvancedMetrics
from src.utils.cache import TeamDataCache
from src.utils.cbbd_client import CBBD_HTTP_Client


def _current_season() -> int:
    """Return the current NCAA season year."""
    now = datetime.now()
    return now.year if now.month >= 8 else now.year

logger = logging.getLogger(__name__)

# Module-level cache singleton shared across all calls within a CLI execution
_cache = TeamDataCache()

_BARTTORVIK_URL = "https://barttorvik.com/getteam.php"


def _fetch_cbbd(team_name: str) -> dict | None:
    """Fetch advanced stats from CBBD using CBBD_HTTP_Client.

    Calls get_adjusted_ratings and get_team_season_stats, merging results.
    Returns a normalized dict or None if both calls fail.

    Requirements: 5.2
    """
    client = CBBD_HTTP_Client()
    result: dict = {}

    ratings = client.get_adjusted_ratings(team_name, _current_season())
    if ratings:
        result.update(ratings)

    stats = client.get_team_season_stats(team_name, _current_season())
    if stats:
        result.update(stats)

    return result if result else None


def _fetch_barttorvik(team_name: str) -> dict | None:
    """Fetch tempo-free stats from BartTorvik.

    GETs https://barttorvik.com/getteam.php?team={team_name}&year=2025&json=1
    Returns the parsed JSON dict on success, or None on any error.

    Requirements: 5.2
    """
    try:
        params = {"team": team_name, "year": "2025", "json": "1"}
        response = httpx.get(_BARTTORVIK_URL, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error("BartTorvik error for team '%s': %s", team_name, exc)
        return None


def _fetch_cbbpy(team_name: str) -> dict | None:
    """Fetch team schedule/box scores via CBBpy (ESPN scraper).

    Returns a dict with a 'schedule' key containing a list of game records,
    or None on any error.

    Requirements: 5.2
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


def _compute_last_10_trend(schedule: list[dict]) -> str:
    """Derive last-10-games record from a list of game dicts."""
    completed = [g for g in schedule if g.get("game_result") in ("W", "L")]
    last_10 = completed[-10:]
    if not last_10:
        return "N/A"
    wins = sum(1 for g in last_10 if g.get("game_result") == "W")
    return f"{wins}-{len(last_10) - wins}"


def _compute_close_game_record(schedule: list[dict]) -> str:
    """Derive record in games decided by 5 or fewer points."""
    close = [
        g
        for g in schedule
        if g.get("game_result") in ("W", "L")
        and abs(
            (g.get("team_score") or 0) - (g.get("opponent_score") or 0)
        ) <= 5
    ]
    if not close:
        return "N/A"
    wins = sum(1 for g in close if g.get("game_result") == "W")
    return f"{wins}-{len(close) - wins}"


def _build_advanced_metrics(
    team_name: str,
    cbbd_data: dict | None,
    torvik_data: dict | None,
    cbbpy_data: dict | None,
) -> AdvancedMetrics:
    """Merge data from all available sources into an AdvancedMetrics object.

    Fields that cannot be populated from any source default to 0.0 (numeric)
    or "N/A" (string). Each metric records which source provided it.

    Requirements: 5.1, 5.3
    """
    data_sources: dict[str, str] = {}

    def _pick(metric: str, candidates: list[tuple[dict | None, str, str]]) -> float:
        """Return the first non-None numeric value from (source_dict, key, source_label)."""
        for src, key, label in candidates:
            if src and key in src and src[key] is not None:
                try:
                    val = float(src[key])
                    data_sources[metric] = label
                    return val
                except (TypeError, ValueError):
                    continue
        return 0.0

    def _pick_int(metric: str, candidates: list[tuple[dict | None, str, str]]) -> int:
        """Return the first non-None integer value from (source_dict, key, source_label)."""
        for src, key, label in candidates:
            if src and key in src and src[key] is not None:
                try:
                    val = int(src[key])
                    data_sources[metric] = label
                    return val
                except (TypeError, ValueError):
                    continue
        return 0

    # --- Adjusted Offensive Efficiency ---
    adj_off = _pick(
        "adj_offensive_efficiency",
        [
            (cbbd_data, "adj_off_efficiency", "cbbd"),
            (cbbd_data, "adj_oe", "cbbd"),
            (torvik_data, "adjoe", "barttorvik"),
            (torvik_data, "adj_off", "barttorvik"),
        ],
    )

    # --- Adjusted Defensive Efficiency ---
    adj_def = _pick(
        "adj_defensive_efficiency",
        [
            (cbbd_data, "adj_def_efficiency", "cbbd"),
            (cbbd_data, "adj_de", "cbbd"),
            (torvik_data, "adjde", "barttorvik"),
            (torvik_data, "adj_def", "barttorvik"),
        ],
    )

    # --- NET Ranking ---
    net_ranking = _pick_int(
        "net_ranking",
        [
            (cbbd_data, "net_ranking", "cbbd"),
            (cbbd_data, "net", "cbbd"),
            (torvik_data, "net_ranking", "barttorvik"),
        ],
    )

    # --- Tempo ---
    tempo = _pick(
        "tempo",
        [
            (cbbd_data, "tempo", "cbbd"),
            (cbbd_data, "adj_tempo", "cbbd"),
            (torvik_data, "tempo", "barttorvik"),
            (torvik_data, "adj_tempo", "barttorvik"),
        ],
    )

    # --- Effective FG% ---
    effective_fg_pct = _pick(
        "effective_fg_pct",
        [
            (cbbd_data, "effective_fg_pct", "cbbd"),
            (cbbd_data, "efg_pct", "cbbd"),
            (torvik_data, "efg_pct", "barttorvik"),
            (torvik_data, "efg", "barttorvik"),
        ],
    )

    # --- Turnover Rate ---
    turnover_rate = _pick(
        "turnover_rate",
        [
            (cbbd_data, "turnover_rate", "cbbd"),
            (cbbd_data, "to_rate", "cbbd"),
            (torvik_data, "tov_rate", "barttorvik"),
            (torvik_data, "to_pct", "barttorvik"),
        ],
    )

    # --- Offensive Rebounding % ---
    offensive_rebound_pct = _pick(
        "offensive_rebound_pct",
        [
            (cbbd_data, "offensive_rebound_pct", "cbbd"),
            (cbbd_data, "orb_pct", "cbbd"),
            (torvik_data, "orb_pct", "barttorvik"),
            (torvik_data, "or_pct", "barttorvik"),
        ],
    )

    # --- Free Throw Rate ---
    free_throw_rate = _pick(
        "free_throw_rate",
        [
            (cbbd_data, "free_throw_rate", "cbbd"),
            (cbbd_data, "ft_rate", "cbbd"),
            (torvik_data, "ft_rate", "barttorvik"),
            (torvik_data, "ftr", "barttorvik"),
        ],
    )

    # --- 3PT% ---
    three_point_pct = _pick(
        "three_point_pct",
        [
            (cbbd_data, "three_point_pct", "cbbd"),
            (cbbd_data, "three_pt_pct", "cbbd"),
            (torvik_data, "three_pt_pct", "barttorvik"),
            (torvik_data, "3p_pct", "barttorvik"),
        ],
    )

    # --- 3PT Defense% ---
    three_point_defense_pct = _pick(
        "three_point_defense_pct",
        [
            (cbbd_data, "three_point_defense_pct", "cbbd"),
            (cbbd_data, "opp_three_pt_pct", "cbbd"),
            (torvik_data, "opp_3p_pct", "barttorvik"),
            (torvik_data, "three_pt_def_pct", "barttorvik"),
        ],
    )

    # --- Close Game Record and Last 10 Trend (from CBBpy box scores) ---
    close_game_record = "N/A"
    last_10_trend = "N/A"

    if cbbpy_data and "schedule" in cbbpy_data:
        schedule = cbbpy_data["schedule"]
        close_game_record = _compute_close_game_record(schedule)
        last_10_trend = _compute_last_10_trend(schedule)
        if close_game_record != "N/A":
            data_sources["close_game_record"] = "cbbpy"
        if last_10_trend != "N/A":
            data_sources["last_10_trend"] = "cbbpy"

    # Fall back to CBBD/BartTorvik string fields if CBBpy didn't provide them
    if close_game_record == "N/A":
        for src, key, label in [
            (cbbd_data, "close_game_record", "cbbd"),
            (torvik_data, "close_game_record", "barttorvik"),
        ]:
            if src and key in src and src[key] is not None:
                close_game_record = str(src[key])
                data_sources["close_game_record"] = label
                break

    if last_10_trend == "N/A":
        for src, key, label in [
            (cbbd_data, "last_10_trend", "cbbd"),
            (torvik_data, "last_10_trend", "barttorvik"),
        ]:
            if src and key in src and src[key] is not None:
                last_10_trend = str(src[key])
                data_sources["last_10_trend"] = label
                break

    return AdvancedMetrics(
        team_name=team_name,
        adj_offensive_efficiency=adj_off,
        adj_defensive_efficiency=adj_def,
        net_ranking=net_ranking,
        tempo=tempo,
        effective_fg_pct=effective_fg_pct,
        turnover_rate=turnover_rate,
        offensive_rebound_pct=offensive_rebound_pct,
        free_throw_rate=free_throw_rate,
        three_point_pct=three_point_pct,
        three_point_defense_pct=three_point_defense_pct,
        close_game_record=close_game_record,
        last_10_trend=last_10_trend,
        data_sources=data_sources,
    )


@tool
def get_advanced_analytics(team_name: str) -> dict:
    """Retrieve advanced tempo-free efficiency metrics for a tournament team.

    Queries CBBD, BartTorvik, and CBBpy box scores in sequence. If any
    source fails, the error is logged and the remaining sources are still
    attempted. Numeric fields that could not be populated from any source
    default to 0.0; string fields default to "N/A".

    Each metric in the returned dict includes a ``data_sources`` mapping
    that records which source provided each value (Requirement 5.3).

    Results are cached by team name so that subsequent rounds do not
    trigger redundant API calls.

    Args:
        team_name: The team name as it appears in the bracket (e.g. "Duke").

    Returns:
        A JSON-compatible dict matching the AdvancedMetrics schema.

    Validates: Requirements 5.1, 5.2, 5.3
    """
    # Return cached result if available
    if _cache.has(team_name, "analytics"):
        logger.debug("Cache hit for team '%s' analytics.", team_name)
        return _cache.get(team_name, "analytics")  # type: ignore[return-value]

    logger.info("Fetching advanced analytics for team '%s'.", team_name)

    # Requirement 5.2 — try each source, log errors and continue
    cbbd_data = _fetch_cbbd(team_name)
    torvik_data = _fetch_barttorvik(team_name)
    cbbpy_data = _fetch_cbbpy(team_name)

    # Requirement 5.1, 5.3 — build AdvancedMetrics from whatever succeeded
    metrics = _build_advanced_metrics(team_name, cbbd_data, torvik_data, cbbpy_data)

    result_dict = metrics.to_dict()

    # Cache before returning
    _cache.set(team_name, "analytics", result_dict)

    return result_dict
