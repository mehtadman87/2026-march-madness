"""ESPN API client for college basketball team statistics.

Uses ESPN's undocumented public API (no auth required) to fetch
current and historical season team statistics.

Endpoints:
  - Teams list: site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams
  - Team stats: site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{id}/statistics
  - Team info:  site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{id}
"""

import json as _json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"

# Lazy-loaded team name -> ESPN ID mapping
_team_id_cache: dict[str, str] | None = None

# Local cache file for team IDs (reduces API calls)
_CACHE_DIR = Path(__file__).parent.parent / "data"
_TEAM_ID_CACHE_FILE = _CACHE_DIR / "espn_team_ids.json"


def _save_team_id_cache(mapping: dict[str, str]) -> None:
    """Persist team ID mapping to a local JSON file."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _TEAM_ID_CACHE_FILE.write_text(_json.dumps(mapping, indent=2))
        logger.debug("Saved ESPN team ID cache to %s", _TEAM_ID_CACHE_FILE)
    except Exception as exc:
        logger.warning("Could not save ESPN team ID cache: %s", exc)


def _load_team_id_cache() -> dict[str, str] | None:
    """Load team ID mapping from local cache file if it exists."""
    try:
        if _TEAM_ID_CACHE_FILE.is_file():
            data = _json.loads(_TEAM_ID_CACHE_FILE.read_text())
            if isinstance(data, dict) and len(data) > 100:
                logger.debug("Loaded ESPN team ID cache from %s (%d entries)", _TEAM_ID_CACHE_FILE, len(data))
                return data
    except Exception as exc:
        logger.warning("Could not load ESPN team ID cache: %s", exc)
    return None


def _validate_espn_response(data: dict, context: str) -> bool:
    """Validate that an ESPN API response has the expected structure.

    Logs a clear warning if the schema has changed, so we catch
    ESPN API changes early rather than silently returning None.
    """
    if not isinstance(data, dict):
        logger.warning("ESPN API schema change detected (%s): expected dict, got %s", context, type(data).__name__)
        return False
    return True


def _validate_teams_response(data: dict) -> bool:
    """Validate the ESPN teams list response structure."""
    sports = data.get("sports")
    if not isinstance(sports, list) or not sports:
        logger.warning("ESPN API schema change: 'sports' key missing or empty in teams response")
        return False
    leagues = sports[0].get("leagues")
    if not isinstance(leagues, list) or not leagues:
        logger.warning("ESPN API schema change: 'leagues' key missing or empty in teams response")
        return False
    teams = leagues[0].get("teams")
    if not isinstance(teams, list):
        logger.warning("ESPN API schema change: 'teams' key missing in teams response")
        return False
    return True


def _validate_stats_response(data: dict) -> bool:
    """Validate the ESPN team stats response structure."""
    results = data.get("results")
    if not isinstance(results, dict):
        logger.warning("ESPN API schema change: 'results' key missing in stats response")
        return False
    stats = results.get("stats")
    if not isinstance(stats, dict):
        logger.warning("ESPN API schema change: 'results.stats' key missing in stats response")
        return False
    categories = stats.get("categories")
    if not isinstance(categories, list):
        logger.warning("ESPN API schema change: 'results.stats.categories' key missing in stats response")
        return False
    return True


def _load_team_ids() -> dict[str, str]:
    """Fetch all teams from ESPN and build a name -> ID lookup.

    Tries local cache first, falls back to ESPN API, then persists to cache.
    """
    global _team_id_cache
    if _team_id_cache is not None:
        return _team_id_cache

    # Try local cache first
    cached = _load_team_id_cache()
    if cached:
        _team_id_cache = cached
        return cached

    mapping: dict[str, str] = {}
    try:
        resp = httpx.get(f"{_BASE}/teams", params={"limit": 400}, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        if not _validate_espn_response(data, "teams list"):
            return mapping
        if not _validate_teams_response(data):
            return mapping

        teams = data["sports"][0]["leagues"][0]["teams"]
        for t in teams:
            team = t.get("team", {})
            tid = team.get("id", "")
            if not tid:
                continue
            # Map every name variant to the same ID
            for key in [
                team.get("displayName", ""),
                team.get("shortDisplayName", ""),
                team.get("abbreviation", ""),
                team.get("location", ""),
                team.get("name", ""),  # mascot only
            ]:
                if key:
                    mapping[key.lower()] = tid
            # Also map "Location Mascot" without "University of" etc.
            loc = team.get("location", "")
            if loc:
                mapping[loc.lower()] = tid

        logger.info("Loaded %d ESPN team name mappings (%d teams).", len(mapping), len(teams))
        # Persist to local cache
        _save_team_id_cache(mapping)
    except Exception as exc:
        logger.error("Failed to load ESPN team list: %s", exc)
        # Try local cache as last resort
        cached = _load_team_id_cache()
        if cached:
            logger.info("Using stale ESPN team ID cache after API failure.")
            mapping = cached
        else:
            mapping = {}

    _team_id_cache = mapping
    return mapping


def resolve_team_id(team_name: str) -> str | None:
    """Resolve a team name to an ESPN team ID.

    Tries exact match first, then progressively looser matching:
    1. Exact lowercase match
    2. Common bracket abbreviation lookup
    3. Match after stripping trailing periods
    4. Substring match (team_name contained in an ESPN name, min 5 chars)
    5. ESPN name contained in team_name (min 5 chars)
    """
    mapping = _load_team_ids()
    name_lower = team_name.lower().strip()

    # 1. Exact match
    if name_lower in mapping:
        return mapping[name_lower]

    # 2. Common bracket abbreviations not in ESPN's data
    _BRACKET_ABBREVS = {
        "sfla": "south florida",
        "ndakst": "north dakota state",
        "michst": "michigan state",
        "maryca": "maryland",
        "kensaw": "kennesaw state",
        "pvam/lehigh": "prairie view a&m",
        "umbc/how": "umbc",
        "texas/ncst": "texas",
        "miaoh/smu": "miami (oh)",
        "n. iowa": "northern iowa",
        "n. carolina": "north carolina",
        "iowa st.": "iowa state",
        "ohio st.": "ohio state",
        "utah st.": "utah state",
        "wright st.": "wright state",
        "tenn. state": "tennessee state",
    }
    resolved = _BRACKET_ABBREVS.get(name_lower)
    if resolved and resolved in mapping:
        return mapping[resolved]

    # 3. Strip trailing periods
    stripped = name_lower.rstrip(".")
    if stripped in mapping:
        return mapping[stripped]

    # 4. team_name is a substring of an ESPN name (require min 5 chars to avoid false matches)
    if len(name_lower) >= 5:
        for espn_name, tid in mapping.items():
            if name_lower in espn_name:
                return tid

    # 5. ESPN name is a substring of team_name (require min 5 chars)
    for espn_name, tid in mapping.items():
        if len(espn_name) >= 5 and espn_name in name_lower:
            return tid

    # 6. Fuzzy matching using Levenshtein-like similarity (no external deps)
    best_match = _fuzzy_match(name_lower, mapping)
    if best_match:
        logger.info("Fuzzy matched '%s' -> '%s' (ESPN ID %s)", team_name, best_match[0], best_match[1])
        return best_match[1]

    logger.warning("Could not resolve ESPN team ID for '%s'", team_name)
    return None


def _fuzzy_match(name: str, mapping: dict[str, str], threshold: float = 0.6) -> tuple[str, str] | None:
    """Find the best fuzzy match for a team name in the ESPN mapping.

    Uses a simple character-overlap similarity metric (Jaccard on character bigrams).
    Returns (matched_name, team_id) if similarity >= threshold, else None.
    """
    def _bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}

    name_bg = _bigrams(name)
    best_score = 0.0
    best_name = ""
    best_tid = ""

    for espn_name, tid in mapping.items():
        if len(espn_name) < 4:
            continue
        espn_bg = _bigrams(espn_name)
        intersection = len(name_bg & espn_bg)
        union = len(name_bg | espn_bg)
        score = intersection / union if union > 0 else 0.0
        if score > best_score:
            best_score = score
            best_name = espn_name
            best_tid = tid

    if best_score >= threshold:
        return (best_name, best_tid)
    return None


def get_team_info(team_name: str) -> dict[str, Any] | None:
    """Fetch basic team info (record, rank, conference) from ESPN.

    Returns a dict with keys: name, record, rank, conference, or None on error.
    """
    tid = resolve_team_id(team_name)
    if tid is None:
        return None

    try:
        resp = httpx.get(f"{_BASE}/teams/{tid}", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        team = data.get("team", {})

        record_items = team.get("record", {}).get("items", [])
        record = record_items[0].get("summary", "N/A") if record_items else "N/A"

        groups = team.get("groups", {})
        conf = ""
        if groups and groups.get("parent"):
            conf = groups["parent"].get("shortName", "")

        return {
            "name": team.get("displayName", team_name),
            "record": record,
            "rank": team.get("rank", 0),
            "conference": conf,
            "espn_id": tid,
        }
    except Exception as exc:
        logger.error("ESPN team info error for '%s': %s", team_name, exc)
        return None


def get_team_stats(team_name: str, season: int | None = None) -> dict[str, Any] | None:
    """Fetch team statistics from ESPN for a given season.

    Args:
        team_name: Team name (any variant — will be resolved to ESPN ID).
        season: Season year (e.g. 2026 for 2025-26 season). None = current season.

    Returns a normalized dict with keys matching the project's stat schema,
    or None on error.
    """
    tid = resolve_team_id(team_name)
    if tid is None:
        return None

    try:
        params: dict[str, Any] = {}
        if season is not None:
            params["season"] = season

        resp = httpx.get(f"{_BASE}/teams/{tid}/statistics", params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        if not _validate_espn_response(data, f"stats for {team_name}"):
            return None
        if not _validate_stats_response(data):
            return None

        categories = data["results"]["stats"]["categories"]
        if not categories:
            logger.warning("ESPN returned no stat categories for '%s'", team_name)
            return None

        # Flatten stats — prefer per-game averages over totals.
        # ESPN uses the same abbreviation for both (e.g. "PTS" for total and PPG).
        # Per-game stats have "Per Game" or "Average" in their displayName.
        stats_total: dict[str, float] = {}
        stats_avg: dict[str, float] = {}
        for cat in categories:
            for s in cat.get("stats", []):
                abbr = s.get("abbreviation", "")
                display = s.get("displayName", "")
                try:
                    val = float(s.get("value", 0.0))
                except (TypeError, ValueError):
                    continue
                if "per game" in display.lower() or "average" in display.lower() or "percentage" in display.lower() or "ratio" in display.lower() or "%" in abbr:
                    stats_avg[abbr] = val
                else:
                    stats_total[abbr] = val

        # Use per-game averages where available, fall back to totals
        def _stat(abbr: str) -> float:
            return stats_avg.get(abbr, stats_total.get(abbr, 0.0))

        # Also get team info for record
        info = get_team_info(team_name)
        record = info.get("record", "N/A") if info else "N/A"

        return {
            # Structured data keys (per-game averages)
            "season_record": record,
            "scoring_offense": _stat("PTS"),
            "scoring_defense": 0.0,  # ESPN doesn't expose opponent PPG directly
            "field_goal_pct": _stat("FG%"),
            "three_point_pct": _stat("3P%"),
            "free_throw_pct": _stat("FT%"),
            "rebounds_per_game": _stat("REB"),
            "assists_per_game": _stat("AST"),
            "turnovers_per_game": _stat("TO"),
            "steals_per_game": _stat("STL"),
            "blocks_per_game": _stat("BLK"),
            "offensive_rebounds_per_game": _stat("OR"),
            "defensive_rebounds_per_game": _stat("DR"),
            "assist_turnover_ratio": _stat("AST/TO"),
            "two_point_pct": _stat("2P%"),
            # Source metadata
            "data_source": "espn",
            "espn_id": tid,
        }
    except Exception as exc:
        logger.error("ESPN stats error for '%s' (season=%s): %s", team_name, season, exc)
        return None
