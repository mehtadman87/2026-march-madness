"""Output data models for March Madness Bracket Predictor.

Defines RoundResult and BracketOutput dataclasses for structured output
of bracket predictions including JSON serialization and console display.
"""

from dataclasses import dataclass, field
from typing import Any
import json

from src.models.enums import RoundName
from src.models.prediction import Prediction


@dataclass
class RoundResult:
    """Represents the results of a single tournament round.
    
    Attributes:
        round_name: The tournament round (e.g., Round of 64, Sweet 16).
        matchups: List of Prediction objects for each matchup in the round.
        upset_count: Number of upsets predicted in this round.
        cinderella_candidates: List of team names (seeds 11+) advancing.
    """
    round_name: RoundName
    matchups: list[Prediction]
    upset_count: int
    cinderella_candidates: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict.
        
        Returns:
            Dictionary representation of the round result.
        """
        return {
            "round_name": self.round_name.value,
            "matchups": [m.to_dict() for m in self.matchups],
            "upset_count": self.upset_count,
            "cinderella_candidates": self.cinderella_candidates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoundResult":
        """Deserialize from JSON-compatible dict.
        
        Args:
            data: Dictionary containing round result data.
            
        Returns:
            RoundResult instance.
        """
        return cls(
            round_name=RoundName(data["round_name"]),
            matchups=[Prediction.from_dict(m) for m in data["matchups"]],
            upset_count=data["upset_count"],
            cinderella_candidates=data["cinderella_candidates"],
        )


@dataclass
class BracketOutput:
    """Complete bracket prediction output.
    
    Attributes:
        champion: Name of the predicted tournament champion.
        champion_confidence: Confidence score (50-99) for the champion prediction.
        champion_path: List of opponents the champion defeated in each round.
        rounds: List of RoundResult objects for all tournament rounds.
        upset_alerts: List of all upset predictions across all rounds.
        cinderella_watch: List of lower-seeded teams (11+) advancing past R1.
    """
    champion: str
    champion_confidence: int
    champion_path: list[str]
    rounds: list[RoundResult]
    upset_alerts: list[dict[str, Any]]
    cinderella_watch: list[dict[str, Any]]
    championship_score: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result = {
            "champion": self.champion,
            "champion_confidence": self.champion_confidence,
            "champion_path": self.champion_path,
            "rounds": [r.to_dict() for r in self.rounds],
            "upset_alerts": self.upset_alerts,
            "cinderella_watch": self.cinderella_watch,
        }
        if self.championship_score is not None:
            result["championship_score"] = self.championship_score
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BracketOutput":
        """Deserialize from JSON-compatible dict.
        
        Args:
            data: Dictionary containing bracket output data.
            
        Returns:
            BracketOutput instance.
        """
        return cls(
            champion=data["champion"],
            champion_confidence=data["champion_confidence"],
            champion_path=data["champion_path"],
            rounds=[RoundResult.from_dict(r) for r in data["rounds"]],
            upset_alerts=data["upset_alerts"],
            cinderella_watch=data["cinderella_watch"],
        )

    def to_json(self) -> str:
        """Serialize complete output to JSON string.
        
        Produces a complete JSON structure with ALL matchups, predicted winners,
        and confidence percentages. Each matchup includes:
        - Both team names and seeds
        - Predicted winner
        - Confidence score
        - Rationale
        - Key factors
        - Upset alert flag
        
        Returns:
            JSON string representation of the complete bracket output.
        """
        return json.dumps(self.to_dict(), indent=2)

    def _format_matchup_lines(self, matchup: Prediction) -> list[str]:
        """Format a single matchup for console display.
        
        Args:
            matchup: The Prediction object to format.
            
        Returns:
            List of formatted lines for the matchup.
        """
        lines: list[str] = []
        team_a_display = f"({matchup.team_a.seed}) {matchup.team_a.name}"
        team_b_display = f"({matchup.team_b.seed}) {matchup.team_b.name}"
        
        winner_seed = matchup.team_a.seed if matchup.winner == matchup.team_a.name else matchup.team_b.seed
        upset_marker = " 🚨 UPSET" if matchup.upset_alert else ""
        
        lines.append(f"  {team_a_display} vs {team_b_display}")
        lines.append(f"    → Winner: ({winner_seed}) {matchup.winner} [{matchup.confidence}%]{upset_marker}")
        lines.append(f"    Key factors: {', '.join(matchup.key_factors[:3])}")
        lines.append("")
        return lines

    def _format_round_lines(self, round_result: RoundResult) -> list[str]:
        """Format a single round for console display.
        
        Args:
            round_result: The RoundResult object to format.
            
        Returns:
            List of formatted lines for the round.
        """
        lines: list[str] = []
        lines.append(f"{'─' * 60}")
        lines.append(f"📊 {round_result.round_name.value.upper()}")
        lines.append(f"{'─' * 60}")
        
        for matchup in round_result.matchups:
            lines.extend(self._format_matchup_lines(matchup))
        
        if round_result.upset_count > 0:
            lines.append(f"  ⚠️  Upsets in round: {round_result.upset_count}")
        
        if round_result.cinderella_candidates:
            lines.append(f"  🏀 Cinderella candidates: {', '.join(round_result.cinderella_candidates)}")
        
        lines.append("")
        return lines

    def _format_upset_alerts(self) -> list[str]:
        """Format upset alerts section for console display.
        
        Returns:
            List of formatted lines for upset alerts.
        """
        if not self.upset_alerts:
            return []
        
        lines: list[str] = []
        lines.append("─" * 60)
        lines.append("🚨 ALL UPSET ALERTS")
        lines.append("─" * 60)
        for alert in self.upset_alerts:
            winner_info = f"({alert.get('winner_seed', '?')}) {alert.get('winner', 'Unknown')}"
            loser_info = f"({alert.get('loser_seed', '?')}) {alert.get('loser', 'Unknown')}"
            lines.append(f"  • {alert.get('round', 'Unknown')}: {winner_info} over {loser_info}")
        lines.append("")
        return lines

    def _format_cinderella_watch(self) -> list[str]:
        """Format Cinderella watch section for console display.
        
        Returns:
            List of formatted lines for Cinderella watch.
        """
        if not self.cinderella_watch:
            return []
        
        lines: list[str] = []
        lines.append("─" * 60)
        lines.append("🌟 CINDERELLA WATCH")
        lines.append("─" * 60)
        for team in self.cinderella_watch:
            team_info = f"({team.get('seed', '?')}) {team.get('team', 'Unknown')}"
            lines.append(f"  • {team_info} - Advanced to: {team.get('furthest_round', 'Unknown')}")
        lines.append("")
        return lines

    def to_console_summary(self) -> str:
        """Generate human-readable round-by-round summary.
        
        Displays each round with matchup results, showing:
        - Round name
        - Each matchup with teams, seeds, winner, and confidence
        - Upset alerts for the round
        - Cinderella candidates
        - Final champion information
        
        Returns:
            Human-readable string summary of the bracket predictions.
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("MARCH MADNESS BRACKET PREDICTIONS")
        lines.append("=" * 60)
        lines.append("")

        for round_result in self.rounds:
            lines.extend(self._format_round_lines(round_result))

        # Champion summary
        lines.append("=" * 60)
        lines.append("🏆 TOURNAMENT CHAMPION")
        lines.append("=" * 60)
        lines.append(f"  Champion: {self.champion}")
        lines.append(f"  Confidence: {self.champion_confidence}%")
        lines.append(f"  Path to victory: {' → '.join(self.champion_path)}")
        if self.championship_score:
            lines.append(f"")
            lines.append(f"  📊 Predicted Championship Score:")
            lines.append(f"     Total: {self.championship_score.get('predicted_total', 'N/A')}")
            ta = self.championship_score.get('team_a_predicted_score', '?')
            tb = self.championship_score.get('team_b_predicted_score', '?')
            lines.append(f"     {ta} - {tb}")
        lines.append("")

        lines.extend(self._format_upset_alerts())
        lines.extend(self._format_cinderella_watch())

        lines.append("=" * 60)
        
        return "\n".join(lines)
