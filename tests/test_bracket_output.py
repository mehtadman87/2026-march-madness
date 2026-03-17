"""Unit tests for BracketOutput JSON serialization.

**Validates: Requirements 12.1, 12.2, 12.3**

Tests that BracketOutput.to_json() produces valid JSON with all required fields
including matchups, upset alerts, cinderella watch, and champion information.
"""

import json
import pytest

from src.models.enums import Region, RoundName
from src.models.team import Team
from src.models.prediction import Prediction
from src.models.output import RoundResult, BracketOutput


# --- Fixtures ---


@pytest.fixture
def team_duke() -> Team:
    """Create Duke team fixture (1 seed)."""
    return Team(name="Duke", seed=1, region=Region.EAST)


@pytest.fixture
def team_underdog() -> Team:
    """Create underdog team fixture (16 seed)."""
    return Team(name="Underdog State", seed=16, region=Region.EAST)


@pytest.fixture
def team_cinderella() -> Team:
    """Create Cinderella team fixture (12 seed)."""
    return Team(name="Cinderella U", seed=12, region=Region.SOUTH)


@pytest.fixture
def team_favorite() -> Team:
    """Create favorite team fixture (5 seed)."""
    return Team(name="Favorite State", seed=5, region=Region.SOUTH)


@pytest.fixture
def team_kansas() -> Team:
    """Create Kansas team fixture (2 seed)."""
    return Team(name="Kansas", seed=2, region=Region.WEST)


@pytest.fixture
def team_mid_major() -> Team:
    """Create mid-major team fixture (15 seed)."""
    return Team(name="Mid Major", seed=15, region=Region.WEST)


@pytest.fixture
def prediction_no_upset(team_duke, team_underdog) -> Prediction:
    """Create a prediction where the higher seed wins (no upset)."""
    return Prediction(
        team_a=team_duke,
        team_b=team_underdog,
        winner="Duke",
        confidence=95,
        rationale="Duke has superior talent and experience. Their depth will be decisive.",
        key_factors=["Talent advantage", "Tournament experience", "Depth"],
        upset_alert=False,
        round_name=RoundName.ROUND_OF_64,
    )


@pytest.fixture
def prediction_upset(team_favorite, team_cinderella) -> Prediction:
    """Create a prediction where the lower seed wins (upset)."""
    return Prediction(
        team_a=team_favorite,
        team_b=team_cinderella,
        winner="Cinderella U",
        confidence=55,
        rationale="Cinderella U is playing their best basketball. Their momentum is undeniable.",
        key_factors=["Hot shooting", "Momentum", "Favorable matchup"],
        upset_alert=True,  # Will be auto-calculated
        round_name=RoundName.ROUND_OF_64,
    )


@pytest.fixture
def prediction_kansas(team_kansas, team_mid_major) -> Prediction:
    """Create a prediction for Kansas game."""
    return Prediction(
        team_a=team_kansas,
        team_b=team_mid_major,
        winner="Kansas",
        confidence=88,
        rationale="Kansas has too much firepower. Their defense will stifle the opponent.",
        key_factors=["Offensive efficiency", "Defensive pressure"],
        upset_alert=False,
        round_name=RoundName.ROUND_OF_64,
    )


@pytest.fixture
def round_result_r64(prediction_no_upset, prediction_upset, prediction_kansas) -> RoundResult:
    """Create a Round of 64 result with multiple matchups."""
    return RoundResult(
        round_name=RoundName.ROUND_OF_64,
        matchups=[prediction_no_upset, prediction_upset, prediction_kansas],
        upset_count=1,
        cinderella_candidates=["Cinderella U"],
    )



@pytest.fixture
def round_result_r32(team_duke, team_cinderella) -> RoundResult:
    """Create a Round of 32 result."""
    prediction = Prediction(
        team_a=team_duke,
        team_b=team_cinderella,
        winner="Duke",
        confidence=75,
        rationale="Duke's experience prevails. Cinderella's run ends here.",
        key_factors=["Experience", "Depth", "Coaching"],
        upset_alert=False,
        round_name=RoundName.ROUND_OF_32,
    )
    return RoundResult(
        round_name=RoundName.ROUND_OF_32,
        matchups=[prediction],
        upset_count=0,
        cinderella_candidates=[],
    )


