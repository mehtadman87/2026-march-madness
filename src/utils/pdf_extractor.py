"""
PDF bracket extraction utilities.

Provides two extraction strategies:
  1. extract_with_pdfplumber - text-based extraction via pdfplumber
  2. extract_with_vision     - multimodal fallback via Bedrock Claude

Both return a dict with keys:
  "teams"    : list of {"name": str, "seed": int, "region": str}
  "matchups" : list of {"team_a": str, "team_b": str, "venue": str}
  "season"   : int | None

Both catch all exceptions and return None on any failure.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGIONS = {"East", "West", "South", "Midwest"}

# Season year – look for a 4-digit year in the 2000s
_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Bedrock cross-region inference profile for vision fallback.
# Using the global Claude Opus 4.6 inference profile for best accuracy.
_VISION_MODEL_ID = "global.anthropic.claude-opus-4-6-v1"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_FIRST_ROUND_SEED_PAIRS = [
    (1, 16),
    (8, 9),
    (5, 12),
    (4, 13),
    (6, 11),
    (3, 14),
    (7, 10),
    (2, 15),
]
_SEED_TEAM_RE = re.compile(r"^\(?([1-9]|1[0-6])\)?\s+(.+)$")


def _detect_region(line: str) -> str | None:
    """Return the region name if the line looks like a region header, else None."""
    if len(line) >= 40:
        return None
    lower = line.lower()
    for region in REGIONS:
        if region.lower() in lower:
            return region
    return None


def _build_region_matchups(region_teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair teams within a region into standard first-round matchups."""
    seed_map = {t["seed"]: t for t in region_teams}
    result = []
    for s_a, s_b in _FIRST_ROUND_SEED_PAIRS:
        if s_a in seed_map and s_b in seed_map:
            result.append(
                {
                    "team_a": seed_map[s_a]["name"],
                    "team_b": seed_map[s_b]["name"],
                    "venue": "",
                }
            )
    return result


def _extract_season(lines: list[str]) -> int | None:
    """Return the first 4-digit year found in the text, or None."""
    for line in lines:
        m = _YEAR_RE.search(line)
        if m:
            return int(m.group(1))
    return None


def _is_duplicate_team(teams: list[dict[str, Any]], seed: int, region: str) -> bool:
    return any(t["seed"] == seed and t["region"] == region for t in teams)


def _try_add_team(
    line: str,
    region: str,
    teams: list[dict[str, Any]],
    region_teams: list[dict[str, Any]],
) -> None:
    """Parse a seed+name line and append to both lists if not already present."""
    seed_match = _SEED_TEAM_RE.match(line)
    if not seed_match:
        return
    seed = int(seed_match.group(1))
    name = seed_match.group(2).strip()
    if not _is_duplicate_team(teams, seed, region):
        entry: dict[str, Any] = {"name": name, "seed": seed, "region": region}
        teams.append(entry)
        region_teams.append(entry)


