"""Orchestrator Agent for March Madness Bracket Predictor.

Top-level coordinator that runs the full prediction pipeline across all rounds.
All sub-agent tool functions are invoked as direct Python calls rather than
through an LLM agent loop. This is an intentional design choice: the
orchestration logic is fully deterministic and does not require LLM reasoning
to decide which agents to call or in what order.

Requirements: 10.1, 15.2, 15.3
"""

from __future__ import annotations

import logging
from typing import Any

from strands import tool

from src.agents.advanced_analytics import get_advanced_analytics
from src.agents.bracket_review import review_round
from src.agents.historical_stats import get_historical_comparison
from src.agents.matchup_analyst import analyze_matchup
from src.agents.pdf_parser import parse_bracket
from src.agents.player_injury import assess_players
from src.agents.prediction import predict_matchup
from src.agents.structured_data import get_team_data
from src.agents.team_research import get_qualitative_research
from src.models.enums import Region, RoundName
from src.models.output import BracketOutput, RoundResult
from src.models.prediction import Prediction
from src.models.team import Bracket, Matchup, Team
from src.utils.seed_history import load_seed_history

logger = logging.getLogger(__name__)

# Tournament round progression order (Requirement 10.1)
ROUND_ORDER: list[str] = [
    RoundName.ROUND_OF_64.value,
    RoundName.ROUND_OF_32.value,
    RoundName.SWEET_16.value,
    RoundName.ELITE_8.value,
    RoundName.FINAL_FOUR.value,
    RoundName.CHAMPIONSHIP.value,
]


