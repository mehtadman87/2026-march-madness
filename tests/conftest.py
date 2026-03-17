"""
pytest configuration and shared fixtures for the test suite.

Provides properly-scoped sys.modules stubs for heavy dependencies (strands,
strands.models, cbbpy) and sub-agent modules that are not installed in the
test environment. Using session-scoped fixtures with autouse ensures stubs
are set up once and torn down cleanly, preventing cross-test pollution.
"""

import sys
import pytest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Early bootstrap — runs before any test module is imported
# ---------------------------------------------------------------------------
# Module-level code in test files (sys.modules.pop, imports) runs at
# collection time, before session fixtures. We must set up the strands
# identity-decorator stub here at conftest import time so it is in place
# when test modules are collected.


def _bootstrap_strands():
    """Set strands.tool to an identity decorator before any test module loads."""
    mock_strands = sys.modules.get("strands")
    if mock_strands is None or not isinstance(mock_strands, MagicMock):
        mock_strands = MagicMock()
        sys.modules["strands"] = mock_strands
    # Always ensure tool is an identity decorator
    mock_strands.tool = lambda fn: fn

    mock_strands_models = sys.modules.get("strands.models")
    if mock_strands_models is None:
        sys.modules["strands.models"] = MagicMock()


def _bootstrap_cbbpy():
    """Register cbbpy stubs before any test module loads."""
    mock_scraper = MagicMock()
    mock_cbbpy = MagicMock()
    mock_cbbpy.mens_scraper = mock_scraper
    sys.modules.setdefault("cbbpy", mock_cbbpy)
    sys.modules.setdefault("cbbpy.mens_scraper", mock_scraper)


# Run bootstraps immediately at conftest import time
_bootstrap_strands()
_bootstrap_cbbpy()


# ---------------------------------------------------------------------------
# Sub-agent modules needed by test_orchestrator.py
# ---------------------------------------------------------------------------

_ORCHESTRATOR_STUB_MODULES = [
    "src.agents.advanced_analytics",
    "src.agents.bracket_review",
    "src.agents.historical_stats",
    "src.agents.pdf_parser",
    "src.agents.structured_data",
    "src.agents.team_research",
]


@pytest.fixture(scope="session", autouse=True)
def stub_orchestrator_sub_agents():
    """Stub sub-agent modules that OrchestratorAgent imports but aren't tested directly."""
    originals = {}
    for mod in _ORCHESTRATOR_STUB_MODULES:
        originals[mod] = sys.modules.get(mod)
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

    yield

    for mod, original in originals.items():
        if original is None:
            sys.modules.pop(mod, None)
        else:
            sys.modules[mod] = original


# ---------------------------------------------------------------------------
# Custom markers
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (real time.sleep calls); run with -m slow",
    )
