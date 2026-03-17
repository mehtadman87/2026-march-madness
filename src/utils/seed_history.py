"""Utility functions for loading and querying historical seed matchup win rate data."""

import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent / "data" / "seed_history.json"
_cache: dict | None = None


def load_seed_history() -> dict:
    """Load and return the full seed history dict from seed_history.json."""
    global _cache
    if _cache is None:
        with open(_DATA_PATH, "r") as f:
            _cache = json.load(f)
    return _cache


def get_seed_win_rate(seed_a: int, seed_b: int) -> float:
    """Return the win rate for the higher seed (lower number) in a matchup.

    Normalizes the key so the lower seed number always comes first.
    Returns 0.5 as a neutral default if the pairing is not found.
    """
    lower, higher = min(seed_a, seed_b), max(seed_a, seed_b)
    key = f"{lower}_vs_{higher}"
    data = load_seed_history()
    entry = data.get(key)
    if entry is None:
        return 0.5
    return entry["higher_seed_wins"]
