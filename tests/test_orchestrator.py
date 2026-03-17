"""Unit tests for OrchestratorAgent round advancement logic.

Tests cover:
- advance_winners: winners from one round populate next round matchups
- _build_bracket_output: championship round produces complete BracketOutput
- _reconstruct_matchups_from_prior: resume-from-round with prior results

Requirements: 10.1, 10.4, 10.5, 1.5
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

# strands, strands.models, and sub-agent stubs are registered by conftest.py.
# We only need to stub the modules that OrchestratorAgent directly imports
# but that are NOT covered by conftest (bracket_review, matchup_analyst,
# player_injury, prediction) — these need to be present before the import.
for _mod in [
    "src.agents.bracket_review",
    "src.agents.matchup_analyst",
    "src.agents.player_injury",
    "src.agents.prediction",
]:
    sys.modules.setdefault(_mod, MagicMock())

from src.models.enums import Region, RoundName  # noqa: E402
from src.models.output import BracketOutput, RoundResult  # noqa: E402
from src.models.prediction import Prediction  # noqa: E402
from src.models.team import Matchup, Team  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_team(name: str, seed: int, region: Region = Region.EAST) -> Team:
    return Team(name=name, seed=seed, region=region)


def _make_prediction(
    team_a: Team,
    team_b: Team,
    winner_name: str,
    round_name: RoundName = RoundName.ROUND_OF_64,
    confidence: int = 75,
) -> Prediction:
    """Build a minimal valid Prediction using Prediction.from_dict()."""
    return Prediction.from_dict(
        {
            "team_a": team_a.to_dict(),
            "team_b": team_b.to_dict(),
            "winner": winner_name,
            "confidence": confidence,
            "rationale": "Team A is stronger. Their defense is elite.",
            "key_factors": ["Defense", "Rebounding"],
            "upset_alert": False,
            "round_name": round_name.value,
        }
    )


def _make_round_result(
    round_name: RoundName,
    predictions: list[Prediction],
) -> RoundResult:
    upset_count = sum(1 for p in predictions if p.upset_alert)
    cinderella = [
        p.winner
        for p in predictions
        if (p.winner == p.team_a.name and p.team_a.seed >= 11)
        or (p.winner == p.team_b.name and p.team_b.seed >= 11)
    ]
    return RoundResult(
        round_name=round_name,
        matchups=predictions,
        upset_count=upset_count,
        cinderella_candidates=cinderella,
    )


# Import OrchestratorAgent after mocks are in place.
# Since test_cli.py no longer inserts a MagicMock for src.agents.orchestrator
# at module level, no sys.modules.pop is needed here.

with patch("strands.Agent", MagicMock()), patch("strands.models.BedrockModel", MagicMock()):
    from src.agents.orchestrator import OrchestratorAgent  # noqa: E402


def _make_orchestrator() -> OrchestratorAgent:
    """Create an OrchestratorAgent without touching AWS."""
    with patch("strands.Agent", MagicMock()), patch("strands.models.BedrockModel", MagicMock()):
        return OrchestratorAgent()


# ---------------------------------------------------------------------------
# Test 1 – advance_winners
# ---------------------------------------------------------------------------


class TestAdvanceWinners(unittest.TestCase):
    """Test that winners from one round correctly populate next round matchups.

    Requirements: 10.4
    """

    def setUp(self) -> None:
        self.orch = _make_orchestrator()

    def _four_predictions_team_a_wins(self) -> list[Prediction]:
        """Create 4 predictions where team_a wins each."""
        teams = [
            (_make_team("Alpha", 1), _make_team("Alpha16", 16)),
            (_make_team("Beta", 2), _make_team("Beta15", 15)),
            (_make_team("Gamma", 3), _make_team("Gamma14", 14)),
            (_make_team("Delta", 4), _make_team("Delta13", 13)),
        ]
        return [
            _make_prediction(a, b, a.name, RoundName.ROUND_OF_64)
            for a, b in teams
        ]

    def test_advance_winners_returns_two_matchups(self) -> None:
        """4 predictions → 2 next-round matchups."""
        predictions = self._four_predictions_team_a_wins()
        matchups = self.orch.advance_winners(RoundName.ROUND_OF_64.value, predictions)
        self.assertEqual(len(matchups), 2)

    def test_advance_winners_pairs_sequentially(self) -> None:
        """winner[0] vs winner[1] and winner[2] vs winner[3]."""
        predictions = self._four_predictions_team_a_wins()
        matchups = self.orch.advance_winners(RoundName.ROUND_OF_64.value, predictions)

        # First matchup: Alpha vs Beta
        self.assertEqual(matchups[0].team_a.name, "Alpha")
        self.assertEqual(matchups[0].team_b.name, "Beta")

        # Second matchup: Gamma vs Delta
        self.assertEqual(matchups[1].team_a.name, "Gamma")
        self.assertEqual(matchups[1].team_b.name, "Delta")

    def test_advance_winners_next_round_is_round_of_32(self) -> None:
        """After Round of 64, next round should be Round of 32."""
        predictions = self._four_predictions_team_a_wins()
        matchups = self.orch.advance_winners(RoundName.ROUND_OF_64.value, predictions)

        for matchup in matchups:
            self.assertEqual(matchup.round_name, RoundName.ROUND_OF_32)

    def test_advance_winners_returns_matchup_objects(self) -> None:
        """Returned items are Matchup instances."""
        predictions = self._four_predictions_team_a_wins()
        matchups = self.orch.advance_winners(RoundName.ROUND_OF_64.value, predictions)

        for matchup in matchups:
            self.assertIsInstance(matchup, Matchup)

    def test_advance_winners_championship_returns_empty(self) -> None:
        """Championship is the last round – no next round matchups."""
        team_a = _make_team("FinalA", 1)
        team_b = _make_team("FinalB", 2)
        predictions = [_make_prediction(team_a, team_b, team_a.name, RoundName.CHAMPIONSHIP)]
        matchups = self.orch.advance_winners(RoundName.CHAMPIONSHIP.value, predictions)
        self.assertEqual(matchups, [])


# ---------------------------------------------------------------------------
# Test 2 – _build_bracket_output
# ---------------------------------------------------------------------------

# All 6 rounds in order
_ALL_ROUNDS = [
    RoundName.ROUND_OF_64,
    RoundName.ROUND_OF_32,
    RoundName.SWEET_16,
    RoundName.ELITE_8,
    RoundName.FINAL_FOUR,
    RoundName.CHAMPIONSHIP,
]


def _build_six_round_results(champion_name: str = "Champion") -> list[RoundResult]:
    """Build one RoundResult per round, champion wins every game."""
    champ_seed = 1
    results = []
    for round_name in _ALL_ROUNDS:
        opponent = _make_team(f"Opponent_{round_name.value}", 8)
        champ = _make_team(champion_name, champ_seed)
        pred = _make_prediction(champ, opponent, champion_name, round_name)
        results.append(_make_round_result(round_name, [pred]))
    return results


class TestBuildBracketOutput(unittest.TestCase):
    """Test that _build_bracket_output produces a complete BracketOutput.

    Requirements: 10.5
    """

    def setUp(self) -> None:
        self.orch = _make_orchestrator()
        self.champion_name = "Champion"
        self.round_results = _build_six_round_results(self.champion_name)
        self.output = self.orch._build_bracket_output(self.round_results)

    def test_returns_bracket_output_instance(self) -> None:
        """Result is a BracketOutput."""
        self.assertIsInstance(self.output, BracketOutput)

    def test_champion_is_set_correctly(self) -> None:
        """Champion name matches the winner of the championship matchup."""
        self.assertEqual(self.output.champion, self.champion_name)

    def test_champion_path_has_six_entries(self) -> None:
        """Champion path has one entry per round (6 total)."""
        self.assertEqual(len(self.output.champion_path), 6)

    def test_champion_path_contains_opponents(self) -> None:
        """Each entry in champion_path is an opponent name (not the champion)."""
        for opponent in self.output.champion_path:
            self.assertNotEqual(opponent, self.champion_name)

    def test_upset_alerts_is_list(self) -> None:
        """upset_alerts is a list."""
        self.assertIsInstance(self.output.upset_alerts, list)

    def test_cinderella_watch_is_list(self) -> None:
        """cinderella_watch is a list."""
        self.assertIsInstance(self.output.cinderella_watch, list)

    def test_all_rounds_included(self) -> None:
        """All 6 rounds are present in the output."""
        self.assertEqual(len(self.output.rounds), 6)

    def test_champion_confidence_set(self) -> None:
        """Champion confidence is a valid value (50-99)."""
        self.assertGreaterEqual(self.output.champion_confidence, 50)
        self.assertLessEqual(self.output.champion_confidence, 99)

    def test_upset_alerts_populated_for_upsets(self) -> None:
        """Upset alerts are collected when upsets occur."""
        # Build a round result with an upset (lower seed wins)
        favorite = _make_team("Favorite", 1)
        underdog = _make_team("Underdog", 12)
        upset_pred = _make_prediction(favorite, underdog, "Underdog", RoundName.ROUND_OF_64)
        # upset_alert is auto-calculated; underdog seed 12 > favorite seed 1 → upset
        round_with_upset = _make_round_result(RoundName.ROUND_OF_64, [upset_pred])

        # Championship to set champion
        champ_a = _make_team("Underdog", 12)
        champ_b = _make_team("Other", 2)
        champ_pred = _make_prediction(champ_a, champ_b, "Underdog", RoundName.CHAMPIONSHIP)
        champ_round = _make_round_result(RoundName.CHAMPIONSHIP, [champ_pred])

        output = self.orch._build_bracket_output([round_with_upset, champ_round])
        self.assertGreater(len(output.upset_alerts), 0)


# ---------------------------------------------------------------------------
# Test 3 – _reconstruct_matchups_from_prior
# ---------------------------------------------------------------------------


class TestReconstructMatchupsFromPrior(unittest.TestCase):
    """Test resume-from-round functionality with prior results.

    Requirements: 1.5, 10.1
    """

    def setUp(self) -> None:
        self.orch = _make_orchestrator()

    def _make_r64_prior_results(self) -> dict:
        """Create prior_results dict with Round of 64 predictions (4 games)."""
        teams = [
            (_make_team("A1", 1), _make_team("A16", 16)),
            (_make_team("B2", 2), _make_team("B15", 15)),
            (_make_team("C3", 3), _make_team("C14", 14)),
            (_make_team("D4", 4), _make_team("D13", 13)),
        ]
        predictions = [
            _make_prediction(a, b, a.name, RoundName.ROUND_OF_64)
            for a, b in teams
        ]
        return {
            RoundName.ROUND_OF_64.value: [p.to_dict() for p in predictions]
        }

    def test_reconstruct_returns_matchups(self) -> None:
        """Reconstructed matchups list is non-empty."""
        prior = self._make_r64_prior_results()
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_32.value, prior
        )
        self.assertGreater(len(matchups), 0)

    def test_reconstruct_matchup_count(self) -> None:
        """4 R64 winners → 2 R32 matchups."""
        prior = self._make_r64_prior_results()
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_32.value, prior
        )
        self.assertEqual(len(matchups), 2)

    def test_reconstruct_matchups_are_matchup_objects(self) -> None:
        """Reconstructed items are Matchup instances."""
        prior = self._make_r64_prior_results()
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_32.value, prior
        )
        for matchup in matchups:
            self.assertIsInstance(matchup, Matchup)

    def test_reconstruct_uses_prior_winners(self) -> None:
        """Reconstructed matchups contain the winners from prior round."""
        prior = self._make_r64_prior_results()
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_32.value, prior
        )
        # All team_a winners from R64 were seeds 1-4 (A1, B2, C3, D4)
        all_team_names = {m.team_a.name for m in matchups} | {m.team_b.name for m in matchups}
        self.assertIn("A1", all_team_names)
        self.assertIn("B2", all_team_names)
        self.assertIn("C3", all_team_names)
        self.assertIn("D4", all_team_names)

    def test_reconstruct_round_of_64_returns_empty(self) -> None:
        """Reconstructing Round of 64 (first round) returns empty list."""
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_64.value, {}
        )
        self.assertEqual(matchups, [])

    def test_reconstruct_empty_prior_returns_empty(self) -> None:
        """Empty prior_results returns empty list."""
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_32.value, {}
        )
        self.assertEqual(matchups, [])

    def test_reconstruct_correct_round_name_on_matchups(self) -> None:
        """Reconstructed matchups have the correct target round name."""
        prior = self._make_r64_prior_results()
        matchups = self.orch._reconstruct_matchups_from_prior(
            RoundName.ROUND_OF_32.value, prior
        )
        for matchup in matchups:
            self.assertEqual(matchup.round_name, RoundName.ROUND_OF_32)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Test 4 – TD-006: OrchestratorAgent init does not connect to Bedrock
# ---------------------------------------------------------------------------


class TestOrchestratorAgentInitNoBedrock(unittest.TestCase):
    """Property 10: OrchestratorAgent init does not connect to Bedrock.

    Requirements: 9.4, 9.5
    """

    def test_init_completes_without_aws_credentials(self) -> None:
        """OrchestratorAgent() must complete without raising any AWS-related exception."""
        import os
        # Temporarily unset AWS env vars to simulate no credentials
        env_backup = {
            k: os.environ.pop(k, None)
            for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                      "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION")
        }
        try:
            agent = OrchestratorAgent()  # must not raise
            self.assertIsNotNone(agent)
        finally:
            for k, v in env_backup.items():
                if v is not None:
                    os.environ[k] = v

    def test_init_has_no_agent_attribute(self) -> None:
        """OrchestratorAgent instance must not have a self.agent attribute.

        Requirements: 9.1, 9.5
        """
        agent = OrchestratorAgent()
        self.assertFalse(
            hasattr(agent, "agent"),
            "OrchestratorAgent should not have a self.agent attribute",
        )

    def test_init_has_no_model_id_attribute(self) -> None:
        """OrchestratorAgent instance must not have a model_id attribute.

        Requirements: 9.2
        """
        agent = OrchestratorAgent()
        self.assertFalse(
            hasattr(agent, "model_id"),
            "OrchestratorAgent should not have a model_id attribute",
        )

    def test_invocation_state_initialized(self) -> None:
        """invocation_state is initialized with expected keys."""
        agent = OrchestratorAgent()
        self.assertIn("bracket", agent.invocation_state)
        self.assertIn("current_round", agent.invocation_state)
        self.assertIn("completed_rounds", agent.invocation_state)
        self.assertIn("team_cache", agent.invocation_state)


if __name__ == "__main__":
    unittest.main()
