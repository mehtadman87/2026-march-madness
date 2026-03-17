"""HTTP server for AgentCore Runtime deployment.

Exposes the required endpoints for Bedrock AgentCore Runtime:
  GET  /ping         — health check
  POST /invocations  — bracket prediction

Also preserves CLI mode when run directly via `python -m src.main`.

Reference: https://docs.aws.amazon.com/marketplace/latest/userguide/bedrock-agentcore-runtime.html
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="March Madness Bracket Predictor")


@app.get("/ping")
def ping():
    """Health check endpoint required by AgentCore Runtime."""
    return {"status": "Healthy"}


@app.post("/invocations")
async def invocations(request: Request):
    """Prediction endpoint required by AgentCore Runtime.

    Accepts JSON with either:
      {"bracket_json": {...}}          — bracket data as JSON object
      {"bracket_pdf_base64": "..."}    — base64-encoded bracket PDF

    Returns the full BracketOutput JSON.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON in request body"},
        )

    # Resolve secrets if running on AgentCore
    from src.main import _resolve_secrets_from_arns
    _resolve_secrets_from_arns()

    try:
        from src.agents.orchestrator import OrchestratorAgent
        from src.agents.pdf_parser import parse_bracket
        from src.models.team import Bracket

        bracket_dict = None

        # Option 1: bracket_json provided directly
        if "bracket_json" in body:
            bracket_dict = body["bracket_json"]

        # Option 2: base64-encoded PDF
        elif "bracket_pdf_base64" in body:
            pdf_bytes = base64.b64decode(body["bracket_pdf_base64"])
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
            try:
                bracket_dict = parse_bracket(tmp_path)
            finally:
                os.unlink(tmp_path)

        # Option 3: prompt-based (simple text query)
        elif "prompt" in body:
            return JSONResponse(content={
                "response": "This agent accepts bracket data via 'bracket_json' or 'bracket_pdf_base64' keys. "
                            "Please provide a bracket to generate predictions.",
                "status": "success",
            })

        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Request must include 'bracket_json', 'bracket_pdf_base64', or 'prompt'"},
            )

        if bracket_dict is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Could not extract bracket data from the provided input"},
            )

        # Run the prediction pipeline
        bracket = Bracket.from_dict(bracket_dict)
        orchestrator = OrchestratorAgent()
        result = orchestrator.run(bracket=bracket)

        return JSONResponse(content=json.loads(result.to_json()))

    except Exception as exc:
        logger.error("Invocation error: %s\n%s", exc, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )


def start_server():
    """Start the uvicorn server on port 8080 (AgentCore requirement)."""
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    start_server()
