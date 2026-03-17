"""PDF Parser Agent for March Madness bracket extraction.

Implements the parse_bracket tool with a fallback chain:
  1. pdfplumber text extraction
  2. Bedrock Claude multimodal vision
  3. Raise ValueError prompting user to supply --bracket-json

Validates the extracted bracket (64 teams, 4 regions, 32 matchups)
and presents a summary to the user before returning.
"""

from __future__ import annotations

import logging
import os

import boto3
from strands import tool

from src.models.enums import Region, RoundName
from src.models.team import Bracket, BracketValidationError, Matchup, RegionBracket, Team
from src.utils.pdf_extractor import extract_with_pdfplumber, extract_with_vision

logger = logging.getLogger(__name__)

# Standard first-round seed pairings (higher seed vs lower seed)
_FIRST_ROUND_SEED_PAIRS = [
    (1, 16), (8, 9), (5, 12), (4, 13),
    (6, 11), (3, 14), (7, 10), (2, 15),
]


def _region_from_str(region_str: str) -> Region:
    """Convert a region string to a Region enum value."""
    normalized = region_str.strip().title()
    try:
        return Region(normalized)
    except ValueError:
        # Try case-insensitive match
        for r in Region:
            if r.value.lower() == region_str.strip().lower():
                return r
        raise ValueError(f"Unknown region: {region_str!r}")


def _build_bracket_from_extracted(extracted: dict) -> Bracket:
    """Build a Bracket object from the raw extracted dict.

    Args:
        extracted: Dict with keys "teams", "matchups", "season".
            teams: list of {"name": str, "seed": int, "region": str}
            matchups: list of {"team_a": str, "team_b": str, "venue": str}
            season: int | None

    Returns:
        A validated Bracket object.

    Raises:
        ValueError: If the extracted data cannot be mapped to a valid Bracket.
        BracketValidationError: If the resulting Bracket fails structural validation.
    """
    raw_teams: list[dict] = extracted.get("teams", [])
    raw_matchups: list[dict] = extracted.get("matchups", [])
    season: int = extracted.get("season") or 2025

    # Build Team objects keyed by name for quick lookup
    teams_by_name: dict[str, Team] = {}
    # Group teams by region
    teams_by_region: dict[Region, list[Team]] = {r: [] for r in Region}

    for raw in raw_teams:
        try:
            region = _region_from_str(raw["region"])
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping team with invalid region: %s – %s", raw, exc)
            continue

        team = Team(
            name=raw["name"],
            seed=int(raw["seed"]),
            region=region,
        )
        teams_by_name[team.name] = team
        teams_by_region[region].append(team)

    # Build matchup lookup: team_name -> venue (from raw matchups)
    venue_by_pair: dict[frozenset[str], str] = {}
    for rm in raw_matchups:
        key = frozenset([rm.get("team_a", ""), rm.get("team_b", "")])
        venue_by_pair[key] = rm.get("venue", "")

    # Build RegionBracket objects
    region_brackets: list[RegionBracket] = []
    game_number = 1

    for region in Region:
        region_teams = teams_by_region[region]
        seed_map: dict[int, Team] = {t.seed: t for t in region_teams}

        matchups: list[Matchup] = []
        for seed_a, seed_b in _FIRST_ROUND_SEED_PAIRS:
            team_a = seed_map.get(seed_a)
            team_b = seed_map.get(seed_b)
            if team_a is None or team_b is None:
                continue
            venue = venue_by_pair.get(frozenset([team_a.name, team_b.name]), "")
            matchups.append(
                Matchup(
                    team_a=team_a,
                    team_b=team_b,
                    round_name=RoundName.ROUND_OF_64,
                    venue=venue,
                    game_number=game_number,
                )
            )
            game_number += 1

        region_brackets.append(
            RegionBracket(region=region, teams=region_teams, matchups=matchups)
        )

    return Bracket(regions=region_brackets, season=season)


