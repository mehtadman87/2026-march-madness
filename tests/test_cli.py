"""Unit tests for CLI argument parsing and validation in src/main.py.

Requirements: 1.1, 1.2, 1.3, 1.6, 1.7
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub out heavy imports before src.main is loaded
# ---------------------------------------------------------------------------

_mock_strands = MagicMock()
sys.modules.setdefault("strands", _mock_strands)
sys.modules.setdefault("strands.models", MagicMock())

for _mod in [
    "src.agents.advanced_analytics",
    "src.agents.bracket_review",
    "src.agents.matchup_analyst",
    "src.agents.pdf_parser",
    "src.agents.player_injury",
    "src.agents.prediction",
    "src.agents.structured_data",
    "src.agents.team_research",
]:
    sys.modules.setdefault(_mod, MagicMock())
# NOTE: src.agents.orchestrator is NOT stubbed at module level — each test
# that needs it uses patch("src.main.OrchestratorAgent") scoped to that test.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_BRACKET_DICT = {"teams": [], "season": "2025"}


def _make_mock_result() -> MagicMock:
    """Return a mock BracketOutput with the methods main() calls."""
    result = MagicMock()
    result.to_console_summary.return_value = "Summary"
    result.to_json.return_value = json.dumps({"champion": "Duke"})
    return result


def _patch_main_deps(bracket_dict=None):
    """Return a context manager that patches OrchestratorAgent, parse_bracket, and Bracket."""
    if bracket_dict is None:
        bracket_dict = _VALID_BRACKET_DICT

    mock_result = _make_mock_result()
    mock_orch_instance = MagicMock()
    mock_orch_instance.run.return_value = mock_result
    mock_orch_cls = MagicMock(return_value=mock_orch_instance)

    mock_bracket_instance = MagicMock()
    mock_bracket_from_dict = MagicMock(return_value=mock_bracket_instance)

    return (
        patch("src.main.OrchestratorAgent", mock_orch_cls),
        patch("src.main.parse_bracket", return_value=bracket_dict),
        patch("src.main.Bracket.from_dict", mock_bracket_from_dict),
        mock_orch_instance,
        mock_result,
    )


# ---------------------------------------------------------------------------
# Tests: validate_file_path
# ---------------------------------------------------------------------------


class TestValidateFilePath(unittest.TestCase):
    """Tests for the validate_file_path helper.

    Requirements: 1.7
    """

    def test_valid_file_returns_path(self) -> None:
        """validate_file_path returns the path unchanged for an existing file."""
        from src.main import validate_file_path

        with tempfile.NamedTemporaryFile() as tmp:
            result = validate_file_path(tmp.name)
            self.assertEqual(result, tmp.name)

    def test_nonexistent_file_raises_system_exit(self) -> None:
        """validate_file_path raises SystemExit for a non-existent file."""
        from src.main import validate_file_path

        with self.assertRaises(SystemExit) as ctx:
            validate_file_path("/nonexistent/path/to/file.pdf")
        self.assertEqual(ctx.exception.code, 1)

    def test_nonexistent_file_prints_descriptive_error(self) -> None:
        """validate_file_path prints a descriptive error message to stderr."""
        from src.main import validate_file_path

        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            with self.assertRaises(SystemExit):
                validate_file_path("/no/such/file.pdf")
        self.assertIn("/no/such/file.pdf", stderr_buf.getvalue())


# ---------------------------------------------------------------------------
# Tests: --bracket (PDF path)
# ---------------------------------------------------------------------------


class TestBracketArgument(unittest.TestCase):
    """Test that --bracket with a real temp file is accepted.

    Requirements: 1.1
    """

    def test_valid_bracket_pdf_is_accepted(self) -> None:
        """--bracket with an existing file runs without SystemExit."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket", tmp.name]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit as exc:
                        self.fail(f"main() raised SystemExit({exc.code}) unexpectedly")

    def test_valid_bracket_invokes_orchestrator(self) -> None:
        """--bracket causes OrchestratorAgent.run() to be called."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket", tmp.name]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    mock_orch.run.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: --bracket-json
# ---------------------------------------------------------------------------


class TestBracketJsonArgument(unittest.TestCase):
    """Test that --bracket-json with a real temp file is accepted.

    Requirements: 1.2
    """

    def test_valid_bracket_json_is_accepted(self) -> None:
        """--bracket-json with an existing JSON file runs without SystemExit."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w") as tmp:
            json.dump(_VALID_BRACKET_DICT, tmp)
            tmp.flush()

            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket-json", tmp.name]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit as exc:
                        self.fail(f"main() raised SystemExit({exc.code}) unexpectedly")

    def test_valid_bracket_json_invokes_orchestrator(self) -> None:
        """--bracket-json causes OrchestratorAgent.run() to be called."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w") as tmp:
            json.dump(_VALID_BRACKET_DICT, tmp)
            tmp.flush()

            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket-json", tmp.name]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    mock_orch.run.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: missing bracket input
# ---------------------------------------------------------------------------


class TestMissingBracketInput(unittest.TestCase):
    """Test that omitting both --bracket and --bracket-json exits non-zero.

    Requirements: 1.6
    """

    def test_no_bracket_exits_nonzero(self) -> None:
        """No bracket argument → SystemExit with non-zero code."""
        with patch("sys.argv", ["bracket-predictor"]):
            from src.main import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertNotEqual(ctx.exception.code, 0)

    def test_no_bracket_prints_usage_error(self) -> None:
        """No bracket argument → error message written to stderr."""
        stderr_buf = io.StringIO()
        with patch("sys.argv", ["bracket-predictor"]):
            from src.main import main
            with contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(SystemExit):
                    main()
        output = stderr_buf.getvalue()
        # Should mention the required arguments
        self.assertTrue(
            "--bracket" in output or "required" in output or "usage" in output.lower(),
            msg=f"Expected usage hint in stderr, got: {output!r}",
        )


# ---------------------------------------------------------------------------
# Tests: invalid file path
# ---------------------------------------------------------------------------


class TestInvalidFilePath(unittest.TestCase):
    """Test that a non-existent file path exits non-zero with a descriptive error.

    Requirements: 1.7
    """

    def test_invalid_bracket_path_exits_nonzero(self) -> None:
        """--bracket with a non-existent path → SystemExit with code 1."""
        with patch("sys.argv", ["bracket-predictor", "--bracket", "/no/such/file.pdf"]):
            from src.main import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 1)

    def test_invalid_bracket_path_prints_descriptive_error(self) -> None:
        """--bracket with a non-existent path → error message contains the path."""
        stderr_buf = io.StringIO()
        with patch("sys.argv", ["bracket-predictor", "--bracket", "/no/such/file.pdf"]):
            from src.main import main
            with contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(SystemExit):
                    main()
        self.assertIn("/no/such/file.pdf", stderr_buf.getvalue())

    def test_invalid_bracket_json_path_exits_nonzero(self) -> None:
        """--bracket-json with a non-existent path → SystemExit with code 1."""
        with patch("sys.argv", ["bracket-predictor", "--bracket-json", "/no/such/bracket.json"]):
            from src.main import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 1)


# ---------------------------------------------------------------------------
# Tests: --output flag
# ---------------------------------------------------------------------------


class TestOutputFlag(unittest.TestCase):
    """Test that --output triggers JSON file write.

    Requirements: 1.3, 12.5
    """

    def test_output_flag_writes_json_file(self) -> None:
        """--output causes the JSON result to be written to the specified path."""
        orch_patch, parse_patch, bracket_patch, mock_orch, mock_result = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as bracket_tmp:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out_tmp:
                out_path = out_tmp.name

            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", [
                    "bracket-predictor",
                    "--bracket", bracket_tmp.name,
                    "--output", out_path,
                ]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass

            # Verify the file was written
            with open(out_path, "r") as fh:
                content = fh.read()
            self.assertTrue(len(content) > 0)
            # Verify it's valid JSON
            parsed = json.loads(content)
            self.assertIn("champion", parsed)

    def test_output_flag_calls_to_json(self) -> None:
        """--output causes result.to_json() to be called."""
        orch_patch, parse_patch, bracket_patch, mock_orch, mock_result = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as bracket_tmp:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out_tmp:
                out_path = out_tmp.name

            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", [
                    "bracket-predictor",
                    "--bracket", bracket_tmp.name,
                    "--output", out_path,
                ]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass

            mock_result.to_json.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: --verbose flag
# ---------------------------------------------------------------------------


class TestVerboseFlag(unittest.TestCase):
    """Test that --verbose is parsed and forwarded to the orchestrator.

    Requirements: 1.4
    """

    def test_verbose_flag_passed_to_orchestrator(self) -> None:
        """--verbose causes orchestrator.run() to receive verbose=True."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket", tmp.name, "--verbose"]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    _, kwargs = mock_orch.run.call_args
                    self.assertTrue(kwargs.get("verbose", False))

    def test_no_verbose_flag_defaults_false(self) -> None:
        """Without --verbose, orchestrator.run() receives verbose=False."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket", tmp.name]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    _, kwargs = mock_orch.run.call_args
                    self.assertFalse(kwargs.get("verbose", True))


# ---------------------------------------------------------------------------
# Tests: --round and --prior-results flags
# ---------------------------------------------------------------------------


class TestRoundAndPriorResultsFlags(unittest.TestCase):
    """Test that --round and --prior-results are parsed and forwarded.

    Requirements: 1.5
    """

    def test_round_flag_passed_to_orchestrator(self) -> None:
        """--round value is forwarded to orchestrator.run() as start_round."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as bracket_tmp:
            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", [
                    "bracket-predictor",
                    "--bracket", bracket_tmp.name,
                    "--round", "Sweet 16",
                ]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    _, kwargs = mock_orch.run.call_args
                    self.assertEqual(kwargs.get("start_round"), "Sweet 16")

    def test_prior_results_flag_passed_to_orchestrator(self) -> None:
        """--prior-results JSON is loaded and forwarded to orchestrator.run()."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()
        prior_data = {"Round of 64": []}

        with tempfile.NamedTemporaryFile(suffix=".pdf") as bracket_tmp:
            with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w", delete=False
            ) as prior_tmp:
                json.dump(prior_data, prior_tmp)
                prior_path = prior_tmp.name

            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", [
                    "bracket-predictor",
                    "--bracket", bracket_tmp.name,
                    "--prior-results", prior_path,
                ]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    _, kwargs = mock_orch.run.call_args
                    self.assertEqual(kwargs.get("prior_results"), prior_data)

    def test_no_round_defaults_to_round_of_64(self) -> None:
        """Without --round, start_round defaults to 'Round of 64'."""
        orch_patch, parse_patch, bracket_patch, mock_orch, _ = _patch_main_deps()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            with orch_patch, parse_patch, bracket_patch:
                with patch("sys.argv", ["bracket-predictor", "--bracket", tmp.name]):
                    from src.main import main
                    try:
                        main()
                    except SystemExit:
                        pass
                    _, kwargs = mock_orch.run.call_args
                    self.assertEqual(kwargs.get("start_round"), "Round of 64")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Tests: _resolve_secrets_from_arns
# ---------------------------------------------------------------------------


class TestResolveSecretsFromArns(unittest.TestCase):
    """Tests for the Secrets Manager ARN resolution helper.

    Covers the TD-NEW-004 fix: API keys are resolved from ARN env vars
    at container startup rather than via CloudFormation dynamic references.
    """

    def test_no_arns_set_is_noop(self) -> None:
        """When no ARN env vars are set, function returns without calling boto3."""
        from src.main import _resolve_secrets_from_arns

        env = {"LINKUP_API_KEY": "direct-key", "CBBD_API_KEY": "direct-key"}
        with patch.dict("os.environ", env, clear=False):
            with patch("src.main.os.environ.get", side_effect=lambda k, d=None: env.get(k, d)):
                # Should not raise even without boto3
                _resolve_secrets_from_arns()

    def test_resolves_linkup_key_from_arn(self) -> None:
        """When LINKUP_API_KEY_SECRET_ARN is set, fetches and sets LINKUP_API_KEY."""
        from src.main import _resolve_secrets_from_arns

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "resolved-linkup-key"}
        mock_boto3.client.return_value = mock_client

        env = {"LINKUP_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:linkup"}
        # Remove LINKUP_API_KEY so the function tries to resolve it
        env.pop("LINKUP_API_KEY", None)

        with patch.dict("os.environ", env, clear=True):
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                _resolve_secrets_from_arns()

        mock_client.get_secret_value.assert_called_once_with(
            SecretId="arn:aws:secretsmanager:us-east-1:123:secret:linkup"
        )

    def test_boto3_exception_does_not_crash(self) -> None:
        """If boto3 raises, the function logs a warning and does not propagate."""
        from src.main import _resolve_secrets_from_arns

        mock_boto3 = MagicMock()
        mock_boto3.client.side_effect = Exception("no credentials")

        env = {"LINKUP_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:x"}
        with patch.dict("os.environ", env, clear=True):
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                # Must not raise
                _resolve_secrets_from_arns()

    def test_skips_resolution_if_key_already_set(self) -> None:
        """Does not call get_secret_value if the API key is already in the environment."""
        from src.main import _resolve_secrets_from_arns

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        env = {
            "LINKUP_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:linkup",
            "LINKUP_API_KEY": "already-set",
        }
        with patch.dict("os.environ", env, clear=True):
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                _resolve_secrets_from_arns()

        mock_client.get_secret_value.assert_not_called()
