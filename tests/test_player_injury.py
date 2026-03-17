"""
Unit and property-based tests for player_injury agent.

Requirements: 3.2, 3.3, 3.4, 3.5
"""

import sys
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# conftest.py registers strands with an identity @tool decorator and stubs
# cbbpy. We only need to ensure the real player_injury module is loaded.
sys.modules.pop("src.agents.player_injury", None)

# cbbpy mock is registered by conftest.py; grab the scraper mock so patch()
# targets the same object that _fetch_cbbpy_player_stats imports.
_mock_cbbpy_scraper = sys.modules.get("cbbpy.mens_scraper", MagicMock())

from src.agents.player_injury import _fetch_cbbpy_player_stats, assess_players  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_schedule_df(completed=True):
    """Return a minimal schedule DataFrame with one completed game."""
    result = "W" if completed else "P"
    return pd.DataFrame([{"game_id": "12345", "game_result": result}])


def _make_boxscore_df(rows):
    """Return a boxscore DataFrame from a list of row dicts."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_fetch_cbbpy_player_stats_returns_real_names():
    """
    Mock CBBpy returning a DataFrame with 2 players.
    Verify name != 'Unknown Player 1' and stats != 0.0.

    Requirements: 3.2, 3.3
    """
    schedule_df = _make_schedule_df(completed=True)
    boxscore_df = _make_boxscore_df([
        {"player_name": "Alice Smith", "pts": 22.0, "reb": 8.0, "ast": 3.0, "usg_pct": 0.28},
        {"player_name": "Bob Jones",  "pts": 15.0, "reb": 5.0, "ast": 6.0, "usg_pct": 0.22},
    ])

    with patch("cbbpy.mens_scraper.get_team_schedule", return_value=schedule_df), \
         patch("cbbpy.mens_scraper.get_game_boxscore", return_value=boxscore_df):
        result = _fetch_cbbpy_player_stats("Duke")

    assert result is not None
    assert len(result) == 2
    names = [p["name"] for p in result]
    assert "Unknown Player 1" not in names
    assert "Alice Smith" in names
    assert "Bob Jones" in names
    # Stats should be non-zero
    alice = next(p for p in result if p["name"] == "Alice Smith")
    assert alice["ppg"] == 22.0
    assert alice["rpg"] == 8.0
    assert alice["apg"] == 3.0


def test_fetch_cbbpy_player_stats_empty_schedule_returns_none():
    """
    Mock get_team_schedule returning an empty DataFrame.
    Verify None is returned.

    Requirements: 3.4
    """
    empty_df = pd.DataFrame()

    with patch("cbbpy.mens_scraper.get_team_schedule", return_value=empty_df):
        result = _fetch_cbbpy_player_stats("Duke")

    assert result is None


def test_fetch_cbbpy_player_stats_exception_returns_none():
    """
    Mock get_team_schedule raising an Exception.
    Verify None is returned.

    Requirements: 3.4
    """
    with patch("cbbpy.mens_scraper.get_team_schedule", side_effect=Exception("network error")):
        result = _fetch_cbbpy_player_stats("Duke")

    assert result is None


def test_assess_players_tier3_fallback():
    """
    Mock _fetch_cbbpy_player_stats returning None AND mock search_web returning
    empty list. Verify injury_impact_summary == 'Player data unavailable from all sources'.

    Requirements: 3.5
    """
    with patch("src.agents.player_injury._fetch_cbbpy_player_stats", return_value=None), \
         patch("src.agents.player_injury.search_web", return_value=[]):
        result = assess_players("Duke")

    assert result["injury_impact_summary"] == "Player data unavailable from all sources"


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------


@given(
    st.lists(
        st.fixed_dictionaries({
            "player_name": st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            ),
            "pts": st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            "reb": st.floats(min_value=0.0, max_value=25.0, allow_nan=False),
            "ast": st.floats(min_value=0.0, max_value=20.0, allow_nan=False),
            "usg_pct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        }),
        min_size=1,
        max_size=4,
    )
)
@settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
def test_property_player_info_populated_from_cbbpy_data(player_rows):
    """
    Property 5: PlayerInfo fields populated from CBBpy data.

    For any CBBpy response containing at least one player row with a non-empty
    name, the resulting player dicts SHALL have:
    - name not equal to "Unknown Player N" pattern
    - ppg, rpg, apg equal to the values in the generated rows

    Validates: Requirements 3.2, 3.3
    """
    schedule_df = _make_schedule_df(completed=True)
    boxscore_df = _make_boxscore_df(player_rows)

    with patch("cbbpy.mens_scraper.get_team_schedule", return_value=schedule_df), \
         patch("cbbpy.mens_scraper.get_game_boxscore", return_value=boxscore_df):
        result = _fetch_cbbpy_player_stats("Duke")

    assert result is not None, "Expected player list, got None"

    # Build a lookup from the generated rows (sorted by pts desc, top 4)
    sorted_rows = sorted(player_rows, key=lambda r: r["pts"], reverse=True)[:4]

    for i, player in enumerate(result):
        expected_row = sorted_rows[i]

        # Name must come from the data, not be a placeholder
        assert not player["name"].startswith("Unknown Player"), (
            f"Player name '{player['name']}' looks like a placeholder"
        )
        assert player["name"] == expected_row["player_name"]

        # Stats must match the generated row values
        assert player["ppg"] == pytest.approx(expected_row["pts"])
        assert player["rpg"] == pytest.approx(expected_row["reb"])
        assert player["apg"] == pytest.approx(expected_row["ast"])
