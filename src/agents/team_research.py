"""Team Research Agent for March Madness Bracket Predictor.

Gathers qualitative insights about each team via web search:
- Coach tournament track record
- Program historical pedigree
- Conference strength reputation
- Current season momentum
- Transfer portal impact on roster
- Team scheme or style identity

Validates: Requirements 4.1, 4.2, 4.3
"""

from strands import tool
from src.models.agent_outputs import QualitativeReport
from src.mcp_servers.web_search_server import search_web


def _extract_first_result(search_result: list | dict) -> tuple[str, str]:
    """Extract snippet and URL from the first search result, or return empty strings."""
    if isinstance(search_result, list) and search_result:
        first = search_result[0]
        return first.get("snippet", "").strip(), first.get("url", "")
    return "", ""


@tool
def get_qualitative_research(team_name: str) -> dict:
    """
    Research qualitative factors for a team using web search.

    Gathers: coach tournament record, program pedigree, conference strength,
    current momentum, transfer portal impact, and style identity.

    Returns QualitativeReport.to_dict() with each factor labeled and sourced.
    Unavailable factors are noted explicitly rather than omitted.
    """
    factors = {
        "coach_tournament_record": f"{team_name} coach NCAA tournament record wins",
        "program_pedigree": f"{team_name} basketball program history championships",
        "conference_strength": f"{team_name} conference strength 2025 basketball",
        "current_momentum": f"{team_name} basketball 2025 recent form momentum",
        "transfer_portal_impact": f"{team_name} basketball transfer portal 2025 roster",
        "style_identity": f"{team_name} basketball playing style offense defense scheme",
    }

    results: dict[str, str] = {}
    sources: list[str] = []
    unavailable_factors: list[str] = []

    for factor, query in factors.items():
        search_result = search_web(query, num_results=3)

        # search_web returns list[dict] on success or dict with "error" key on failure
        snippet, url = _extract_first_result(search_result)
        results[factor] = snippet or "Unavailable"
        if not snippet:
            unavailable_factors.append(factor)
        if url:
            sources.append(url)

    report = QualitativeReport(
        team_name=team_name,
        coach_tournament_record=results["coach_tournament_record"],
        program_pedigree=results["program_pedigree"],
        conference_strength=results["conference_strength"],
        current_momentum=results["current_momentum"],
        transfer_portal_impact=results["transfer_portal_impact"],
        style_identity=results["style_identity"],
        sources=sources,
        unavailable_factors=unavailable_factors,
    )

    return report.to_dict()