@pytest.fixture
def sample_bracket_output(round_result_r64, round_result_r32) -> BracketOutput:
    """Create a sample BracketOutput with multiple rounds."""
    return BracketOutput(
        champion="Duke",
        champion_confidence=85,
        champion_path=["Underdog State", "Cinderella U", "Kansas", "UNC", "Gonzaga", "Kentucky"],
        rounds=[round_result_r64, round_result_r32],
        upset_alerts=[
            {
                "round": "Round of 64",
                "winner": "Cinderella U",
                "winner_seed": 12,
                "loser": "Favorite State",
                "loser_seed": 5,
            }
        ],
        cinderella_watch=[
            {
                "team": "Cinderella U",
                "seed": 12,
                "furthest_round": "Round of 32",
            }
        ],
    )


# --- Test Classes ---


class TestBracketOutputToJson:
    """Tests for BracketOutput.to_json() method.

    **Validates: Requirements 12.1, 12.2, 12.3**
    """

    def test_to_json_produces_valid_json(self, sample_bracket_output: BracketOutput) -> None:
        """Test that to_json() produces valid JSON string.

        **Validates: Requirements 12.1**
        """
        json_str = sample_bracket_output.to_json()
        
        # Should not raise - valid JSON
        parsed = json.loads(json_str)
        
        assert isinstance(parsed, dict)

    def test_to_json_includes_champion(self, sample_bracket_output: BracketOutput) -> None:
        """Test that to_json() includes champion name.

        **Validates: Requirements 12.1**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert "champion" in parsed
        assert parsed["champion"] == "Duke"

    def test_to_json_includes_champion_confidence(self, sample_bracket_output: BracketOutput) -> None:
        """Test that to_json() includes champion confidence score.

        **Validates: Requirements 12.1**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert "champion_confidence" in parsed
        assert parsed["champion_confidence"] == 85

    def test_to_json_includes_champion_path(self, sample_bracket_output: BracketOutput) -> None:
        """Test that to_json() includes champion path through all rounds.

        **Validates: Requirements 12.1**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert "champion_path" in parsed
        assert isinstance(parsed["champion_path"], list)
        assert len(parsed["champion_path"]) == 6
        assert parsed["champion_path"][0] == "Underdog State"

    def test_to_json_includes_rounds(self, sample_bracket_output: BracketOutput) -> None:
        """Test that to_json() includes all rounds.

        **Validates: Requirements 12.1**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert "rounds" in parsed
        assert isinstance(parsed["rounds"], list)
        assert len(parsed["rounds"]) == 2

    def test_to_json_round_includes_round_name(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each round includes round_name.

        **Validates: Requirements 12.1**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            assert "round_name" in round_data
            assert round_data["round_name"] in [r.value for r in RoundName]


class TestMatchupFieldsInJson:
    """Tests for matchup fields in JSON output.

    **Validates: Requirements 12.2**
    """

    def test_matchup_includes_team_names_and_seeds(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each matchup includes both team names and seeds.

        **Validates: Requirements 12.2**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            for matchup in round_data["matchups"]:
                # Team A
                assert "team_a" in matchup
                assert "name" in matchup["team_a"]
                assert "seed" in matchup["team_a"]
                assert isinstance(matchup["team_a"]["seed"], int)
                
                # Team B
                assert "team_b" in matchup
                assert "name" in matchup["team_b"]
                assert "seed" in matchup["team_b"]
                assert isinstance(matchup["team_b"]["seed"], int)

    def test_matchup_includes_predicted_winner(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each matchup includes predicted winner.

        **Validates: Requirements 12.2**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            for matchup in round_data["matchups"]:
                assert "winner" in matchup
                assert isinstance(matchup["winner"], str)
                # Winner should be one of the team names
                assert matchup["winner"] in [matchup["team_a"]["name"], matchup["team_b"]["name"]]

    def test_matchup_includes_confidence_score(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each matchup includes confidence score (50-99).

        **Validates: Requirements 12.2**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            for matchup in round_data["matchups"]:
                assert "confidence" in matchup
                assert isinstance(matchup["confidence"], int)
                assert 50 <= matchup["confidence"] <= 99

    def test_matchup_includes_rationale(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each matchup includes text rationale.

        **Validates: Requirements 12.2**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            for matchup in round_data["matchups"]:
                assert "rationale" in matchup
                assert isinstance(matchup["rationale"], str)
                assert len(matchup["rationale"]) > 0

    def test_matchup_includes_key_factors(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each matchup includes key factors list.

        **Validates: Requirements 12.2**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            for matchup in round_data["matchups"]:
                assert "key_factors" in matchup
                assert isinstance(matchup["key_factors"], list)
                assert len(matchup["key_factors"]) > 0
                for factor in matchup["key_factors"]:
                    assert isinstance(factor, str)

    def test_matchup_includes_upset_alert(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each matchup includes upset_alert flag.

        **Validates: Requirements 12.2**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for round_data in parsed["rounds"]:
            for matchup in round_data["matchups"]:
                assert "upset_alert" in matchup
                assert isinstance(matchup["upset_alert"], bool)


class TestUpsetAlertsAndCinderellaWatch:
    """Tests for upset_alerts and cinderella_watch in JSON output.

    **Validates: Requirements 12.3**
    """

    def test_json_includes_upset_alerts_summary(self, sample_bracket_output: BracketOutput) -> None:
        """Test that JSON includes upset_alerts summary listing all upsets.

        **Validates: Requirements 12.3**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert "upset_alerts" in parsed
        assert isinstance(parsed["upset_alerts"], list)
        assert len(parsed["upset_alerts"]) == 1

    def test_upset_alert_contains_required_fields(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each upset alert contains round, winner, loser info.

        **Validates: Requirements 12.3**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for alert in parsed["upset_alerts"]:
            assert "round" in alert
            assert "winner" in alert
            assert "winner_seed" in alert
            assert "loser" in alert
            assert "loser_seed" in alert

    def test_upset_alert_values_are_correct(self, sample_bracket_output: BracketOutput) -> None:
        """Test that upset alert values match expected data.

        **Validates: Requirements 12.3**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        alert = parsed["upset_alerts"][0]
        assert alert["round"] == "Round of 64"
        assert alert["winner"] == "Cinderella U"
        assert alert["winner_seed"] == 12
        assert alert["loser"] == "Favorite State"
        assert alert["loser_seed"] == 5

    def test_json_includes_cinderella_watch_list(self, sample_bracket_output: BracketOutput) -> None:
        """Test that JSON includes cinderella_watch list.

        **Validates: Requirements 12.3**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert "cinderella_watch" in parsed
        assert isinstance(parsed["cinderella_watch"], list)
        assert len(parsed["cinderella_watch"]) == 1

    def test_cinderella_watch_contains_required_fields(self, sample_bracket_output: BracketOutput) -> None:
        """Test that each cinderella entry contains team, seed, furthest_round.

        **Validates: Requirements 12.3**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        for cinderella in parsed["cinderella_watch"]:
            assert "team" in cinderella
            assert "seed" in cinderella
            assert "furthest_round" in cinderella

    def test_cinderella_watch_values_are_correct(self, sample_bracket_output: BracketOutput) -> None:
        """Test that cinderella watch values match expected data.

        **Validates: Requirements 12.3**
        """
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        
        cinderella = parsed["cinderella_watch"][0]
        assert cinderella["team"] == "Cinderella U"
        assert cinderella["seed"] == 12
        assert cinderella["furthest_round"] == "Round of 32"

    def test_empty_upset_alerts_when_no_upsets(self) -> None:
        """Test that upset_alerts is empty list when no upsets predicted.

        **Validates: Requirements 12.3**
        """
        team_a = Team(name="Duke", seed=1, region=Region.EAST)
        team_b = Team(name="Underdog", seed=16, region=Region.EAST)
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=95,
            rationale="Duke dominates. No contest here.",
            key_factors=["Talent"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
        )
        round_result = RoundResult(
            round_name=RoundName.ROUND_OF_64,
            matchups=[prediction],
            upset_count=0,
            cinderella_candidates=[],
        )
        bracket_output = BracketOutput(
            champion="Duke",
            champion_confidence=90,
            champion_path=["Underdog"],
            rounds=[round_result],
            upset_alerts=[],
            cinderella_watch=[],
        )
        
        json_str = bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["upset_alerts"] == []
        assert parsed["cinderella_watch"] == []



class TestToConsoleSummary:
    """Tests for BracketOutput.to_console_summary() method.

    **Validates: Requirements 12.4**
    """

    def test_console_summary_returns_string(self, sample_bracket_output: BracketOutput) -> None:
        """Test that to_console_summary() returns a string."""
        summary = sample_bracket_output.to_console_summary()
        assert isinstance(summary, str)

    def test_console_summary_includes_header(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes header."""
        summary = sample_bracket_output.to_console_summary()
        assert "MARCH MADNESS BRACKET PREDICTIONS" in summary

    def test_console_summary_includes_round_names(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes round names."""
        summary = sample_bracket_output.to_console_summary()
        assert "ROUND OF 64" in summary
        assert "ROUND OF 32" in summary

    def test_console_summary_includes_matchup_details(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes matchup details with teams and seeds."""
        summary = sample_bracket_output.to_console_summary()
        
        # Check for team names with seeds
        assert "(1) Duke" in summary
        assert "(16) Underdog State" in summary
        assert "vs" in summary

    def test_console_summary_includes_winner_and_confidence(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary shows winner with confidence percentage."""
        summary = sample_bracket_output.to_console_summary()
        
        # Check for winner format with confidence
        assert "Winner:" in summary
        assert "%" in summary

    def test_console_summary_includes_key_factors(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes key factors."""
        summary = sample_bracket_output.to_console_summary()
        assert "Key factors:" in summary

    def test_console_summary_includes_upset_marker(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary marks upsets with indicator."""
        summary = sample_bracket_output.to_console_summary()
        # The upset marker emoji should appear for Cinderella U upset
        assert "UPSET" in summary

    def test_console_summary_includes_champion_section(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes champion section."""
        summary = sample_bracket_output.to_console_summary()
        
        assert "TOURNAMENT CHAMPION" in summary
        assert "Champion: Duke" in summary
        assert "Confidence: 85%" in summary

    def test_console_summary_includes_champion_path(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes champion's path to victory."""
        summary = sample_bracket_output.to_console_summary()
        assert "Path to victory:" in summary

    def test_console_summary_includes_upset_alerts_section(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes upset alerts section."""
        summary = sample_bracket_output.to_console_summary()
        assert "ALL UPSET ALERTS" in summary

    def test_console_summary_includes_cinderella_watch_section(self, sample_bracket_output: BracketOutput) -> None:
        """Test that console summary includes Cinderella watch section."""
        summary = sample_bracket_output.to_console_summary()
        assert "CINDERELLA WATCH" in summary

    def test_console_summary_no_upset_alerts_when_empty(self) -> None:
        """Test that console summary omits upset alerts section when empty."""
        team_a = Team(name="Duke", seed=1, region=Region.EAST)
        team_b = Team(name="Underdog", seed=16, region=Region.EAST)
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=95,
            rationale="Duke dominates. No contest here.",
            key_factors=["Talent"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
        )
        round_result = RoundResult(
            round_name=RoundName.ROUND_OF_64,
            matchups=[prediction],
            upset_count=0,
            cinderella_candidates=[],
        )
        bracket_output = BracketOutput(
            champion="Duke",
            champion_confidence=90,
            champion_path=["Underdog"],
            rounds=[round_result],
            upset_alerts=[],
            cinderella_watch=[],
        )
        
        summary = bracket_output.to_console_summary()
        # When no upsets, the section should not appear
        assert "ALL UPSET ALERTS" not in summary


class TestRoundResultSerialization:
    """Tests for RoundResult serialization."""

    def test_round_result_to_dict(self, round_result_r64: RoundResult) -> None:
        """Test RoundResult.to_dict() produces correct structure."""
        result = round_result_r64.to_dict()
        
        assert result["round_name"] == "Round of 64"
        assert result["upset_count"] == 1
        assert result["cinderella_candidates"] == ["Cinderella U"]
        assert len(result["matchups"]) == 3

    def test_round_result_from_dict(self, round_result_r64: RoundResult) -> None:
        """Test RoundResult.from_dict() creates correct object."""
        data = round_result_r64.to_dict()
        restored = RoundResult.from_dict(data)
        
        assert restored.round_name == round_result_r64.round_name
        assert restored.upset_count == round_result_r64.upset_count
        assert restored.cinderella_candidates == round_result_r64.cinderella_candidates
        assert len(restored.matchups) == len(round_result_r64.matchups)

    def test_round_result_round_trip(self, round_result_r64: RoundResult) -> None:
        """Test RoundResult round-trip serialization."""
        data = round_result_r64.to_dict()
        restored = RoundResult.from_dict(data)
        
        # Verify all matchups are preserved
        for orig, rest in zip(round_result_r64.matchups, restored.matchups):
            assert rest.winner == orig.winner
            assert rest.confidence == orig.confidence
            assert rest.upset_alert == orig.upset_alert


class TestBracketOutputSerialization:
    """Tests for BracketOutput serialization."""

    def test_bracket_output_to_dict(self, sample_bracket_output: BracketOutput) -> None:
        """Test BracketOutput.to_dict() produces correct structure."""
        result = sample_bracket_output.to_dict()
        
        assert result["champion"] == "Duke"
        assert result["champion_confidence"] == 85
        assert len(result["champion_path"]) == 6
        assert len(result["rounds"]) == 2
        assert len(result["upset_alerts"]) == 1
        assert len(result["cinderella_watch"]) == 1

    def test_bracket_output_from_dict(self, sample_bracket_output: BracketOutput) -> None:
        """Test BracketOutput.from_dict() creates correct object."""
        data = sample_bracket_output.to_dict()
        restored = BracketOutput.from_dict(data)
        
        assert restored.champion == sample_bracket_output.champion
        assert restored.champion_confidence == sample_bracket_output.champion_confidence
        assert restored.champion_path == sample_bracket_output.champion_path
        assert len(restored.rounds) == len(sample_bracket_output.rounds)
        assert restored.upset_alerts == sample_bracket_output.upset_alerts
        assert restored.cinderella_watch == sample_bracket_output.cinderella_watch

    def test_bracket_output_round_trip(self, sample_bracket_output: BracketOutput) -> None:
        """Test BracketOutput round-trip serialization."""
        data = sample_bracket_output.to_dict()
        restored = BracketOutput.from_dict(data)
        
        # Verify champion info
        assert restored.champion == sample_bracket_output.champion
        assert restored.champion_confidence == sample_bracket_output.champion_confidence
        
        # Verify rounds
        for orig_round, rest_round in zip(sample_bracket_output.rounds, restored.rounds):
            assert rest_round.round_name == orig_round.round_name
            assert rest_round.upset_count == orig_round.upset_count
            assert len(rest_round.matchups) == len(orig_round.matchups)

    def test_to_json_and_parse_round_trip(self, sample_bracket_output: BracketOutput) -> None:
        """Test full JSON string round-trip."""
        json_str = sample_bracket_output.to_json()
        parsed = json.loads(json_str)
        restored = BracketOutput.from_dict(parsed)
        
        assert restored.champion == sample_bracket_output.champion
        assert restored.champion_confidence == sample_bracket_output.champion_confidence
        assert len(restored.rounds) == len(sample_bracket_output.rounds)


class TestEdgeCases:
    """Tests for edge cases in BracketOutput serialization."""

    def test_single_round_bracket_output(self) -> None:
        """Test BracketOutput with only one round."""
        team_a = Team(name="Duke", seed=1, region=Region.EAST)
        team_b = Team(name="UNC", seed=2, region=Region.EAST)
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=60,
            rationale="Close game expected. Duke edges it out.",
            key_factors=["Home court"],
            upset_alert=False,
            round_name=RoundName.CHAMPIONSHIP,
        )
        round_result = RoundResult(
            round_name=RoundName.CHAMPIONSHIP,
            matchups=[prediction],
            upset_count=0,
            cinderella_candidates=[],
        )
        bracket_output = BracketOutput(
            champion="Duke",
            champion_confidence=60,
            champion_path=["UNC"],
            rounds=[round_result],
            upset_alerts=[],
            cinderella_watch=[],
        )
        
        json_str = bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["champion"] == "Duke"
        assert len(parsed["rounds"]) == 1
        assert parsed["rounds"][0]["round_name"] == "Championship"

    def test_multiple_upsets_in_bracket(self) -> None:
        """Test BracketOutput with multiple upsets."""
        team_1 = Team(name="Favorite1", seed=1, region=Region.EAST)
        team_16 = Team(name="Underdog1", seed=16, region=Region.EAST)
        team_2 = Team(name="Favorite2", seed=2, region=Region.WEST)
        team_15 = Team(name="Underdog2", seed=15, region=Region.WEST)
        
        prediction1 = Prediction(
            team_a=team_1,
            team_b=team_16,
            winner="Underdog1",
            confidence=51,
            rationale="Historic upset brewing. Underdog1 has the magic.",
            key_factors=["Momentum"],
            upset_alert=True,
            round_name=RoundName.ROUND_OF_64,
        )
        prediction2 = Prediction(
            team_a=team_2,
            team_b=team_15,
            winner="Underdog2",
            confidence=52,
            rationale="Another upset coming. Underdog2 is hot.",
            key_factors=["Hot shooting"],
            upset_alert=True,
            round_name=RoundName.ROUND_OF_64,
        )
        
        round_result = RoundResult(
            round_name=RoundName.ROUND_OF_64,
            matchups=[prediction1, prediction2],
            upset_count=2,
            cinderella_candidates=["Underdog1", "Underdog2"],
        )
        
        bracket_output = BracketOutput(
            champion="Underdog1",
            champion_confidence=51,
            champion_path=["Favorite1"],
            rounds=[round_result],
            upset_alerts=[
                {"round": "Round of 64", "winner": "Underdog1", "winner_seed": 16, "loser": "Favorite1", "loser_seed": 1},
                {"round": "Round of 64", "winner": "Underdog2", "winner_seed": 15, "loser": "Favorite2", "loser_seed": 2},
            ],
            cinderella_watch=[
                {"team": "Underdog1", "seed": 16, "furthest_round": "Round of 32"},
                {"team": "Underdog2", "seed": 15, "furthest_round": "Round of 32"},
            ],
        )
        
        json_str = bracket_output.to_json()
        parsed = json.loads(json_str)
        
        assert len(parsed["upset_alerts"]) == 2
        assert len(parsed["cinderella_watch"]) == 2

    def test_matchup_with_weight_adjustments(self) -> None:
        """Test that weight_adjustments are included in JSON when present."""
        team_a = Team(name="Duke", seed=1, region=Region.EAST)
        team_b = Team(name="Underdog", seed=16, region=Region.EAST)
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            winner="Duke",
            confidence=85,
            rationale="Duke has superior talent. Their experience will be decisive.",
            key_factors=["Talent"],
            upset_alert=False,
            round_name=RoundName.ROUND_OF_64,
            weight_adjustments={"efficiency_margin": 0.30, "matchup_factors": 0.25},
        )
        round_result = RoundResult(
            round_name=RoundName.ROUND_OF_64,
            matchups=[prediction],
            upset_count=0,
            cinderella_candidates=[],
        )
        bracket_output = BracketOutput(
            champion="Duke",
            champion_confidence=85,
            champion_path=["Underdog"],
            rounds=[round_result],
            upset_alerts=[],
            cinderella_watch=[],
        )
        
        json_str = bracket_output.to_json()
        parsed = json.loads(json_str)
        
        matchup = parsed["rounds"][0]["matchups"][0]
        assert "weight_adjustments" in matchup
        assert matchup["weight_adjustments"]["efficiency_margin"] == 0.30
