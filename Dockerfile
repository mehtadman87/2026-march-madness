FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# API keys are injected at runtime via environment variables.
# The application logs a warning at startup if they are missing.
ENV LINKUP_API_KEY=""
ENV CBBD_API_KEY=""

# AgentCore Runtime requires /ping and /invocations on port 8080.
EXPOSE 8080

ENTRYPOINT ["python", "-m", "src.main"]
