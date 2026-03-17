"""Direct httpx client for api.collegebasketballdata.com.

Replaces the cbbd Python package to eliminate the pydantic<2 conflict.
All methods return a normalized dict or None on any error.

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import logging
import os

import httpx

_CBBD_BASE = "https://api.collegebasketballdata.com"
logger = logging.getLogger(__name__)


class CBBD_HTTP_Client:
    """Direct httpx client for api.collegebasketballdata.com."""

    def __init__(self) -> None:
        self._api_key = os.environ.get("CBBD_API_KEY", "")
        self._headers = {"Authorization": f"Bearer {self._api_key}"}

    def get_adjusted_ratings(self, team: str, season: int) -> dict | None:
        """GET /ratings/adjusted — returns normalized dict with adj_off_efficiency, adj_def_efficiency, net_ranking or None."""
        try:
            resp = httpx.get(
                f"{_CBBD_BASE}/ratings/adjusted",
                params={"team": team, "season": season},
                headers=self._headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            if "application/json" not in resp.headers.get("content-type", ""):
                logger.error("CBBD ratings non-JSON response for '%s'", team)
                return None
            data = resp.json()
            if not data:
                return None
            item = data[0]
            return {
                "adj_off_efficiency": item.get("offensiveRating", 0.0),
                "adj_def_efficiency": item.get("defensiveRating", 0.0),
                "net_ranking": item.get("rankings", {}).get("net", 0),
            }
        except httpx.HTTPStatusError as exc:
            logger.error(
                "CBBD ratings HTTP %s for '%s': %s", exc.response.status_code, team, exc
            )
            return None
        except Exception as exc:
            logger.error("CBBD ratings error for '%s': %s", team, exc)
            return None

    def get_team_season_stats(self, team: str, season: int) -> dict | None:
        """GET /stats/teams/season — returns normalized dict with all required keys or None."""
        try:
            resp = httpx.get(
                f"{_CBBD_BASE}/stats/teams/season",
                params={"team": team, "season": season},
                headers=self._headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            if "application/json" not in resp.headers.get("content-type", ""):
                logger.error("CBBD stats non-JSON response for '%s'", team)
                return None
            data = resp.json()
            if not data:
                return None
            item = data[0]
            ts = item.get("teamStats", {})
            os_ = item.get("opponentStats", {})
            ff = ts.get("fourFactors", {})
            fg = ts.get("fieldGoals", {})
            tp = ts.get("threePointFieldGoals", {})
            ft = ts.get("freeThrows", {})
            opp_tp = os_.get("threePointFieldGoals", {})
            pts = ts.get("points", {})
            opp_pts = os_.get("points", {})
            games = item.get("games", 1) or 1
            return {
                # advanced_analytics keys (stats endpoint only)
                "tempo": item.get("pace", 0.0),
                "efg_pct": ff.get("effectiveFieldGoalPct", 0.0),
                "tov_rate": ff.get("turnoverRatio", 0.0),
                "orb_pct": ff.get("offensiveReboundPct", 0.0),
                "ftr": ff.get("freeThrowRate", 0.0),
                "three_pt_pct": tp.get("pct", 0.0),
                "opp_3p_pct": opp_tp.get("pct", 0.0),
                # structured_data keys
                "scoring_offense": pts.get("total", 0.0) / games,
                "scoring_defense": opp_pts.get("total", 0.0) / games,
                "field_goal_pct": fg.get("pct", 0.0),
                "free_throw_pct": ft.get("pct", 0.0),
                "three_point_pct": tp.get("pct", 0.0),
                "effective_fg_pct": ff.get("effectiveFieldGoalPct", 0.0),
                "turnover_ratio": ff.get("turnoverRatio", 0.0),
                "offensive_rebound_pct": ff.get("offensiveReboundPct", 0.0),
                "free_throw_rate": ff.get("freeThrowRate", 0.0),
                "pace": item.get("pace", 0.0),
                "season_record": f"{item.get('wins', 0)}-{item.get('losses', 0)}",
                # NOTE: adj_off_efficiency, adj_def_efficiency, net_ranking are
                # NOT included here — they come from get_adjusted_ratings().
                # advanced_analytics.py merges both calls before using the data.
            }
        except httpx.HTTPStatusError as exc:
            logger.error(
                "CBBD stats HTTP %s for '%s': %s", exc.response.status_code, team, exc
            )
            return None
        except Exception as exc:
            logger.error("CBBD stats error for '%s': %s", team, exc)
            return None
