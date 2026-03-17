"""Team and Bracket data models for March Madness Bracket Predictor.

Defines Team, Matchup, RegionBracket, and Bracket dataclasses used throughout
the bracket prediction system.
"""

from dataclasses import dataclass, field
from typing import Any

from src.models.enums import Region, RoundName


@dataclass
class Team:
    """Represents a tournament team.
    
    Attributes:
        name: Team name (e.g., "Duke")
        seed: Seed number (1-16)
        region: Tournament region (East, West, South, Midwest)
    """
    name: str
    seed: int
    region: Region

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "name": self.name,
            "seed": self.seed,
            "region": self.region.value
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Team":
        """Deserialize from JSON-compatible dict."""
        return cls(
            name=data["name"],
            seed=data["seed"],
            region=Region(data["region"])
        )


@dataclass
class Matchup:
    """Represents a single game matchup between two teams.
    
    Attributes:
        team_a: First team in the matchup
        team_b: Second team in the matchup
        round_name: Tournament round (Round of 64, etc.)
        venue: Game location / arena name
        game_number: Position within the round
    """
    team_a: Team
    team_b: Team
    round_name: RoundName
    venue: str
    game_number: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "team_a": self.team_a.to_dict(),
            "team_b": self.team_b.to_dict(),
            "round_name": self.round_name.value,
            "venue": self.venue,
            "game_number": self.game_number
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Matchup":
        """Deserialize from JSON-compatible dict."""
        return cls(
            team_a=Team.from_dict(data["team_a"]),
            team_b=Team.from_dict(data["team_b"]),
            round_name=RoundName(data["round_name"]),
            venue=data["venue"],
            game_number=data["game_number"]
        )


@dataclass
class RegionBracket:
    """Represents a single region's bracket.
    
    Attributes:
        region: The tournament region
        teams: List of 16 teams (seeds 1-16)
        matchups: First-round matchups (8 per region)
    """
    region: Region
    teams: list[Team] = field(default_factory=list)
    matchups: list[Matchup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "region": self.region.value,
            "teams": [team.to_dict() for team in self.teams],
            "matchups": [matchup.to_dict() for matchup in self.matchups]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionBracket":
        """Deserialize from JSON-compatible dict."""
        return cls(
            region=Region(data["region"]),
            teams=[Team.from_dict(t) for t in data["teams"]],
            matchups=[Matchup.from_dict(m) for m in data["matchups"]]
        )


class BracketValidationError(Exception):
    """Raised when bracket validation fails."""
    pass


@dataclass
class Bracket:
    """Represents the complete tournament bracket.
    
    Attributes:
        regions: List of exactly 4 RegionBrackets
        season: Tournament season year (e.g., 2025)
    
    Raises:
        BracketValidationError: If bracket doesn't contain exactly 64 teams,
            4 regions, and 32 first-round matchups.
    """
    regions: list[RegionBracket] = field(default_factory=list)
    season: int = 2025

    def __post_init__(self) -> None:
        """Validate bracket structure after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate bracket contains exactly 64 teams, 4 regions, and 32 first-round matchups.
        
        Raises:
            BracketValidationError: If validation fails.
        """
        # Validate exactly 4 regions
        if len(self.regions) != 4:
            raise BracketValidationError(
                f"Bracket must contain exactly 4 regions, got {len(self.regions)}"
            )
        
        # Validate exactly 64 teams (16 per region)
        total_teams = len(self.get_all_teams())
        if total_teams != 64:
            raise BracketValidationError(
                f"Bracket must contain exactly 64 teams, got {total_teams}"
            )
        
        # Validate exactly 32 first-round matchups (8 per region)
        total_matchups = len(self.get_first_round_matchups())
        if total_matchups != 32:
            raise BracketValidationError(
                f"Bracket must contain exactly 32 first-round matchups, got {total_matchups}"
            )

    def get_all_teams(self) -> list[Team]:
        """Get all teams across all regions.
        
        Returns:
            List of all 64 teams in the bracket.
        """
        return [team for region in self.regions for team in region.teams]

    def get_first_round_matchups(self) -> list[Matchup]:
        """Get all first-round matchups across all regions.
        
        Returns:
            List of all 32 first-round matchups.
        """
        return [matchup for region in self.regions for matchup in region.matchups]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "regions": [region.to_dict() for region in self.regions],
            "season": self.season
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bracket":
        """Deserialize from JSON-compatible dict.
        
        Args:
            data: Dictionary containing bracket data.
            
        Returns:
            Bracket instance.
            
        Raises:
            BracketValidationError: If deserialized bracket fails validation.
        """
        return cls(
            regions=[RegionBracket.from_dict(r) for r in data["regions"]],
            season=data["season"]
        )
