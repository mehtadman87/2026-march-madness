"""In-memory cache for team data during CLI execution.

Satisfies Requirements 14.5 and 14.6: cache persists for the duration of a
single CLI execution and clears upon program termination.
"""


class TeamDataCache:
    """Per-team in-memory cache keyed by (team_name, data_type).

    data_type is a string such as "stats", "analytics", "qualitative",
    or "players".  The cache lives only as long as the process that owns it.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], dict] = {}

    def get(self, team_name: str, data_type: str) -> dict | None:
        """Return cached data for the given team and data type, or None."""
        return self._store.get((team_name, data_type))

    def set(self, team_name: str, data_type: str, data: dict) -> None:
        """Store data for the given team and data type."""
        self._store[(team_name, data_type)] = data

    def has(self, team_name: str, data_type: str) -> bool:
        """Return True if data exists for the given team and data type."""
        return (team_name, data_type) in self._store