def _parse_text_to_bracket(text: str) -> dict[str, Any] | None:
    """
    Parse raw text extracted from a bracket PDF into the standard dict.

    Heuristic approach:
    - Scan for region headers (East / West / South / Midwest)
    - Within each region block, pair seed+team lines as matchups using
      the standard NCAA first-round seed pairings
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    teams: list[dict[str, Any]] = []
    matchups: list[dict[str, Any]] = []
    season = _extract_season(lines)
    current_region: str | None = None
    region_teams: list[dict[str, Any]] = []

    for line in lines:
        region = _detect_region(line)
        if region:
            if current_region and region_teams:
                matchups.extend(_build_region_matchups(region_teams))
                region_teams = []
            current_region = region
            continue

        if current_region:
            _try_add_team(line, current_region, teams, region_teams)

    if current_region and region_teams:
        matchups.extend(_build_region_matchups(region_teams))

    return {"teams": teams, "matchups": matchups, "season": season} if teams else None


def _build_vision_prompt() -> str:
    return (
        "You are analyzing an NCAA March Madness bracket PDF image. "
        "Extract all bracket data and return ONLY a valid JSON object with this exact structure:\n"
        "{\n"
        '  "teams": [\n'
        '    {"name": "<full team name>", "seed": <1-16>, "region": "<East|West|South|Midwest>"}\n'
        "  ],\n"
        '  "matchups": [\n'
        '    {"team_a": "<full team name>", "team_b": "<full team name>", "venue": "<location or empty string>"}\n'
        "  ],\n"
        '  "season": <year as integer or null>\n'
        "}\n\n"
        "Rules:\n"
        "- Include all 64 teams with their correct seeds and regions.\n"
        "- List only first-round matchups (32 total).\n"
        "- IMPORTANT: Use the FULL official team name, NOT abbreviations. "
        "For example, use 'Michigan State' not 'MICHST', 'Iowa State' not 'Iowa St.', "
        "'North Dakota State' not 'NDAKST', 'South Florida' not 'SFLA', "
        "'North Carolina' not 'N. Carolina', 'Northern Iowa' not 'N. Iowa'. "
        "If the bracket shows an abbreviation, expand it to the full school name.\n"
        "- Return ONLY the JSON object, no markdown fences, no explanation."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_with_pdfplumber(pdf_path: str) -> dict[str, Any] | None:
    """
    Attempt text extraction from a bracket PDF via pdfplumber.

    Returns a dict with keys "teams", "matchups", "season" on success,
    or None if pdfplumber raises any exception or no teams are found.
    """
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError:
        logger.warning("pdfplumber is not installed; skipping text extraction.")
        return None

    try:
        path = Path(pdf_path)
        if not path.is_file():
            logger.warning("PDF path does not exist: %s", pdf_path)
            return None

        full_text_parts: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text_parts.append(page_text)

        full_text = "\n".join(full_text_parts)
        if not full_text.strip():
            logger.warning("pdfplumber extracted no text from %s", pdf_path)
            return None

        result = _parse_text_to_bracket(full_text)
        if result is None or not result.get("teams"):
            logger.warning("pdfplumber text parsing yielded no teams for %s", pdf_path)
            return None

        return result

    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber extraction failed for %s: %s", pdf_path, exc)
        return None


def extract_with_vision(pdf_path: str, bedrock_client: Any) -> dict[str, Any] | None:
    """
    Attempt bracket extraction via Bedrock Claude multimodal vision.

    Uses the Bedrock Converse API with a PDF document content block —
    the AWS-recommended approach per:
    https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-runtime_example_bedrock-runtime_DocumentUnderstanding_AnthropicClaude_section.html

    Returns a dict with keys "teams", "matchups", "season" on success,
    or None on any failure.
    """
    try:
        path = Path(pdf_path)
        if not path.is_file():
            logger.warning("PDF path does not exist: %s", pdf_path)
            return None

        pdf_bytes = path.read_bytes()
        prompt = _build_vision_prompt()

        # Converse API with document content block (raw bytes, no base64 needed)
        conversation = [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": "pdf",
                            "name": "bracket",
                            "source": {"bytes": pdf_bytes},
                        }
                    },
                    {"text": prompt},
                ],
            }
        ]

        response = bedrock_client.converse(
            modelId=_VISION_MODEL_ID,
            messages=conversation,
            inferenceConfig={"maxTokens": 4096, "temperature": 0.0},
        )

        raw_text = response["output"]["message"]["content"][0]["text"]

        if not raw_text.strip():
            logger.warning("Bedrock vision returned empty response for %s", pdf_path)
            return None

        # Strip any accidental markdown fences
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

        parsed: dict[str, Any] = json.loads(raw_text)

        if not isinstance(parsed.get("teams"), list) or not parsed["teams"]:
            logger.warning("Bedrock vision response missing teams for %s", pdf_path)
            return None

        parsed.setdefault("matchups", [])
        parsed.setdefault("season", None)

        return parsed

    except Exception as exc:  # noqa: BLE001
        logger.warning("Bedrock vision extraction failed for %s: %s", pdf_path, exc)
        return None
