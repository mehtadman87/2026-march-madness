"""
Unit tests for MCP server error handling.

Tests cover web_search_server and ncaa_data_server error paths,
success paths, and rate-limiter integration.

Requirements: 11.3, 11.4
"""

import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

import httpx


class TestSearchWebNoApiKeys(unittest.TestCase):
    """search_web returns structured error when LINKUP_API_KEY is not set."""

    def test_no_api_key_returns_error_dict(self):
        from src.mcp_servers.web_search_server import search_web

        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("LINKUP_API_KEY", None)
            result = search_web("march madness 2025")

        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("results", result)
        self.assertEqual(result["results"], [])
        self.assertIn("LINKUP_API_KEY", result["error"])


class TestSearchWebLinkupError(unittest.TestCase):
    """search_web returns structured error when Linkup client raises an exception."""

    def test_linkup_exception_returns_error_dict(self):
        from src.mcp_servers.web_search_server import search_web

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Linkup API unavailable")
        mock_linkup_cls = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"LINKUP_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"linkup": MagicMock(LinkupClient=mock_linkup_cls)}):
                result = search_web("test query")

        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("results", result)
        self.assertEqual(result["results"], [])
        self.assertIn("Linkup search failed", result["error"])


class TestFetchPageNoApiKey(unittest.TestCase):
    """fetch_page returns error dict immediately when LINKUP_API_KEY is unset."""

    def test_no_api_key_returns_error_without_network_call(self):
        from src.mcp_servers.web_search_server import fetch_page

        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("LINKUP_API_KEY", None)
            with patch("src.mcp_servers.web_search_server.os.environ.get", return_value=None):
                result = fetch_page("https://example.com")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["content"], "")
        self.assertIn("LINKUP_API_KEY", result["error"])


class TestFetchPageLinkupSuccess(unittest.TestCase):
    """fetch_page returns content dict on successful LinkupClient.fetch()."""

    def test_success_returns_correct_shape(self):
        from src.mcp_servers.web_search_server import fetch_page

        mock_response = MagicMock()
        mock_response.content = "Clean page content here"
        mock_client = MagicMock()
        mock_client.fetch.return_value = mock_response
        mock_linkup_cls = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"LINKUP_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"linkup": MagicMock(LinkupClient=mock_linkup_cls)}):
                result = fetch_page("https://example.com")

        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["content"], "Clean page content here")
        self.assertIsNone(result["error"])

    def test_success_has_exactly_three_keys(self):
        from src.mcp_servers.web_search_server import fetch_page

        mock_response = MagicMock()
        mock_response.content = "Some content"
        mock_client = MagicMock()
        mock_client.fetch.return_value = mock_response
        mock_linkup_cls = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"LINKUP_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"linkup": MagicMock(LinkupClient=mock_linkup_cls)}):
                result = fetch_page("https://example.com")

        self.assertEqual(set(result.keys()), {"url", "content", "error"})


class TestFetchPageLinkupException(unittest.TestCase):
    """fetch_page returns error dict when LinkupClient.fetch() raises."""

    def test_exception_returns_error_dict(self):
        from src.mcp_servers.web_search_server import fetch_page

        mock_client = MagicMock()
        mock_client.fetch.side_effect = Exception("network failure")
        mock_linkup_cls = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"LINKUP_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"linkup": MagicMock(LinkupClient=mock_linkup_cls)}):
                result = fetch_page("https://example.com")

        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["content"], "")
        self.assertIn("network failure", result["error"])


class TestGetTeamStatsHttpError(unittest.TestCase):
    """get_team_stats returns structured error on HTTP error."""

    def test_http_error_returns_error_dict(self):
        from src.mcp_servers.ncaa_data_server import get_team_stats

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        http_error = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = http_error
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("src.mcp_servers.ncaa_data_server.httpx.Client", return_value=mock_client_instance):
            result = get_team_stats("duke", 2025)

        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIsNone(result["data"])
        self.assertIn("404", result["error"])


class TestGetTeamStatsSuccess(unittest.TestCase):
    """get_team_stats returns data on success."""

    def test_success_returns_data(self):
        from src.mcp_servers.ncaa_data_server import get_team_stats

        fake_data = {"team": "duke", "wins": 30, "losses": 5}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = fake_data

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("src.mcp_servers.ncaa_data_server.httpx.Client", return_value=mock_client_instance):
            result = get_team_stats("duke", 2025)

        self.assertIsInstance(result, dict)
        self.assertIsNone(result["error"])
        self.assertEqual(result["data"], fake_data)


class TestRateLimiterCalledBeforeNcaaApiCall(unittest.TestCase):
    """rate_limiter.acquire() is called before each NCAA API call."""

    def test_rate_limiter_acquire_called(self):
        import src.mcp_servers.ncaa_data_server as ncaa_module

        fake_data = {"scoreboard": []}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = fake_data

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch.object(ncaa_module.rate_limiter, "acquire") as mock_acquire:
            with patch("src.mcp_servers.ncaa_data_server.httpx.Client", return_value=mock_client_instance):
                ncaa_module.get_team_stats("kansas", 2025)

        mock_acquire.assert_called_once()

    def test_rate_limiter_acquire_called_for_scoreboard(self):
        import src.mcp_servers.ncaa_data_server as ncaa_module

        fake_data = {"games": []}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = fake_data

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch.object(ncaa_module.rate_limiter, "acquire") as mock_acquire:
            with patch("src.mcp_servers.ncaa_data_server.httpx.Client", return_value=mock_client_instance):
                ncaa_module.get_scoreboard("2025-03-20")

        mock_acquire.assert_called_once()


class TestGetScoreboardNetworkFailure(unittest.TestCase):
    """get_scoreboard returns structured error on network failure."""

    def test_connect_error_returns_error_dict(self):
        from src.mcp_servers.ncaa_data_server import get_scoreboard

        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = httpx.ConnectError("connection failed")
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)

        with patch("src.mcp_servers.ncaa_data_server.httpx.Client", return_value=mock_client_instance):
            result = get_scoreboard("2025-03-20")

        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIsNone(result["data"])
        self.assertIn("NCAA API request failed", result["error"])


if __name__ == "__main__":
    unittest.main()

# ---------------------------------------------------------------------------
# Property 9: fetch_page returns correct shape for any successful Linkup response
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st


@given(st.text(min_size=1, max_size=500))
@settings(max_examples=20, deadline=2000)
def test_property_fetch_page_correct_shape_on_success(content_str):
    """
    Property 9: fetch_page returns correct shape for any successful Linkup response.

    For any URL and any non-empty string returned by LinkupClient.fetch(),
    the dict returned by fetch_page(url) SHALL have exactly the keys
    url, content, and error, with error equal to None and content equal
    to the string returned by the Linkup client.

    Validates: Requirements 8.2
    """
    from src.mcp_servers.web_search_server import fetch_page

    mock_response = MagicMock()
    mock_response.content = content_str
    mock_client = MagicMock()
    mock_client.fetch.return_value = mock_response
    mock_linkup_cls = MagicMock(return_value=mock_client)

    test_url = "https://example.com/page"

    with patch.dict("os.environ", {"LINKUP_API_KEY": "test-key"}):
        with patch.dict("sys.modules", {"linkup": MagicMock(LinkupClient=mock_linkup_cls)}):
            result = fetch_page(test_url)

    assert set(result.keys()) == {"url", "content", "error"}, (
        f"Expected keys {{url, content, error}}, got {set(result.keys())}"
    )
    assert result["url"] == test_url
    assert result["error"] is None
    assert result["content"] == content_str
