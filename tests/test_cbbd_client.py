"""
Unit and property-based tests for CBBD_HTTP_Client.

Requirements: 2.3, 2.4, 2.8
"""

import httpx
import pytest
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from src.utils.cbbd_client import CBBD_HTTP_Client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "adj_off_efficiency",
    "adj_def_efficiency",
    "net_ranking",
    "tempo",
    "efg_pct",
    "tov_rate",
    "orb_pct",
    "ftr",
    "three_pt_pct",
    "opp_3p_pct",
}

# Keys returned by get_team_season_stats() only (no efficiency/ratings keys)
STATS_ENDPOINT_KEYS = {
    "tempo",
    "efg_pct",
    "tov_rate",
    "orb_pct",
    "ftr",
    "three_pt_pct",
    "opp_3p_pct",
}

# Keys returned by get_adjusted_ratings() only
RATINGS_ENDPOINT_KEYS = {
    "adj_off_efficiency",
    "adj_def_efficiency",
    "net_ranking",
}

REALISTIC_PAYLOAD = [
    {
        "games": 30,
        "wins": 20,
        "losses": 10,
        "pace": 68.5,
        "teamStats": {
            "fourFactors": {
                "effectiveFieldGoalPct": 0.52,
                "turnoverRatio": 0.15,
                "offensiveReboundPct": 0.30,
                "freeThrowRate": 0.35,
            },
            "fieldGoals": {"pct": 0.46},
            "threePointFieldGoals": {"pct": 0.36},
            "freeThrows": {"pct": 0.72},
            "points": {"total": 2100},
        },
        "opponentStats": {
            "threePointFieldGoals": {"pct": 0.33},
            "points": {"total": 1950},
        },
    }
]


