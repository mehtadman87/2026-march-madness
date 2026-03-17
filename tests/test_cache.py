"""
Unit tests for TeamDataCache.

Requirements: 14.5, 14.6
"""

import pytest

from src.utils.cache import TeamDataCache


@pytest.fixture
def cache() -> TeamDataCache:
    return TeamDataCache()


# ---------------------------------------------------------------------------
# get / set – basic store and retrieve
# ---------------------------------------------------------------------------


def test_cache_stores_and_retrieves_by_name_and_type(cache):
    """set() stores data that get() can retrieve with the same key."""
    data = {"wins": 25, "losses": 8}
    cache.set("Duke", "stats", data)
    assert cache.get("Duke", "stats") == data


def test_cache_returns_none_for_missing_entry(cache):
    """get() returns None when no entry exists for the given key."""
    assert cache.get("Kansas", "stats") is None


def test_cache_returns_none_for_missing_data_type(cache):
    """get() returns None when the team exists under a different data_type."""
    cache.set("Duke", "stats", {"wins": 25})
    assert cache.get("Duke", "analytics") is None


# ---------------------------------------------------------------------------
# has()
# ---------------------------------------------------------------------------


def test_has_returns_true_for_existing_entry(cache):
    """has() returns True after an entry has been set."""
    cache.set("Kentucky", "qualitative", {"coach": "Calipari"})
    assert cache.has("Kentucky", "qualitative") is True


def test_has_returns_false_for_missing_entry(cache):
    """has() returns False when no entry exists for the given key."""
    assert cache.has("Kentucky", "qualitative") is False


def test_has_returns_false_for_missing_data_type(cache):
    """has() returns False when the team exists under a different data_type."""
    cache.set("Kentucky", "stats", {"wins": 20})
    assert cache.has("Kentucky", "qualitative") is False


# ---------------------------------------------------------------------------
# set() overwrites existing entries
# ---------------------------------------------------------------------------


def test_set_overwrites_existing_entry(cache):
    """set() replaces the previously stored value for the same key."""
    cache.set("UNC", "stats", {"wins": 20})
    cache.set("UNC", "stats", {"wins": 28, "losses": 5})
    result = cache.get("UNC", "stats")
    assert result == {"wins": 28, "losses": 5}


# ---------------------------------------------------------------------------
# Independence: different data_types for the same team
# ---------------------------------------------------------------------------


def test_different_data_types_stored_independently(cache):
    """Two data_types for the same team do not interfere with each other."""
    stats = {"wins": 30}
    analytics = {"adj_oe": 115.2}
    cache.set("Gonzaga", "stats", stats)
    cache.set("Gonzaga", "analytics", analytics)

    assert cache.get("Gonzaga", "stats") == stats
    assert cache.get("Gonzaga", "analytics") == analytics


# ---------------------------------------------------------------------------
# Independence: different team names with the same data_type
# ---------------------------------------------------------------------------


def test_different_team_names_stored_independently(cache):
    """Two teams stored under the same data_type do not interfere."""
    duke_data = {"wins": 25}
    unc_data = {"wins": 22}
    cache.set("Duke", "stats", duke_data)
    cache.set("UNC", "stats", unc_data)

    assert cache.get("Duke", "stats") == duke_data
    assert cache.get("UNC", "stats") == unc_data
