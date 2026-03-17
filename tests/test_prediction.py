"""Unit tests for Prediction dataclass."""

import pytest

from src.models.enums import Region, RoundName
from src.models.team import Team
from src.models.prediction import (
    Prediction,
    PredictionValidationError,
    _validate_confidence,
    _validate_rationale,
    _calculate_upset_alert,
)


class TestValidateConfidence:
    """Tests for confidence validation."""

    def test_valid_confidence_minimum(self):
        """Test confidence at minimum value (50) is valid."""
        _validate_confidence(50)  # Should not raise

    def test_valid_confidence_maximum(self):
        """Test confidence at maximum value (99) is valid."""
        _validate_confidence(99)  # Should not raise

    def test_valid_confidence_middle(self):
        """Test confidence in middle of range is valid."""
        _validate_confidence(75)  # Should not raise

    def test_invalid_confidence_below_minimum(self):
        """Test confidence below 50 raises error."""
        with pytest.raises(PredictionValidationError) as exc_info:
            _validate_confidence(49)
        assert "between 50 and 99" in str(exc_info.value)

    def test_invalid_confidence_above_maximum(self):
        """Test confidence above 99 raises error."""
        with pytest.raises(PredictionValidationError) as exc_info:
            _validate_confidence(100)
        assert "between 50 and 99" in str(exc_info.value)

    def test_invalid_confidence_not_integer(self):
        """Test non-integer confidence raises error."""
        with pytest.raises(PredictionValidationError):
            _validate_confidence(75.5)  # type: ignore


class TestValidateRationale:
    """Tests for rationale validation."""

    def test_valid_rationale_two_sentences(self):
        """Test rationale with exactly 2 sentences is valid."""
        _validate_rationale("First sentence. Second sentence.")  # Should not raise

    def test_valid_rationale_multiple_sentences(self):
        """Test rationale with more than 2 sentences is valid."""
        _validate_rationale("One. Two. Three.")  # Should not raise

    def test_invalid_rationale_single_sentence(self):
        """Test rationale with only 1 sentence raises error."""
        with pytest.raises(PredictionValidationError) as exc_info:
            _validate_rationale("Only one sentence.")
        assert "at least 2 sentences" in str(exc_info.value)

    def test_invalid_rationale_empty(self):
        """Test empty rationale raises error."""
        with pytest.raises(PredictionValidationError) as exc_info:
            _validate_rationale("")
        assert "cannot be empty" in str(exc_info.value)

    def test_invalid_rationale_whitespace_only(self):
        """Test whitespace-only rationale raises error."""
        with pytest.raises(PredictionValidationError):
            _validate_rationale("   ")


class TestCalculateUpsetAlert:
    """Tests for upset alert calculation."""

    def test_no_upset_higher_seed_wins(self):
        """Test no upset when higher seed (lower number) wins."""
        team_a = Team(name="Duke", seed=1, region=Region.EAST)
        team_b = Team(name="Underdog", seed=16, region=Region.EAST)
        assert _calculate_upset_alert("Duke", team_a, team_b) is False

    def test_upset_lower_seed_wins(self):
        """Test upset when lower seed (higher number) wins."""
        team_a = Team(name="Duke", seed=1, region=Region.EAST)
        team_b = Team(name="Underdog", seed=16, region=Region.EAST)
        assert _calculate_upset_alert("Underdog", team_a, team_b) is True

    def test_no_upset_equal_seeds(self):
        """Test no upset when seeds are equal."""
        team_a = Team(name="Team A", seed=8, region=Region.EAST)
        team_b = Team(name="Team B", seed=8, region=Region.WEST)
        assert _calculate_upset_alert("Team A", team_a, team_b) is False

    def test_upset_team_b_lower_seed_wins(self):
        """Test upset when team_b (lower seed) wins."""
        team_a = Team(name="Favorite", seed=2, region=Region.SOUTH)
        team_b = Team(name="Cinderella", seed=15, region=Region.SOUTH)
        assert _calculate_upset_alert("Cinderella", team_a, team_b) is True



