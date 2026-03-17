"""
Unit and property-based tests for matchup_analyst agent.

Requirements: 4.2, 4.4, 4.7
"""

import sys
import pytest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# conftest.py registers strands with an identity @tool decorator and stubs
# cbbpy. We only need to ensure the real matchup_analyst module is loaded
# (not a MagicMock stub from test_orchestrator.py's setdefault calls).
sys.modules.pop("src.agents.matchup_analyst", None)

from src.agents.matchup_analyst import (
    _haversine_km,
    _calculate_proximity_scores,
    TEAM_CAMPUS_LOCATIONS,
)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_haversine_known_distance():
    """
    Durham NC (36.0014, -78.9382) to Indianapolis IN (39.7684, -86.1581)
    should be approximately 759 km (within ±50 km tolerance).

    Requirements: 4.2
    """
    dist = _haversine_km(36.0014, -78.9382, 39.7684, -86.1581)
    assert abs(dist - 759.0) <= 50.0, (
        f"Expected ~759 km from Durham NC to Indianapolis IN, got {dist:.1f} km"
    )


def test_haversine_identical_points_is_zero():
    """
    Same point should return 0.0.

    Requirements: 4.2
    """
    assert _haversine_km(36.0014, -78.9382, 36.0014, -78.9382) == 0.0
    assert _haversine_km(0.0, 0.0, 0.0, 0.0) == 0.0
    assert _haversine_km(-45.0, 120.0, -45.0, 120.0) == 0.0


def test_proximity_scores_closer_team_wins():
    """
    Duke (Durham NC ~1050 km from Indy) vs Gonzaga (Spokane WA ~2800 km from Indy)
    at Indianapolis venue → Duke should get score > 0.5.

    Requirements: 4.4, 4.7
    """
    score_a, score_b, detail = _calculate_proximity_scores(
        "Duke", "Gonzaga", "Indianapolis, IN"
    )
    assert score_a > 0.5, (
        f"Duke (closer to Indianapolis) should have score > 0.5, got {score_a}"
    )
    assert score_b < 0.5, (
        f"Gonzaga (farther from Indianapolis) should have score < 0.5, got {score_b}"
    )


def test_proximity_scores_unknown_venue_returns_equal():
    """
    Unknown venue → both scores == 0.5.

    Requirements: 4.6
    """
    score_a, score_b, detail = _calculate_proximity_scores(
        "Duke", "Kansas", "Unknown Arena XYZ"
    )
    assert score_a == 0.5
    assert score_b == 0.5


def test_proximity_scores_unknown_team_uses_keyword_fallback():
    """
    Team not in TEAM_CAMPUS_LOCATIONS → falls back to keyword heuristic.
    The function should not raise and should return valid scores.

    Requirements: 4.5
    """
    score_a, score_b, detail = _calculate_proximity_scores(
        "UnknownTeamXYZ", "Duke", "Indianapolis, IN"
    )
    # Should return valid scores (keyword fallback or equal)
    assert 0.0 <= score_a <= 1.0
    assert 0.0 <= score_b <= 1.0
    assert abs(score_a + score_b - 1.0) < 1e-9, (
        f"Scores should sum to 1.0, got {score_a} + {score_b}"
    )


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------


@given(
    st.floats(-90.0, 90.0, allow_nan=False, allow_infinity=False),
    st.floats(-180.0, 180.0, allow_nan=False, allow_infinity=False),
    st.floats(-90.0, 90.0, allow_nan=False, allow_infinity=False),
    st.floats(-180.0, 180.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=5000)
def test_property_haversine_non_negative(lat1, lon1, lat2, lon2):
    """
    Property 7: Haversine distances are non-negative.

    For any pair of valid (lat, lon) coordinate pairs, _haversine_km shall
    return a value >= 0.0.

    Validates: Requirements 4.2
    """
    dist = _haversine_km(lat1, lon1, lat2, lon2)
    assert dist >= 0.0, (
        f"Expected non-negative distance, got {dist} for "
        f"({lat1}, {lon1}) → ({lat2}, {lon2})"
    )


@given(
    st.floats(-90.0, 90.0, allow_nan=False, allow_infinity=False),
    st.floats(-180.0, 180.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, deadline=5000)
def test_property_haversine_identical_points_zero(lat, lon):
    """
    Property 7 (identical points): _haversine_km(lat, lon, lat, lon) == 0.0
    for any valid coordinate.

    Validates: Requirements 4.2
    """
    dist = _haversine_km(lat, lon, lat, lon)
    assert dist == 0.0, (
        f"Expected 0.0 for identical points ({lat}, {lon}), got {dist}"
    )


@given(
    # venue coords
    st.floats(-89.0, 89.0, allow_nan=False),
    st.floats(-179.0, 179.0, allow_nan=False),
    # team_a lat offset from venue: small offset so team_a is close
    st.floats(0.1, 2.0, allow_nan=False),
    # team_b lat offset from venue: larger offset so team_b is farther
    st.floats(10.0, 45.0, allow_nan=False),
)
@settings(max_examples=50, deadline=5000)
def test_property_location_advantage_monotonicity(v_lat, v_lon, a_offset, b_offset):
    """
    Property 6: Location advantage monotonicity.

    When team_a is strictly closer to the venue than team_b, the location
    advantage score for team_a shall be strictly greater than 0.5.

    Validates: Requirements 4.4, 4.7
    """
    # Place team_a close to venue, team_b far from venue (both offset in same
    # direction so the comparison is unambiguous)
    a_lat = max(-89.0, min(89.0, v_lat + a_offset))
    a_lon = v_lon
    b_lat = max(-89.0, min(89.0, v_lat + b_offset))
    b_lon = v_lon

    dist_a = _haversine_km(a_lat, a_lon, v_lat, v_lon)
    dist_b = _haversine_km(b_lat, b_lon, v_lat, v_lon)

    assume(dist_a < dist_b)  # guard: only test when team_a is strictly closer

    # Patch TEAM_CAMPUS_LOCATIONS and _resolve_venue_coords
    with patch("src.agents.matchup_analyst.TEAM_CAMPUS_LOCATIONS", {"TeamA": (a_lat, a_lon), "TeamB": (b_lat, b_lon)}), \
         patch("src.agents.matchup_analyst._resolve_venue_coords", return_value=(v_lat, v_lon)):
        score_a, score_b, _ = _calculate_proximity_scores("TeamA", "TeamB", "any venue")

    assert score_a > 0.5, (
        f"Expected score_a > 0.5 when dist_a={dist_a:.1f} < dist_b={dist_b:.1f}"
    )
