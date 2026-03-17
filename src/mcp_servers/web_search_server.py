"""
Web Search MCP Server

Exposes search_web and fetch_page tools via FastMCP.
Uses Linkup (https://app.linkup.so) as the web search provider.
Set LINKUP_API_KEY in the environment to enable search and fetch.
"""

import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web-search")


@mcp.tool()
def search_web(query: str, num_results: int = 5) -> list[dict] | dict:
    """
    Search the web using the Linkup API (https://app.linkup.so).

    Requires LINKUP_API_KEY environment variable.

    Returns a list of {"title": str, "url": str, "snippet": str} dicts,
    or {"error": str, "results": []} on failure.
    """
    api_key = os.environ.get("LINKUP_API_KEY")
    if not api_key:
        return {
            "error": "No search API key configured. Set LINKUP_API_KEY.",
            "results": [],
        }
    return _search_linkup(query, num_results, api_key)


def _search_linkup(query: str, num_results: int, api_key: str) -> list[dict] | dict:
    """Call Linkup Search API and return normalized results.

    API reference: https://docs.linkup.so/pages/sdk/python/python
    Uses the linkup-sdk Python client:
        client.search(query, depth, output_type, max_results)
    """
    try:
        from linkup import LinkupClient  # type: ignore[import]

        client = LinkupClient(api_key=api_key)
        response = client.search(
            query=query,
            depth="standard",
            output_type="searchResults",
            include_images=False,
            max_results=num_results,
        )

        results = []
        # response.results is a list of SearchResult objects with .name, .url, .content
        raw_results = getattr(response, "results", []) or []
        for item in raw_results[:num_results]:
            results.append({
                "title": getattr(item, "name", "") or "",
                "url": getattr(item, "url", "") or "",
                "snippet": getattr(item, "content", "") or "",
            })
        return results
    except Exception as e:
        return {"error": f"Linkup search failed: {str(e)}", "results": []}


@mcp.tool()
def fetch_page(url: str) -> dict:
    """
    Fetch page content via LinkupClient.fetch().

    Returns {"url": str, "content": str, "error": None} on success,
    or {"url": str, "content": "", "error": str} on failure.
    """
    api_key = os.environ.get("LINKUP_API_KEY")
    if not api_key:
        return {"url": url, "content": "", "error": "No LINKUP_API_KEY configured"}
    try:
        from linkup import LinkupClient  # type: ignore[import]
        client = LinkupClient(api_key=api_key)
        response = client.fetch(url, render_js=False)
        content = getattr(response, "content", "") or str(response)
        return {"url": url, "content": content, "error": None}
    except Exception as exc:
        return {"url": url, "content": "", "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