class TestPredictionDataclass:
    """Tests for Prediction dataclass."""

    @pytest.fixture
    def team_a(self):
        """Create a sample team_a fixture."""
        return Team(name="Duke", seed=1, region=Region.EAST)

    @pytest.fixture
    def team_b(self):
        """Create a sample team_b fixture."""
        return Team(name="Underdog", seed=16, region=Region.EAST)

    @pytest.fixture
    def valid_prediction(self, team_a, team_b):
        """Create a valid prediction fixture."""
        return Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=85,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent advantage", "Tournament experience"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
        )

    def test_prediction_creation_valid(self, team_a, team_b):
        """Test creating a valid prediction."""
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=85,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent advantage", "Tournament experience"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
        )
        assert prediction.winner == "Duke"
        assert prediction.confidence == 85
        assert prediction.upset_alert is False

    def test_prediction_auto_calculates_upset_alert(self, team_a, team_b):
        """Test that upset_alert is auto-calculated based on seeds."""
        # Even if we pass upset_alert=False, it should be recalculated
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Underdog",  # 16 seed beating 1 seed
            confidence=55,
            rationale="Underdog has momentum. They are playing great basketball.",
            key_factors=["Momentum", "Hot shooting"],
            upset_alert=False,  # This should be overridden to True
            round_name=RoundName.ROUND_OF_64,
        )
        assert prediction.upset_alert is True

    def test_prediction_invalid_confidence(self, team_a, team_b):
        """Test that invalid confidence raises error."""
        with pytest.raises(PredictionValidationError):
            Prediction(
                team_a=team_a,
                team_b=team_b,
                winner="Duke",
                confidence=100,  # Invalid - max is 99
                rationale="Duke has superior talent. Their experience will be decisive.",
                key_factors=["Talent"],
                upset_alert=False,
                round_name=RoundName.ROUND_OF_64,
            )

    def test_prediction_invalid_rationale(self, team_a, team_b):
        """Test that invalid rationale raises error."""
        with pytest.raises(PredictionValidationError):
            Prediction(
                team_a=team_a,
                team_b=team_b,
                winner="Duke",
                confidence=85,
                rationale="Only one sentence here.",  # Invalid - needs 2 sentences
                key_factors=["Talent"],
                upset_alert=False,
                round_name=RoundName.ROUND_OF_64,
            )

    def test_prediction_with_weight_adjustments(self, team_a, team_b):
        """Test prediction with weight adjustments."""
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=75,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
            weight_adjustments={"efficiency_margin": 0.30, "matchup_factors": 0.25},
        )
        assert prediction.weight_adjustments == {
            "efficiency_margin": 0.30,
            "matchup_factors": 0.25,
        }


class TestPredictionSerialization:
    """Tests for Prediction to_dict and from_dict methods."""

    @pytest.fixture
    def team_a(self):
        """Create a sample team_a fixture."""
        return Team(name="Duke", seed=1, region=Region.EAST)

    @pytest.fixture
    def team_b(self):
        """Create a sample team_b fixture."""
        return Team(name="Underdog", seed=16, region=Region.EAST)

    def test_to_dict_basic(self, team_a, team_b):
        """Test to_dict produces correct structure."""
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=85,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent advantage", "Tournament experience"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
        )
        result = prediction.to_dict()

        assert result["winner"] == "Duke"
        assert result["confidence"] == 85
        assert result["rationale"] == "Duke has superior talent. Their experience will be decisive."
        assert result["key_factors"] == ["Talent advantage", "Tournament experience"]
        assert result["upset_alert"] is False
        assert result["round_name"] == "Round of 64"
        assert result["team_a"]["name"] == "Duke"
        assert result["team_b"]["name"] == "Underdog"
        assert "weight_adjustments" not in result

    def test_to_dict_with_weight_adjustments(self, team_a, team_b):
        """Test to_dict includes weight_adjustments when present."""
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=75,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
            weight_adjustments={"efficiency_margin": 0.30},
        )
        result = prediction.to_dict()
        assert result["weight_adjustments"] == {"efficiency_margin": 0.30}

    def test_from_dict_basic(self):
        """Test from_dict creates correct Prediction."""
        data = {
            "team_a": {"name": "Duke", "seed": 1, "region": "East"},
            "team_b": {"name": "Underdog", "seed": 16, "region": "East"},
            "winner": "Duke",
            "confidence": 85,
            "rationale": "Duke has superior talent. Their experience will be decisive.",
            "key_factors": ["Talent advantage", "Tournament experience"],
            "upset_alert": False,
            "round_name": "Round of 64",
        }
        prediction = Prediction.from_dict(data)

        assert prediction.winner == "Duke"
        assert prediction.confidence == 85
        assert prediction.team_a.name == "Duke"
        assert prediction.team_b.name == "Underdog"
        assert prediction.round_name == RoundName.ROUND_OF_64
        assert prediction.weight_adjustments is None

    def test_from_dict_with_weight_adjustments(self):
        """Test from_dict handles weight_adjustments."""
        data = {
            "team_a": {"name": "Duke", "seed": 1, "region": "East"},
            "team_b": {"name": "Underdog", "seed": 16, "region": "East"},
            "winner": "Duke",
            "confidence": 75,
            "rationale": "Duke has superior talent. Their experience will be decisive.",
            "key_factors": ["Talent"],
            "upset_alert": False,
            "round_name": "Round of 64",
            "weight_adjustments": {"efficiency_margin": 0.30},
        }
        prediction = Prediction.from_dict(data)
        assert prediction.weight_adjustments == {"efficiency_margin": 0.30}

    def test_round_trip_serialization(self, team_a, team_b):
        """Test that to_dict -> from_dict produces equivalent Prediction."""
        original = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=85,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent advantage", "Tournament experience"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
            weight_adjustments={"efficiency_margin": 0.30, "matchup_factors": 0.25},
        )

        serialized = original.to_dict()
        restored = Prediction.from_dict(serialized)

        assert restored.team_a.name == original.team_a.name
        assert restored.team_a.seed == original.team_a.seed
        assert restored.team_a.region == original.team_a.region
        assert restored.team_b.name == original.team_b.name
        assert restored.team_b.seed == original.team_b.seed
        assert restored.team_b.region == original.team_b.region
        assert restored.winner == original.winner
        assert restored.confidence == original.confidence
        assert restored.rationale == original.rationale
        assert restored.key_factors == original.key_factors
        assert restored.upset_alert == original.upset_alert
        assert restored.round_name == original.round_name
        assert restored.weight_adjustments == original.weight_adjustments

    def test_round_trip_upset_prediction(self):
        """Test round-trip for an upset prediction."""
        data = {
            "team_a": {"name": "Favorite", "seed": 2, "region": "South"},
            "team_b": {"name": "Cinderella", "seed": 15, "region": "South"},
            "winner": "Cinderella",
            "confidence": 55,
            "rationale": "Cinderella is hot. They have momentum going into the tournament.",
            "key_factors": ["Momentum", "Hot shooting"],
            "upset_alert": True,
            "round_name": "Round of 64",
        }
        prediction = Prediction.from_dict(data)
        assert prediction.upset_alert is True

        serialized = prediction.to_dict()
        assert serialized["upset_alert"] is True


