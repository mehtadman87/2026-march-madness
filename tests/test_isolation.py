"""Test that verifies collection-order independence between test modules.

Confirms the full test suite passes when pytest collects test_orchestrator.py
before test_cli.py, i.e. that no module-level sys.modules pollution causes
OrchestratorAgent to resolve to a MagicMock in test_orchestrator.py.

Requirements: 6.4
"""

import subprocess
import sys


def test_orchestrator_before_cli_collection_order():
    """
    Run test_orchestrator.py then test_cli.py in that explicit order and
    assert both pass. This is the order that previously caused failures
    when test_cli.py inserted a MagicMock for src.agents.orchestrator at
    module level.

    Requirements: 6.4
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/test_orchestrator.py",
            "tests/test_cli.py",
            "-q", "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Tests failed when collected in orchestrator-first order.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