class OrchestratorAgent:
    """Deterministic pipeline orchestrator for bracket prediction.

    All sub-agent tool functions (get_team_data, predict_matchup, etc.) are
    invoked as direct Python calls rather than through an LLM agent loop.
    This is an intentional design choice: the orchestration logic is fully
    deterministic and does not require LLM reasoning to decide which agents
    to call or in what order.

    Attributes:
        invocation_state: Shared state dict tracking bracket progress.
    """

    def __init__(self) -> None:
        """Initialize the orchestrator. No AWS connection is made at init time.

        Requirements: 10.1, 15.2, 15.3
        """
        # No model_id, no Agent, no BedrockModel — no AWS connection at init time.
        self.invocation_state: dict[str, Any] = {
            "bracket": {},
            "current_round": RoundName.ROUND_OF_64.value,
            "completed_rounds": {},
            "team_cache": {},
            "api_usage": {
                "ncaa_api_calls": 0,
                "cbbd_calls_this_month": 0,
            },
        }

    def process_round(self, round_name: str, matchups: list[Matchup]) -> list[Prediction]:
        """Process all matchups in a single tournament round.

        For each matchup:
          1. get_team_data for both teams
          2. get_qualitative_research for both teams
          3. get_advanced_analytics for both teams
          4. analyze_matchup with both teams + venue
          5. assess_players for both teams
          6. predict_matchup with all gathered data

        After all matchups: invoke review_round, then re-run predict_matchup
        for any flagged matchups with review feedback as additional context.

        Args:
            round_name: Name of the current tournament round.
            matchups: List of Matchup objects for this round.

        Returns:
            List of finalized Prediction objects for the round.

        Requirements: 10.2, 10.3, 10.6, 9.7
        """
        seed_history = load_seed_history()
        predictions_dict: list[dict] = []

        for matchup in matchups:
            team_a = matchup.team_a.name
            team_b = matchup.team_b.name
            seed_a = matchup.team_a.seed
            seed_b = matchup.team_b.seed
            venue = matchup.venue

            logger.info(
                "Processing matchup: (%d) %s vs (%d) %s in %s",
                seed_a, team_a, seed_b, team_b, round_name,
            )

            # Step 1: Structured data (Requirement 10.2, 10.6 - use cache)
            stats_a = self._get_cached_or_fetch(team_a, "stats", get_team_data)
            stats_b = self._get_cached_or_fetch(team_b, "stats", get_team_data)

            # Step 2: Qualitative research
            qual_a = self._get_cached_or_fetch(team_a, "qualitative", get_qualitative_research)
            qual_b = self._get_cached_or_fetch(team_b, "qualitative", get_qualitative_research)

            # Step 3: Advanced analytics
            analytics_a = self._get_cached_or_fetch(team_a, "analytics", get_advanced_analytics)
            analytics_b = self._get_cached_or_fetch(team_b, "analytics", get_advanced_analytics)

            # Step 4: Matchup analysis
            matchup_report = analyze_matchup(
                team_a=team_a,
                team_b=team_b,
                seed_a=seed_a,
                seed_b=seed_b,
                venue=venue,
            )

            # Step 5: Player/injury assessment
            players_a = self._get_cached_or_fetch(team_a, "players", assess_players)
            players_b = self._get_cached_or_fetch(team_b, "players", assess_players)

            # Step 6: Historical stats comparison (ESPN current + previous season)
            historical_a = self._get_cached_or_fetch(team_a, "historical", get_historical_comparison)
            historical_b = self._get_cached_or_fetch(team_b, "historical", get_historical_comparison)

            # Step 7: Predict matchup
            team_stats = {team_a: stats_a, team_b: stats_b}
            qualitative = {team_a: qual_a, team_b: qual_b}
            analytics = {team_a: analytics_a, team_b: analytics_b}
            players = {team_a: players_a, team_b: players_b}

            # Enrich analytics with historical improvement scores
            if historical_a and isinstance(historical_a, dict):
                analytics.setdefault(team_a, {})
                if isinstance(analytics[team_a], dict):
                    analytics[team_a]["improvement_score"] = historical_a.get("improvement_score", 0.5)
                    analytics[team_a]["historical_trends"] = historical_a.get("trends", {})
            if historical_b and isinstance(historical_b, dict):
                analytics.setdefault(team_b, {})
                if isinstance(analytics[team_b], dict):
                    analytics[team_b]["improvement_score"] = historical_b.get("improvement_score", 0.5)
                    analytics[team_b]["historical_trends"] = historical_b.get("trends", {})

            prediction = predict_matchup(
                team_a=team_a,
                team_b=team_b,
                seed_a=seed_a,
                seed_b=seed_b,
                round_name=round_name,
                team_stats=team_stats,
                qualitative=qualitative,
                analytics=analytics,
                matchup=matchup_report,
                players=players,
                region_a=matchup.team_a.region.value,
                region_b=matchup.team_b.region.value,
            )

            predictions_dict.append(prediction)

        # After all matchups: invoke Bracket Review Agent (Requirement 10.3, 9.1)
        review_result = review_round(
            round_name=round_name,
            predictions=predictions_dict,
            seed_history=seed_history,
        )

        flagged_matchups: list[dict] = review_result.get("flagged_matchups", [])
        flagged_winners: set[str] = {
            p.get("winner", "") for p in flagged_matchups
        }

        # Re-run predict_matchup for flagged matchups with review feedback (Requirement 9.7)
        if flagged_matchups:
            logger.info(
                "Re-evaluating %d flagged matchup(s) in %s after review.",
                len(flagged_matchups), round_name,
            )
            for i, pred_dict in enumerate(predictions_dict):
                winner = pred_dict.get("winner", "")
                if winner not in flagged_winners:
                    continue

                # Find the matching flagged prediction for its feedback
                feedback = ""
                for flagged in flagged_matchups:
                    if flagged.get("winner") == winner:
                        feedback = flagged.get("review_feedback", "")
                        break

                team_a = pred_dict["team_a"]["name"]
                team_b = pred_dict["team_b"]["name"]
                seed_a = pred_dict["team_a"]["seed"]
                seed_b = pred_dict["team_b"]["seed"]

                # Rebuild data dicts from cache
                stats_a = self.invocation_state["team_cache"].get(team_a, {}).get("stats", {})
                stats_b = self.invocation_state["team_cache"].get(team_b, {}).get("stats", {})
                qual_a = self.invocation_state["team_cache"].get(team_a, {}).get("qualitative", {})
                qual_b = self.invocation_state["team_cache"].get(team_b, {}).get("qualitative", {})
                analytics_a = self.invocation_state["team_cache"].get(team_a, {}).get("analytics", {})
                analytics_b = self.invocation_state["team_cache"].get(team_b, {}).get("analytics", {})
                players_a = self.invocation_state["team_cache"].get(team_a, {}).get("players", {})
                players_b = self.invocation_state["team_cache"].get(team_b, {}).get("players", {})

                matchup_report = analyze_matchup(
                    team_a=team_a,
                    team_b=team_b,
                    seed_a=seed_a,
                    seed_b=seed_b,
                    venue=pred_dict.get("venue", ""),
                )

                # Include review feedback in qualitative context
                qual_with_feedback = {
                    team_a: {**qual_a, "review_feedback": feedback},
                    team_b: qual_b,
                }

                revised_prediction = predict_matchup(
                    team_a=team_a,
                    team_b=team_b,
                    seed_a=seed_a,
                    seed_b=seed_b,
                    round_name=round_name,
                    team_stats={team_a: stats_a, team_b: stats_b},
                    qualitative=qual_with_feedback,
                    analytics={team_a: analytics_a, team_b: analytics_b},
                    matchup=matchup_report,
                    players={team_a: players_a, team_b: players_b},
                    region_a=pred_dict["team_a"].get("region", "East"),
                    region_b=pred_dict["team_b"].get("region", "East"),
                )
                predictions_dict[i] = revised_prediction

        # Convert dicts back to Prediction objects
        predictions: list[Prediction] = []
        for pred_dict in predictions_dict:
            predictions.append(Prediction.from_dict(pred_dict))

        # Store completed round in invocation_state
        self.invocation_state["completed_rounds"][round_name] = [
            p.to_dict() for p in predictions
        ]

        return predictions

    def advance_winners(self, round_name: str, predictions: list[Prediction]) -> list[Matchup]:
        """Build next round matchups from current round winners.

        For most rounds, pairs winners sequentially: winner[0] vs winner[1], etc.
        For the Final Four, pairs by NCAA bracket convention:
          - East region winner vs South region winner
          - West region winner vs Midwest region winner

        Args:
            round_name: The round that just completed.
            predictions: Finalized predictions from the completed round.

        Returns:
            List of Matchup objects for the next round.

        Requirements: 10.4
        """
        # Determine next round name
        current_idx = ROUND_ORDER.index(round_name)
        if current_idx >= len(ROUND_ORDER) - 1:
            return []

        next_round_name = ROUND_ORDER[current_idx + 1]
        next_round_enum = RoundName(next_round_name)

        # Extract winners in order
        winners: list[Team] = []
        for pred in predictions:
            if pred.winner == pred.team_a.name:
                winners.append(pred.team_a)
            else:
                winners.append(pred.team_b)

        # For Final Four: pair by region (NCAA bracket convention)
        if next_round_enum == RoundName.FINAL_FOUR and len(winners) == 4:
            return self._build_final_four_matchups(winners, next_round_enum)

        # Standard sequential pairing for all other rounds
        next_matchups: list[Matchup] = []
        game_number = 1
        for i in range(0, len(winners) - 1, 2):
            team_a = winners[i]
            team_b = winners[i + 1]
            next_matchups.append(
                Matchup(
                    team_a=team_a,
                    team_b=team_b,
                    round_name=next_round_enum,
                    venue="TBD",
                    game_number=game_number,
                )
            )
            game_number += 1

        return next_matchups

    def _build_final_four_matchups(
        self, winners: list[Team], round_enum: RoundName
    ) -> list[Matchup]:
        """Build Final Four matchups using NCAA bracket region pairing.

        NCAA convention: East vs South, West vs Midwest.
        If regions can't be determined, falls back to sequential pairing.
        """
        # NCAA Final Four pairing: East vs South, West vs Midwest
        _REGION_PAIRS = [
            (Region.EAST, Region.SOUTH),
            (Region.WEST, Region.MIDWEST),
        ]

        region_map: dict[Region, Team] = {}
        for w in winners:
            region_map[w.region] = w

        matchups: list[Matchup] = []
        game_number = 1

        for region_a, region_b in _REGION_PAIRS:
            team_a = region_map.get(region_a)
            team_b = region_map.get(region_b)
            if team_a and team_b:
                matchups.append(
                    Matchup(
                        team_a=team_a,
                        team_b=team_b,
                        round_name=round_enum,
                        venue="TBD",
                        game_number=game_number,
                    )
                )
                game_number += 1

        # Fallback: if region pairing didn't produce 2 matchups, pair sequentially
        if len(matchups) < 2:
            logger.warning(
                "Could not pair Final Four by region (found %d matchups); "
                "falling back to sequential pairing.",
                len(matchups),
            )
            matchups = []
            game_number = 1
            for i in range(0, len(winners) - 1, 2):
                matchups.append(
                    Matchup(
                        team_a=winners[i],
                        team_b=winners[i + 1],
                        round_name=round_enum,
                        venue="TBD",
                        game_number=game_number,
                    )
                )
                game_number += 1

        return matchups

    def run(
        self,
        bracket: Bracket,
        start_round: str = "Round of 64",
        prior_results: dict | None = None,
        verbose: bool = False,
    ) -> BracketOutput:
        """Execute full bracket prediction workflow across all rounds.

   
     Processes rounds sequentially from start_round through Championship.
        Supports resumption from a specific round via prior_results.

        Args:
            bracket: The tournament bracket with all 64 teams.
            start_round: Round to start from (default "Round of 64").
            prior_results: Prior round results dict for resumption (optional).
            verbose: If True, display console summary after each round.

        Returns:
            Complete BracketOutput with champion, path, all round results,
            upset alerts, and Cinderella watch list.

        Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 1.5, 12.4
        """
        # Initialize invocation_state with bracket data
        self.invocation_state["bracket"] = bracket.to_dict()
        self.invocation_state["current_round"] = start_round

        # Load prior results for resumption (Requirement 1.5)
        if prior_results:
            for rnd_name, preds in prior_results.items():
                self.invocation_state["completed_rounds"][rnd_name] = preds

        # Determine which rounds to process
        start_idx = ROUND_ORDER.index(start_round)
        rounds_to_process = ROUND_ORDER[start_idx:]

        # Get initial matchups for the starting round
        if start_round == RoundName.ROUND_OF_64.value:
            current_matchups = bracket.get_first_round_matchups()
        else:
            # Reconstruct matchups from prior results for the start round
            current_matchups = self._reconstruct_matchups_from_prior(
                start_round, prior_results or {}
            )

        all_round_results: list[RoundResult] = []

        # Include prior round results in output (for resumption)
        if prior_results:
            for rnd_name in ROUND_ORDER[:start_idx]:
                if rnd_name in prior_results:
                    preds = [Prediction.from_dict(p) for p in prior_results[rnd_name]]
                    upset_count = sum(1 for p in preds if p.upset_alert)
                    cinderella = [
                        p.winner for p in preds
                        if (p.winner == p.team_a.name and p.team_a.seed >= 11)
                        or (p.winner == p.team_b.name and p.team_b.seed >= 11)
                    ]
                    all_round_results.append(
                        RoundResult(
                            round_name=RoundName(rnd_name),
                            matchups=preds,
                            upset_count=upset_count,
                            cinderella_candidates=cinderella,
                        )
                    )

        # Process each round sequentially (Requirement 10.1)
        for round_name in rounds_to_process:
            self.invocation_state["current_round"] = round_name
            logger.info("Processing %s (%d matchups)", round_name, len(current_matchups))

            predictions = self.process_round(round_name, current_matchups)

            # Build RoundResult
            upset_count = sum(1 for p in predictions if p.upset_alert)
            cinderella_candidates = [
                p.winner for p in predictions
                if (p.winner == p.team_a.name and p.team_a.seed >= 11)
                or (p.winner == p.team_b.name and p.team_b.seed >= 11)
            ]

            round_result = RoundResult(
                round_name=RoundName(round_name),
                matchups=predictions,
                upset_count=upset_count,
                cinderella_candidates=cinderella_candidates,
            )
            all_round_results.append(round_result)

            # Display console summary if verbose (Requirement 12.4)
            if verbose:
                print(f"\n{'=' * 60}")
                print(f"Completed: {round_name}")
                print(f"{'=' * 60}")
                for pred in predictions:
                    upset_marker = " 🚨 UPSET" if pred.upset_alert else ""
                    print(
                        f"  ({pred.team_a.seed}) {pred.team_a.name} vs "
                        f"({pred.team_b.seed}) {pred.team_b.name} → "
                        f"Winner: {pred.winner} [{pred.confidence}%]{upset_marker}"
                    )

            # Advance winners to next round (Requirement 10.4)
            if round_name != RoundName.CHAMPIONSHIP.value:
                current_matchups = self.advance_winners(round_name, predictions)

        # Build final BracketOutput (Requirement 10.5)
        return self._build_bracket_output(all_round_results)

    def _get_cached_or_fetch(
        self,
        team_name: str,
        data_type: str,
        fetch_fn: Any,
    ) -> dict:
        """Return cached team data or fetch and cache it.

        Implements Requirement 10.6 — reuse cached data from earlier rounds.

        Args:
            team_name: Team name to look up.
            data_type: Type of data (stats, analytics, qualitative, players).
            fetch_fn: Callable to invoke if cache miss.

        Returns:
            Data dict for the team.
        """
        team_cache = self.invocation_state["team_cache"]
        if team_name not in team_cache:
            team_cache[team_name] = {}

        if data_type not in team_cache[team_name]:
            logger.debug("Cache miss for %s/%s — fetching.", team_name, data_type)
            team_cache[team_name][data_type] = fetch_fn(team_name)

        return team_cache[team_name][data_type]

    def _reconstruct_matchups_from_prior(
        self,
        round_name: str,
        prior_results: dict,
    ) -> list[Matchup]:
        """Reconstruct matchups for a round from prior results.

        Used when resuming from a round other than Round of 64.

        Args:
            round_name: The round to reconstruct matchups for.
            prior_results: Dict of prior round results.

        Returns:
            List of Matchup objects for the specified round.
        """
        round_idx = ROUND_ORDER.index(round_name)
        if round_idx == 0:
            return []

        prev_round_name = ROUND_ORDER[round_idx - 1]
        prev_preds_raw = prior_results.get(prev_round_name, [])
        if not prev_preds_raw:
            return []

        prev_predictions = [Prediction.from_dict(p) for p in prev_preds_raw]
        return self.advance_winners(prev_round_name, prev_predictions)

    def _build_bracket_output(self, all_round_results: list[RoundResult]) -> BracketOutput:
        """Build the complete BracketOutput from all round results.

        Determines champion, champion path, upset alerts, and Cinderella watch.

        Args:
            all_round_results: List of RoundResult objects for all processed rounds.

        Returns:
            Complete BracketOutput.

        Requirements: 10.5, 12.1, 12.2, 12.3
        """
        # Find championship round result
        champion = "Unknown"
        champion_confidence = 50
        champion_path: list[str] = []

        championship_result = next(
            (r for r in all_round_results if r.round_name == RoundName.CHAMPIONSHIP),
            None,
        )

        if championship_result and championship_result.matchups:
            champ_pred = championship_result.matchups[0]
            champion = champ_pred.winner
            champion_confidence = champ_pred.confidence

        # Build champion path: opponents beaten in each round (Requirement 10.5)
        if champion != "Unknown":
            for round_result in all_round_results:
                for pred in round_result.matchups:
                    if pred.winner == champion:
                        # The opponent is the team the champion beat
                        opponent = (
                            pred.team_b.name
                            if pred.winner == pred.team_a.name
                            else pred.team_a.name
                        )
                        champion_path.append(opponent)
                        break

        # Collect all upset alerts across all rounds (Requirement 12.3)
        upset_alerts: list[dict] = []
        for round_result in all_round_results:
            for pred in round_result.matchups:
                if pred.upset_alert:
                    winner_seed = (
                        pred.team_a.seed
                        if pred.winner == pred.team_a.name
                        else pred.team_b.seed
                    )
                    loser = (
                        pred.team_b.name
                        if pred.winner == pred.team_a.name
                        else pred.team_a.name
                    )
                    loser_seed = (
                        pred.team_b.seed
                        if pred.winner == pred.team_a.name
                        else pred.team_a.seed
                    )
                    upset_alerts.append({
                        "round": round_result.round_name.value,
                        "winner": pred.winner,
                        "winner_seed": winner_seed,
                        "loser": loser,
                        "loser_seed": loser_seed,
                        "confidence": pred.confidence,
                    })

        # Cinderella watch: seeds >= 11 advancing past Round of 64 (Requirement 12.3)
        cinderella_watch: list[dict] = []
        cinderella_teams: dict[str, dict] = {}

        for round_result in all_round_results:
            for pred in round_result.matchups:
                winner_seed = (
                    pred.team_a.seed
                    if pred.winner == pred.team_a.name
                    else pred.team_b.seed
                )
                if winner_seed >= 11:
                    if pred.winner not in cinderella_teams:
                        cinderella_teams[pred.winner] = {
                            "team": pred.winner,
                            "seed": winner_seed,
                            "furthest_round": round_result.round_name.value,
                        }
                    else:
                        # Update to furthest round reached
                        cinderella_teams[pred.winner]["furthest_round"] = (
                            round_result.round_name.value
                        )

        # Only include teams that advanced past Round of 64
        for team_name, info in cinderella_teams.items():
            if info["furthest_round"] != RoundName.ROUND_OF_64.value:
                cinderella_watch.append(info)

        return BracketOutput(
            champion=champion,
            champion_confidence=champion_confidence,
            champion_path=champion_path,
            rounds=all_round_results,
            upset_alerts=upset_alerts,
            cinderella_watch=cinderella_watch,
        )