def _make_mock_response(payload, status_code=200):
    """Return a mock httpx.Response-like object."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    mock_resp.headers = {"content-type": "application/json"}
    return mock_resp


def _make_http_status_error(status_code: int):
    """Return an httpx.HTTPStatusError with the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = f"HTTP {status_code}"
    return httpx.HTTPStatusError(
        str(status_code), request=MagicMock(), response=mock_response
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_get_team_season_stats_200_returns_required_keys():
    """
    Mock httpx.get for a 200 response with a realistic payload and verify
    all stats-endpoint keys are present (no efficiency/ratings placeholders).

    Requirements: 2.3, 2.4
    """
    with patch("httpx.get", return_value=_make_mock_response(REALISTIC_PAYLOAD)):
        result = CBBD_HTTP_Client().get_team_season_stats("Duke", 2025)

    assert result is not None
    missing = STATS_ENDPOINT_KEYS - result.keys()
    assert not missing, f"Missing required stats keys: {missing}"
    # Efficiency keys must NOT be present (they come from get_adjusted_ratings)
    for key in RATINGS_ENDPOINT_KEYS:
        assert key not in result, f"Unexpected ratings key '{key}' in stats response"


def test_get_adjusted_ratings_200_returns_keys():
    """
    Mock httpx.get for a 200 response and verify adj_off_efficiency,
    adj_def_efficiency, and net_ranking are present.

    Requirements: 2.3
    """
    ratings_payload = [
        {
            "offensiveRating": 115.2,
            "defensiveRating": 98.7,
            "rankings": {"net": 5},
        }
    ]
    with patch("httpx.get", return_value=_make_mock_response(ratings_payload)):
        result = CBBD_HTTP_Client().get_adjusted_ratings("Duke", 2025)

    assert result is not None
    assert "adj_off_efficiency" in result
    assert "adj_def_efficiency" in result
    assert "net_ranking" in result


def test_merged_stats_and_ratings_contain_all_required_keys():
    """
    Verify that merging get_adjusted_ratings() + get_team_season_stats()
    produces the full 10-key set (REQUIRED_KEYS) as advanced_analytics.py does.

    Requirements: 2.3, 2.8
    """
    ratings_payload = [{"offensiveRating": 115.2, "defensiveRating": 98.7, "rankings": {"net": 5}}]
    stats_payload = REALISTIC_PAYLOAD

    client = CBBD_HTTP_Client()
    with patch("httpx.get", return_value=_make_mock_response(ratings_payload)):
        ratings = client.get_adjusted_ratings("Duke", 2025)
    with patch("httpx.get", return_value=_make_mock_response(stats_payload)):
        stats = client.get_team_season_stats("Duke", 2025)

    merged = {**(ratings or {}), **(stats or {})}
    missing = REQUIRED_KEYS - merged.keys()
    assert not missing, f"Merged result missing required keys: {missing}"


def test_get_team_season_stats_4xx_returns_none():
    """
    Mock httpx.get to raise HTTPStatusError with status 404 and verify
    None is returned.

    Requirements: 2.4
    """
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock()
        mock_get.return_value.raise_for_status.side_effect = _make_http_status_error(404)
        result = CBBD_HTTP_Client().get_team_season_stats("Unknown", 2025)

    assert result is None


def test_get_team_season_stats_5xx_returns_none():
    """
    Mock httpx.get to raise HTTPStatusError with status 500 and verify
    None is returned.

    Requirements: 2.4
    """
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock()
        mock_get.return_value.raise_for_status.side_effect = _make_http_status_error(500)
        result = CBBD_HTTP_Client().get_team_season_stats("Duke", 2025)

    assert result is None


def test_get_team_season_stats_exception_returns_none():
    """
    Mock httpx.get to raise a generic Exception and verify None is returned.

    Requirements: 2.4
    """
    with patch("httpx.get", side_effect=Exception("network failure")):
        result = CBBD_HTTP_Client().get_team_season_stats("Duke", 2025)

    assert result is None


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------


@given(
    st.fixed_dictionaries(
        {
            "games": st.integers(min_value=1, max_value=40),
            "wins": st.integers(min_value=0, max_value=40),
            "losses": st.integers(min_value=0, max_value=40),
            "pace": st.floats(min_value=55.0, max_value=85.0, allow_nan=False),
            "teamStats": st.fixed_dictionaries(
                {
                    "fourFactors": st.fixed_dictionaries(
                        {
                            "effectiveFieldGoalPct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                            "turnoverRatio": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                            "offensiveReboundPct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                            "freeThrowRate": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                        }
                    ),
                    "fieldGoals": st.fixed_dictionaries(
                        {"pct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False)}
                    ),
                    "threePointFieldGoals": st.fixed_dictionaries(
                        {"pct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False)}
                    ),
                    "freeThrows": st.fixed_dictionaries(
                        {"pct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False)}
                    ),
                    "points": st.fixed_dictionaries(
                        {"total": st.integers(min_value=0, max_value=5000)}
                    ),
                }
            ),
            "opponentStats": st.fixed_dictionaries(
                {
                    "threePointFieldGoals": st.fixed_dictionaries(
                        {"pct": st.floats(min_value=0.0, max_value=1.0, allow_nan=False)}
                    ),
                    "points": st.fixed_dictionaries(
                        {"total": st.integers(min_value=0, max_value=5000)}
                    ),
                }
            ),
        }
    )
)
@settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
def test_property_cbbd_normalized_dict_contains_required_keys(mock_item):
    """
    Property 4: CBBD_HTTP_Client normalized dict contains required keys.

    For any valid API response shape, get_team_season_stats() must return a
    dict containing all 7 stats-endpoint keys. The 3 efficiency/ratings keys
    (adj_off_efficiency, adj_def_efficiency, net_ranking) come from
    get_adjusted_ratings() and are NOT expected in the stats response.

    The combined 10-key set (REQUIRED_KEYS) is assembled by advanced_analytics.py
    which merges both endpoint responses.

    Validates: Requirements 2.3, 2.8
    """
    mock_payload = [mock_item]
    mock_resp = _make_mock_response(mock_payload)

    with patch("httpx.get", return_value=mock_resp):
        result = CBBD_HTTP_Client().get_team_season_stats("Duke", 2025)

    assert result is not None, "Expected a dict, got None"
    missing = STATS_ENDPOINT_KEYS - result.keys()
    assert not missing, f"Missing required stats keys: {missing}"
    # Efficiency keys must NOT be present as placeholders
    for key in RATINGS_ENDPOINT_KEYS:
        assert key not in result, f"Unexpected ratings placeholder key '{key}' in stats response"
