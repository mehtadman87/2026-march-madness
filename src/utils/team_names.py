"""Team name normalization for bracket data.

Maps common bracket abbreviations and short names to canonical full names
used by external APIs (ESPN, NCAA, CBBD, BartTorvik).

Applied immediately after PDF extraction, before any API calls.
"""

import logging

logger = logging.getLogger(__name__)

# Bracket abbreviation/short name -> canonical full name
# Sources: CBS bracket PDFs, ESPN team list, NCAA.com
_NORMALIZATION_MAP: dict[str, str] = {
    # State abbreviations
    "Iowa St.": "Iowa State",
    "Ohio St.": "Ohio State",
    "Utah St.": "Utah State",
    "Wright St.": "Wright State",
    "Tenn. State": "Tennessee State",
    "Mich. State": "Michigan State",
    "Penn St.": "Penn State",
    "Boise St.": "Boise State",
    "Fresno St.": "Fresno State",
    "San Jose St.": "San Jose State",
    "Wichita St.": "Wichita State",
    "Arizona St.": "Arizona State",
    "Florida St.": "Florida State",
    "N.C. State": "NC State",
    "Miss. State": "Mississippi State",
    "Colo. State": "Colorado State",
    "Kansas St.": "Kansas State",
    "Oregon St.": "Oregon State",
    # Directional abbreviations
    "N. Carolina": "North Carolina",
    "N. Iowa": "Northern Iowa",
    "N. Dakota St.": "North Dakota State",
    "S. Carolina": "South Carolina",
    "S. Florida": "South Florida",
    "W. Virginia": "West Virginia",
    "W. Kentucky": "Western Kentucky",
    "E. Washington": "Eastern Washington",
    # CBS bracket all-caps abbreviations
    "SFLA": "South Florida",
    "MICHST": "Michigan State",
    "NDAKST": "North Dakota State",
    "MARYCA": "Maryland",
    "KENSAW": "Kennesaw State",
    "PVAM/LEHIGH": "Prairie View A&M",
    "UMBC/HOW": "UMBC",
    "TEXAS/NCST": "Texas",
    "MIAOH/SMU": "SMU",
    # Saint/St variations
    "St. John's": "St. John's",
    "Saint Louis": "Saint Louis",
    "Cal Baptist": "California Baptist",
    # Common short forms
    "UConn": "Connecticut",
    "UCF": "UCF",
    "VCU": "VCU",
    "BYU": "BYU",
    "TCU": "TCU",
    "SMU": "SMU",
    "LIU": "LIU",
    "UNLV": "UNLV",
    "USC": "USC",
    "UCLA": "UCLA",
}

# Build a case-insensitive lookup
_NORM_LOWER: dict[str, str] = {k.lower(): v for k, v in _NORMALIZATION_MAP.items()}


def normalize_team_name(name: str) -> str:
    """Normalize a team name from bracket extraction to its canonical form.

    Returns the canonical name if a mapping exists, otherwise returns
    the original name unchanged.
    """
    normalized = _NORM_LOWER.get(name.lower().strip())
    if normalized and normalized != name:
        logger.debug("Normalized team name: '%s' -> '%s'", name, normalized)
        return normalized
    return name


def normalize_bracket_teams(extracted: dict) -> dict:
    """Normalize all team names in an extracted bracket dict.

    Modifies the 'teams' and 'matchups' lists in-place, replacing
    abbreviated names with canonical full names.

    Args:
        extracted: Dict with keys "teams", "matchups", "season"

    Returns:
        The same dict with normalized team names.
    """
    for team in extracted.get("teams", []):
        if "name" in team:
            team["name"] = normalize_team_name(team["name"])

    for matchup in extracted.get("matchups", []):
        if "team_a" in matchup:
            matchup["team_a"] = normalize_team_name(matchup["team_a"])
        if "team_b" in matchup:
            matchup["team_b"] = normalize_team_name(matchup["team_b"])

    return extracted