def _print_bracket_summary(bracket: Bracket) -> None:
    """Print a human-readable bracket summary for user confirmation."""
    print("\n=== Extracted Bracket Summary ===")
    print(f"Season: {bracket.season}")
    print(f"Total teams: {len(bracket.get_all_teams())}")
    print(f"Total first-round matchups: {len(bracket.get_first_round_matchups())}")
    print()
    for region_bracket in bracket.regions:
        print(f"  {region_bracket.region.value} ({len(region_bracket.teams)} teams):")
        for team in sorted(region_bracket.teams, key=lambda t: t.seed):
            print(f"    ({team.seed}) {team.name}")
    print("=================================\n")


def _try_vision_fallback(file_path: str, pdfplumber_result: dict | None) -> dict | None:
    """Attempt Bedrock Claude vision extraction when pdfplumber is incomplete.

    Returns the better result (more teams) between pdfplumber and vision,
    or None if both failed.
    """
    pdfplumber_teams = len((pdfplumber_result or {}).get("teams", []))
    if pdfplumber_result is not None:
        logger.info(
            "pdfplumber only extracted %d teams (need 64); trying Bedrock Claude vision.",
            pdfplumber_teams,
        )
    else:
        logger.info("pdfplumber extraction failed; trying Bedrock Claude vision.")

    bedrock_client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    vision_extracted = extract_with_vision(file_path, bedrock_client)
    if vision_extracted is not None:
        vision_teams = len(vision_extracted.get("teams", []))
        if vision_teams > pdfplumber_teams:
            logger.info("Using Bedrock vision result (%d teams).", vision_teams)
            return vision_extracted
    return pdfplumber_result


@tool
def parse_bracket(file_path: str) -> dict:
    """Extract and validate a March Madness bracket from a CBS bracket PDF.

    Implements a three-step fallback chain:
      1. pdfplumber text extraction
      2. Bedrock Claude multimodal vision
      3. Raise ValueError asking user to supply --bracket-json

    After extraction the bracket is validated (64 teams, 4 regions,
    32 first-round matchups) and a summary is printed for user confirmation.

    Args:
        file_path: Path to the CBS bracket PDF file.

    Returns:
        Bracket.to_dict() – a JSON-serializable representation of the bracket.

    Raises:
        ValueError: If extraction fails or the bracket fails validation.
    """
    # Step 1: Try pdfplumber
    extracted = extract_with_pdfplumber(file_path)

    # Step 2: Fall back to Bedrock Claude vision if pdfplumber failed entirely
    # OR returned an incomplete result (fewer than 64 teams)
    pdfplumber_teams = len((extracted or {}).get("teams", []))
    if extracted is None or pdfplumber_teams < 64:
        extracted = _try_vision_fallback(file_path, extracted)

    # Step 3: Neither method worked – ask user to supply JSON
    if extracted is None:
        raise ValueError(
            "Could not extract bracket data from the provided PDF using either "
            "pdfplumber or Bedrock Claude vision. "
            "Please provide the bracket as a JSON file using the --bracket-json option."
        )

    # Build Bracket object from extracted data
    try:
        bracket = _build_bracket_from_extracted(extracted)
    except BracketValidationError as exc:
        raise ValueError(
            f"Extracted bracket failed validation: {exc}. "
            "Please verify the PDF is a valid CBS bracket or supply --bracket-json."
        ) from exc

    # Validate counts explicitly for a clear error message
    total_teams = len(bracket.get_all_teams())
    total_regions = len(bracket.regions)
    total_matchups = len(bracket.get_first_round_matchups())

    if total_teams != 64:
        raise ValueError(
            f"Bracket validation failed: expected 64 teams, found {total_teams}. "
            "Please verify the PDF or supply --bracket-json."
        )
    if total_regions != 4:
        raise ValueError(
            f"Bracket validation failed: expected 4 regions, found {total_regions}. "
            "Please verify the PDF or supply --bracket-json."
        )
    if total_matchups != 32:
        raise ValueError(
            f"Bracket validation failed: expected 32 first-round matchups, "
            f"found {total_matchups}. "
            "Please verify the PDF or supply --bracket-json."
        )

    # Present bracket to user for confirmation
    _print_bracket_summary(bracket)

    return bracket.to_dict()
