"""Prediction data model for March Madness Bracket Predictor.

Defines the Prediction dataclass used to represent a single matchup prediction
with winner, confidence score, rationale, and upset alert.
"""

from dataclasses import dataclass, field
from typing import Any

from src.models.enums import RoundName
from src.models.team import Team


class PredictionValidationError(Exception):
    """Raised when prediction validation fails."""
    pass


def _validate_confidence(confidence: int) -> None:
    """Validate confidence is between 50 and 99 inclusive.
    
    Args:
        confidence: The confidence score to validate.
        
    Raises:
        PredictionValidationError: If confidence is not in range 50-99.
    """
    if not isinstance(confidence, int) or confidence < 50 or confidence > 99:
        raise PredictionValidationError(
            f"Confidence must be an integer between 50 and 99, got {confidence}"
        )


def _validate_rationale(rationale: str) -> None:
    """Validate rationale has at least 2 sentences.
    
    A sentence is detected by finding at least one period followed by text
    (indicating there's content after the first sentence).
    
    Args:
        rationale: The rationale text to validate.
        
    Raises:
        PredictionValidationError: If rationale doesn't have at least 2 sentences.
    """
    if not isinstance(rationale, str):
        raise PredictionValidationError(
            f"Rationale must be a string, got {type(rationale).__name__}"
        )
    
    # Find periods that are followed by text (indicating multiple sentences)
    # We need at least one period followed by non-empty content
    stripped = rationale.strip()
    if not stripped:
        raise PredictionValidationError("Rationale cannot be empty")
    
    # Split by period and check if there's meaningful content after the first sentence
    parts = stripped.split('.')
    # Filter out empty parts (from trailing periods or multiple periods)
    non_empty_parts = [p.strip() for p in parts if p.strip()]
    
    if len(non_empty_parts) < 2:
        raise PredictionValidationError(
            "Rationale must have at least 2 sentences (at least one period followed by text)"
        )


def _calculate_upset_alert(winner: str, team_a: Team, team_b: Team) -> bool:
    """Calculate if this prediction is an upset.
    
    An upset occurs when the winner has a higher seed number (lower seed)
    than their opponent.
    
    Args:
        winner: The name of the winning team.
        team_a: First team in the matchup.
        team_b: Second team in the matchup.
        
    Returns:
        True if the winner is the lower-seeded team (upset), False otherwise.
    """
    if winner == team_a.name:
        winner_seed = team_a.seed
        opponent_seed = team_b.seed
    elif winner == team_b.name:
        winner_seed = team_b.seed
        opponent_seed = team_a.seed
    else:
        # Winner name doesn't match either team - shouldn't happen in valid data
        return False
    
    # Upset when winner seed > opponent seed (higher seed number = lower seed)
    return winner_seed > opponent_seed


@dataclass
class Prediction:
    """Represents a prediction for a single matchup.
    
    Attributes:
        team_a: First team in the matchup.
        team_b: Second team in the matchup.
        winner: Name of the predicted winning team.
        confidence: Confidence score (50-99).
        rationale: Explanation with at least 2 sentences.
        key_factors: List of decisive factors for the prediction.
        upset_alert: True if winner seed > opponent seed.
        round_name: Tournament round for this matchup.
        weight_adjustments: Optional dict of weight adjustments if data was missing.
        
    Raises:
        PredictionValidationError: If confidence is not 50-99 or rationale
            doesn't have at least 2 sentences.
    """
    team_a: Team
    team_b: Team
    winner: str
    confidence: int
    rationale: str
    key_factors: list[str]
    upset_alert: bool
    round_name: RoundName
    weight_adjustments: dict[str, float] | None = None

    def __post_init__(self) -> None:
        """Validate prediction after initialization."""
        _validate_confidence(self.confidence)
        _validate_rationale(self.rationale)
        # Auto-calculate upset_alert based on winner seed vs opponent seed
        self.upset_alert = _calculate_upset_alert(
            self.winner, self.team_a, self.team_b
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict.
        
        Returns:
            Dictionary representation of the prediction.
        """
        result: dict[str, Any] = {
            "team_a": self.team_a.to_dict(),
            "team_b": self.team_b.to_dict(),
            "winner": self.winner,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "key_factors": self.key_factors,
            "upset_alert": self.upset_alert,
            "round_name": self.round_name.value,
        }
        if self.weight_adjustments is not None:
            result["weight_adjustments"] = self.weight_adjustments
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Prediction":
        """Deserialize from JSON-compatible dict.
        
        Args:
            data: Dictionary containing prediction data.
            
        Returns:
            Prediction instance.
            
        Raises:
            PredictionValidationError: If deserialized prediction fails validation.
        """
        return cls(
            team_a=Team.from_dict(data["team_a"]),
            team_b=Team.from_dict(data["team_b"]),
            winner=data["winner"],
            confidence=data["confidence"],
            rationale=data["rationale"],
            key_factors=data["key_factors"],
            upset_alert=data["upset_alert"],  # Will be recalculated in __post_init__
            round_name=RoundName(data["round_name"]),
            weight_adjustments=data.get("weight_adjustments"),
        )
