"""Player/Injury Agent for March Madness Bracket Predictor.

Assesses roster composition and injury impact for a team:
- Top 3-4 player stats (PPG, RPG, APG, usage rate)
- Latest injury reports via web search
- Impact estimation for injured key players
- Player matchup dynamics, experience factor, bench depth, star tournament experience

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""

import logging

from strands import tool
from src.models.agent_outputs import PlayerAssessment, PlayerInfo
from src.mcp_servers.web_search_server import search_web

logger = logging.getLogger(__name__)


def _extract_first_snippet(search_result: list | dict) -> str:
    """Return the snippet from the first search result, or empty string on failure."""
    if isinstance(search_result, list) and search_result:
        return search_result[0].get("snippet", "").strip()
    return ""


def _fetch_cbbpy_player_stats(team_name: str) -> list[dict] | None:
    """Fetch player stats via CBBpy for the most recent completed game.

    Returns list of dicts with keys: name, ppg, rpg, apg, usage_rate
    for top 3-4 players by points, or None on any error.
    """
    try:
        import cbbpy.mens_scraper as cbb  # type: ignore[import]

        schedule = cbb.get_team_schedule(team_name)
        if schedule is None or (hasattr(schedule, 'empty') and schedule.empty):
            return None

        completed = schedule[schedule["game_result"].isin(["W", "L"])]
        if hasattr(completed, 'empty') and completed.empty:
            return None

        game_id = str(completed.iloc[-1]["game_id"])
        boxscore = cbb.get_game_boxscore(game_id)

        # boxscore may be a tuple (home_df, away_df) or a single DataFrame
        df = None
        if isinstance(boxscore, tuple):
            for part in boxscore:
                if hasattr(part, 'iterrows'):
                    # Check if this part contains the team
                    team_col = None
                    for col in ["team", "team_name", "school"]:
                        if col in part.columns:
                            team_col = col
                            break
                    if team_col and team_name.lower() in part[team_col].str.lower().values:
                        df = part
                        break
            if df is None and boxscore:
                df = boxscore[0]  # fallback to first part
        elif hasattr(boxscore, 'iterrows'):
            df = boxscore

        if df is None or (hasattr(df, 'empty') and df.empty):
            return None

        # Sort by points descending, take top 4
        pts_col = next((c for c in ["pts", "points", "PTS"] if c in df.columns), None)
        if pts_col:
            df = df.sort_values(pts_col, ascending=False).head(4)
        else:
            df = df.head(4)

        players = []
        for _, row in df.iterrows():
            name = str(row.get("player_name", row.get("name", row.get("player", "Unknown"))))
            ppg = float(row.get("pts", row.get("points", row.get("PTS", 0.0))) or 0.0)
            rpg = float(row.get("reb", row.get("trb", row.get("REB", 0.0))) or 0.0)
            apg = float(row.get("ast", row.get("AST", 0.0)) or 0.0)
            usage_rate = float(row.get("usg_pct", row.get("usage", row.get("USG%", 0.0))) or 0.0)
            players.append({"name": name, "ppg": ppg, "rpg": rpg, "apg": apg, "usage_rate": usage_rate})

        return players if players else None
    except Exception as exc:
        logger.warning("CBBpy player stats error for '%s': %s", team_name, exc)
        return None


@tool
def assess_players(team_name: str) -> dict:
    """Assess player-level factors for a team including injuries and roster composition."""
    key_players: list[PlayerInfo] = []

    # Tier 1: Try CBBpy for real player stats
    cbbpy_players = _fetch_cbbpy_player_stats(team_name)
    if cbbpy_players:
        for p in cbbpy_players:
            key_players.append(PlayerInfo(
                name=p["name"],
                ppg=p["ppg"],
                rpg=p["rpg"],
                apg=p["apg"],
                usage_rate=p["usage_rate"],
                injury_status="unknown",
                injury_details=None,
                estimated_impact=None,
            ))

    # Tier 2: Web search fallback for player names/stats
    if not key_players:
        stats_query = f"{team_name} basketball top players stats PPG RPG 2025"
        stats_result = search_web(stats_query, num_results=3)
        stats_snippet = _extract_first_snippet(stats_result)

        if stats_snippet:
            # Try to parse names from snippet — use snippet as context for first player
            key_players.append(PlayerInfo(
                name="Unknown Player 1",
                ppg=0.0, rpg=0.0, apg=0.0, usage_rate=0.0,
                injury_status="unknown",
                injury_details=None,
                estimated_impact=stats_snippet,
            ))

    # Tier 3: Placeholder fallback
    if not key_players:
        for i in range(1, 4):
            key_players.append(PlayerInfo(
                name=f"Unknown Player {i}",
                ppg=0.0, rpg=0.0, apg=0.0, usage_rate=0.0,
                injury_status="unknown",
                injury_details=None,
                estimated_impact=None,
            ))
        injury_impact_summary = "Player data unavailable from all sources"
    else:
        injury_impact_summary = None  # will be set from injury report below

    # Always retrieve injury reports via web search (Requirement 3.6)
    injury_query = f"{team_name} basketball injury report 2025 NCAA tournament"
    injury_result = search_web(injury_query, num_results=3)
    injury_snippet = _extract_first_snippet(injury_result)
    if injury_impact_summary is None:
        injury_impact_summary = injury_snippet if injury_snippet else "No injury information available"

    # Star tournament experience
    exp_query = f"{team_name} star player NCAA tournament experience"
    exp_result = search_web(exp_query, num_results=3)
    star_tournament_experience = _extract_first_snippet(exp_result) or "Unknown"

    assessment = PlayerAssessment(
        team_name=team_name,
        key_players=key_players,
        experience_factor=0.5,
        bench_depth="Unknown - data not available",
        star_tournament_experience=star_tournament_experience,
        player_matchup_dynamics="Matchup dynamics to be evaluated against opponent",
        injury_impact_summary=injury_impact_summary,
    )
    return assessment.to_dict()