# ---------------------------------------------------------------------------
# Task 9.3 — Property 8: Region round-trip in predict_matchup
# ---------------------------------------------------------------------------
import sys
from unittest.mock import MagicMock

from hypothesis import given, settings
import hypothesis.strategies as st

from src.models.enums import Region

# conftest.py registers strands with an identity @tool decorator.
# Remove any stale MagicMock stub for prediction so we import the real module.
sys.modules.pop("src.agents.prediction", None)

from src.agents.prediction import predict_matchup  # noqa: E402


def _call_predict_matchup(region_a="East", region_b="East"):
    """Helper to call predict_matchup with minimal valid args."""
    return predict_matchup(
        team_a="Duke",
        team_b="Kansas",
        seed_a=1,
        seed_b=2,
        round_name="Round of 64",
        team_stats={},
        qualitative={},
        analytics={},
        matchup={},
        players={},
        region_a=region_a,
        region_b=region_b,
    )


class TestPredictMatchupRegionRoundTrip:
    """
    Property 8: Region round-trip in predict_matchup
    Validates: Requirements 5.2, 5.5
    """

    @given(
        region_a=st.sampled_from([r.value for r in Region]),
        region_b=st.sampled_from([r.value for r in Region]),
    )
    @settings(max_examples=10, deadline=2000)
    def test_region_round_trip_property(self, region_a, region_b):
        """**Validates: Requirements 5.2, 5.5**

        Property 8: For any valid Region enum value passed as region_a / region_b,
        the returned dict must reflect those exact region strings in team_a and team_b.
        """
        result = _call_predict_matchup(region_a=region_a, region_b=region_b)
        assert result["team_a"]["region"] == region_a
        assert result["team_b"]["region"] == region_b

    def test_predict_matchup_west_south_regions(self):
        """Unit test: West and South regions are preserved in the returned dict."""
        result = _call_predict_matchup(region_a="West", region_b="South")
        assert result["team_a"]["region"] == "West"
        assert result["team_b"]["region"] == "South"

    def test_predict_matchup_unrecognized_region_defaults_to_east(self):
        """Unit test: Unrecognized region string defaults to East."""
        result = _call_predict_matchup(region_a="InvalidRegion", region_b="East")
        assert result["team_a"]["region"] == "East"

    def test_predict_matchup_default_region_is_east(self):
        """Unit test: Omitting region params defaults both teams to East."""
        result = _call_predict_matchup()
        assert result["team_a"]["region"] == "East"
        assert result["team_b"]["region"] == "East"
