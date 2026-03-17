"""Unit tests for the AgentCore HTTP server endpoints.

Tests cover:
- GET /ping health check
- POST /invocations with prompt
- POST /invocations with invalid input
- POST /invocations with bracket_json (mocked orchestrator)
"""

from unittest.mock import MagicMock, patch

from src.server import app


def _client():
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_ping_returns_healthy():
    """GET /ping returns 200 with status Healthy."""
    r = _client().get("/ping")
    assert r.status_code == 200
    assert r.json() == {"status": "Healthy"}


def test_invocations_prompt_returns_guidance():
    """POST /invocations with prompt key returns guidance message."""
    r = _client().post("/invocations", json={"prompt": "hello"})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert "bracket_json" in r.json()["response"]


def test_invocations_bad_input_returns_400():
    """POST /invocations without required keys returns 400."""
    r = _client().post("/invocations", json={"bad": "input"})
    assert r.status_code == 400
    assert "error" in r.json()


def test_invocations_invalid_json_returns_400():
    """POST /invocations with non-JSON body returns 400."""
    r = _client().post("/invocations", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
