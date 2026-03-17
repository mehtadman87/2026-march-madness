"""
NCAA Data MCP Server

Exposes get_team_stats, get_game_details, get_scoreboard, get_rankings,
and get_standings tools via FastMCP, wrapping the NCAA API at
ncaa-api.henrygd.me with rate limiting (5 req/sec).

Requirements: 11.2, 11.3, 11.4
"""

import httpx
from mcp.server.fastmcp import FastMCP

from src.utils.rate_limiter import RateLimiter

mcp = FastMCP("ncaa-data")

BASE_URL = "https://ncaa-api.henrygd.me"

# Module-level rate limiter: 5 requests per second (Requirement 11.3)
rate_limiter = RateLimiter(requests_per_second=5.0)


def _get(path: str, params: dict | None = None) -> dict:
    """
    Perform a rate-limited GET request to the NCAA API.

    Acquires a rate-limiter token before each call. Returns
    {"error": None, "data": <response_json>} on success, or
    {"error": <message>, "data": None} on any failure (Requirement 11.4).
    """
    rate_limiter.acquire()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(BASE_URL + path, params=params)
            response.raise_for_status()
            return {"error": None, "data": response.json()}
    except httpx.HTTPStatusError as exc:
        return {
            "error": f"NCAA API HTTP error {exc.response.status_code}: {exc.response.text}",
            "data": None,
        }
    except Exception as exc:
        return {"error": f"NCAA API request failed: {str(exc)}", "data": None}


@mcp.tool()
def get_team_stats(team: str, season: int) -> dict:
    """
    Get team statistics from the NCAA API.

    Args:
        team: Team name or identifier (URL-safe slug).
        season: Season year (e.g. 2025).

    Returns:
        {"error": None, "data": <stats>} on success,
        {"error": <message>, "data": None} on failure.
    """
    return _get(f"/v1/teams/{team}/stats", params={"season": season})


@mcp.tool()
def get_game_details(game_id: str) -> dict:
    """
    Get detailed information for a specific game.

    Args:
        game_id: Unique game identifier.

    Returns:
        {"error": None, "data": <game>} on success,
        {"error": <message>, "data": None} on failure.
    """
    return _get(f"/v1/games/{game_id}")


@mcp.tool()
def get_scoreboard(date: str) -> dict:
    """
    Get the scoreboard for a specific date.

    Args:
        date: Date string in YYYY-MM-DD format.

    Returns:
        {"error": None, "data": <scoreboard>} on success,
        {"error": <message>, "data": None} on failure.
    """
    return _get("/v1/scoreboard", params={"date": date})


@mcp.tool()
def get_rankings(season: int, week: int) -> dict:
    """
    Get team rankings for a given season and week.

    Args:
        season: Season year (e.g. 2025).
        week: Week number within the season.

    Returns:
        {"error": None, "data": <rankings>} on success,
        {"error": <message>, "data": None} on failure.
    """
    return _get("/v1/rankings", params={"season": season, "week": week})


@mcp.tool()
def get_standings(season: int, conference: str) -> dict:
    """
    Get conference standings for a given season.

    Args:
        season: Season year (e.g. 2025).
        conference: Conference name or identifier.

    Returns:
        {"error": None, "data": <standings>} on success,
        {"error": <message>, "data": None} on failure.
    """
    return _get("/v1/standings", params={"season": season, "conference": conference})


if __name__ == "__main__":
    mcp.run()