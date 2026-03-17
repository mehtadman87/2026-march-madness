"""CLI entry point for the March Madness Bracket Predictor.

Parses command-line arguments, validates inputs, loads the bracket
(from PDF or JSON), invokes the OrchestratorAgent, and optionally
writes JSON output to a file.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 12.1, 12.2, 12.3, 12.5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from src.agents.orchestrator import OrchestratorAgent
from src.agents.pdf_parser import parse_bracket
from src.models.team import Bracket

logger = logging.getLogger(__name__)


def _resolve_secrets_from_arns() -> None:
    """Resolve API keys from Secrets Manager ARNs if ARN env vars are set.

    When deployed on AgentCore Runtime, the CloudFormation template injects
    LINKUP_API_KEY_SECRET_ARN and CBBD_API_KEY_SECRET_ARN as environment
    variables. This function fetches the secret values and sets the
    corresponding API key env vars so the rest of the application works
    without any changes.

    Falls back gracefully if boto3 is unavailable or the ARNs are not set.
    """
    linkup_arn = os.environ.get("LINKUP_API_KEY_SECRET_ARN")
    cbbd_arn = os.environ.get("CBBD_API_KEY_SECRET_ARN")

    if not linkup_arn and not cbbd_arn:
        return  # running locally with keys already set directly

    try:
        import boto3  # type: ignore[import]
        # Use AWS_DEFAULT_REGION if set; otherwise boto3 falls back to
        # instance metadata (works on AgentCore Runtime / EC2 / ECS).
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
        client_kwargs = {"region_name": region} if region else {}
        client = boto3.client("secretsmanager", **client_kwargs)

        if linkup_arn and not os.environ.get("LINKUP_API_KEY"):
            secret = client.get_secret_value(SecretId=linkup_arn)
            os.environ["LINKUP_API_KEY"] = secret["SecretString"]
            logger.info("Resolved LINKUP_API_KEY from Secrets Manager.")

        if cbbd_arn and not os.environ.get("CBBD_API_KEY"):
            secret = client.get_secret_value(SecretId=cbbd_arn)
            os.environ["CBBD_API_KEY"] = secret["SecretString"]
            logger.info("Resolved CBBD_API_KEY from Secrets Manager.")

    except Exception as exc:
        logger.warning("Could not resolve API keys from Secrets Manager: %s", exc)


def validate_file_path(path: str) -> str:
    """Validate that a file exists and is readable.

    Args:
        path: File path to validate.

    Returns:
        The validated path (unchanged).

    Raises:
        SystemExit: With a descriptive error message and exit code 1
            if the file does not exist or is not readable.

    Requirements: 1.7
    """
    if not os.path.exists(path):
        print(
            f"error: file not found: {path!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not os.access(path, os.R_OK):
        print(
            f"error: file is not readable: {path!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    return path


def main() -> None:
    """Parse CLI arguments, validate inputs, and invoke the OrchestratorAgent.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 12.5
    """
    # Resolve API keys from Secrets Manager ARNs when running on AgentCore Runtime
    _resolve_secrets_from_arns()

    parser = argparse.ArgumentParser(
        prog="bracket-predictor",
        description="NCAA March Madness bracket prediction system",
    )

    # Bracket input (mutually exclusive group — at least one required)
    bracket_group = parser.add_mutually_exclusive_group()
    bracket_group.add_argument(
        "--bracket",
        metavar="PATH",
        help="path to CBS bracket PDF file",
    )
    bracket_group.add_argument(
        "--bracket-json",
        metavar="PATH",
        dest="bracket_json",
        help="path to JSON bracket file (alternative to PDF)",
    )

    # Output options
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="write complete JSON prediction output to this file path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="display detailed per-agent reasoning during processing",
    )

    # Resumption options
    parser.add_argument(
        "--round",
        metavar="ROUND",
        dest="round",
        help=(
            "resume prediction from this round "
            "(e.g. 'Round of 32', 'Sweet 16', 'Elite 8', 'Final Four', 'Championship')"
        ),
    )
    parser.add_argument(
        "--prior-results",
        metavar="PATH",
        dest="prior_results",
        help="path to prior results JSON file (required when using --round)",
    )

    args = parser.parse_args()

    # Requirement 1.6 — require at least one bracket input
    if args.bracket is None and args.bracket_json is None:
        print(
            "error: one of the following arguments is required: --bracket, --bracket-json",
            file=sys.stderr,
        )
        parser.print_usage(sys.stderr)
        sys.exit(1)

    # Requirement 1.7 — validate all provided file paths
    if args.bracket is not None:
        validate_file_path(args.bracket)

    if args.bracket_json is not None:
        validate_file_path(args.bracket_json)

    if args.prior_results is not None:
        validate_file_path(args.prior_results)

    # Load bracket
    if args.bracket is not None:
        # Requirement 1.1 — parse bracket from PDF
        raw = parse_bracket(args.bracket)
        bracket = Bracket.from_dict(raw)
    else:
        # Requirement 1.2 — load bracket from JSON file
        with open(args.bracket_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        bracket = Bracket.from_dict(data)

    # Load prior results if provided (Requirement 1.5)
    prior_results: dict | None = None
    if args.prior_results is not None:
        with open(args.prior_results, "r", encoding="utf-8") as fh:
            prior_results = json.load(fh)

    # Determine start round
    start_round: str = args.round if args.round else "Round of 64"

    # Invoke orchestrator (Requirements 1.1–1.5)
    orchestrator = OrchestratorAgent()
    result = orchestrator.run(
        bracket=bracket,
        start_round=start_round,
        prior_results=prior_results,
        verbose=args.verbose,
    )

    # Display console summary (Requirement 12.4)
    print(result.to_console_summary())

    # Requirement 1.3 / 12.5 — write JSON output to file if --output provided
    if args.output is not None:
        json_output = result.to_json()
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(json_output)
        print(f"Output written to: {args.output}")


if __name__ == "__main__":
    main()
