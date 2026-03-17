# March Madness Bracket Predictor 🏀

A multi-AI-agent NCAA Men's Basketball Tournament bracket prediction system built with the [Strands Agents SDK](https://github.com/strands-agents/strands-agents-python) on AWS Bedrock. It accepts a CBS bracket PDF (or JSON input) via CLI, orchestrates 8 specialized sub-agents, and produces structured predictions with confidence scores for every matchup from the Round of 64 through the Championship.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   OrchestratorAgent                      │
│            (deterministic pipeline coordinator)          │
├─────────────────────────────────────────────────────────┤
│  PDF Parser → Structured Data → Qualitative Research    │
│  → Advanced Analytics → Matchup Analyst                 │
│  → Player/Injury → Prediction → Bracket Review          │
├─────────────────────────────────────────────────────────┤
│  Data Sources:                                           │
│  • NCAA API (ncaa-api.henrygd.me)                       │
│  • CBBD API (collegebasketballdata.com)                 │
│  • CBBpy (ESPN scraper)                                 │
│  • BartTorvik (tempo-free stats)                        │
│  • Linkup Search (web search + page fetch)              │
│  • Bedrock Claude Opus 4.6 (PDF vision extraction)      │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Python 3.12+**
- **AWS Account** with Bedrock access enabled (Claude Opus 4.6 model access)
- **AWS CLI** configured (`aws configure`)
- **API Keys:**
  - `LINKUP_API_KEY` — [Get one at linkup.so](https://app.linkup.so)
  - `CBBD_API_KEY` — [Get one at collegefootballdata.com](https://collegefootballdata.com/key)
- **Docker** (optional, for container deployment)

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/march-madness-bracket-predictor.git
cd march-madness-bracket-predictor
```

### 2. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

Then export them:

```bash
export LINKUP_API_KEY="your-linkup-api-key"
export CBBD_API_KEY="your-cbbd-api-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### 5. Configure AWS credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region (us-east-1)
```

Ensure your AWS account has access to the Claude Opus 4.6 model in Bedrock.

### 6. Run the predictor

**From a CBS bracket PDF:**

```bash
python -m src.main --bracket bracket.pdf --output predictions.json
```

**From a JSON bracket file:**

```bash
python -m src.main --bracket-json bracket.json --output predictions.json --verbose
```

**Resume from a specific round** (e.g., you already have Round of 64 results):

```bash
python -m src.main --bracket-json bracket.json \
  --round "Sweet 16" \
  --prior-results round_of_32_results.json \
  --output predictions.json
```

## CLI Arguments

| Argument | Description |
|---|---|
| `--bracket PATH` | Path to a CBS bracket PDF file |
| `--bracket-json PATH` | Path to a JSON bracket file (alternative to PDF) |
| `--output PATH` | Write complete JSON prediction output to this file |
| `--verbose` | Display detailed per-agent reasoning during processing |
| `--round ROUND` | Resume prediction from a specific round |
| `--prior-results PATH` | Path to prior results JSON (required with `--round`) |

One of `--bracket` or `--bracket-json` is required.

Valid `--round` values: `Round of 32`, `Sweet 16`, `Elite 8`, `Final Four`, `Championship`

## JSON Bracket Input Format

If using `--bracket-json`, provide a file with this structure:

```json
{
  "teams": [
    {"name": "Duke", "seed": 1, "region": "East"},
    {"name": "Vermont", "seed": 16, "region": "East"},
    {"name": "Kansas", "seed": 2, "region": "East"}
  ],
  "matchups": [
    {"team_a": "Duke", "team_b": "Vermont", "venue": "Indianapolis"}
  ],
  "season": 2026
}
```

Include all 64 teams across 4 regions (East, West, South, Midwest) with seeds 1-16 per region.

## Output Format

The output `predictions.json` contains:

```json
{
  "champion": "Duke",
  "champion_confidence": 72,
  "champion_path": ["Vermont", "Baylor", "Kentucky", "Houston", "Arizona", "Auburn"],
  "rounds": [
    {
      "round_name": "Round of 64",
      "upset_count": 6,
      "cinderella_candidates": ["Colorado State"],
      "matchups": [
        {
          "team_a": {"name": "Duke", "seed": 1, "region": "East"},
          "team_b": {"name": "Vermont", "seed": 16, "region": "East"},
          "winner": "Duke",
          "confidence": 97,
          "rationale": "Duke holds a commanding efficiency margin...",
          "key_factors": ["Efficiency Margin", "Seed History", "Matchup Factors"],
          "upset_alert": false
        }
      ]
    }
  ],
  "upset_alerts": [...],
  "cinderella_watch": [...]
}
```

## Running Tests

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -q -m "not slow"
```

Run the full suite including slow property tests:

```bash
python -m pytest tests/ -q
```

## Project Structure

```
├── src/
│   ├── main.py                    # CLI entry point
│   ├── agents/
│   │   ├── orchestrator.py        # Deterministic pipeline coordinator
│   │   ├── pdf_parser.py          # Bracket PDF extraction (pdfplumber + Claude vision)
│   │   ├── structured_data.py     # Team stats from NCAA/CBBD/CBBpy APIs
│   │   ├── advanced_analytics.py  # Tempo-free efficiency metrics
│   │   ├── matchup_analyst.py     # Haversine distance + matchup scoring
│   │   ├── player_injury.py       # Player stats + injury reports
│   │   ├── prediction.py          # Weighted prediction framework
│   │   ├── bracket_review.py      # Post-round review + flagging
│   │   └── team_research.py       # Qualitative web research
│   ├── mcp_servers/
│   │   ├── ncaa_data_server.py    # NCAA API FastMCP server
│   │   └── web_search_server.py   # Linkup search + fetch FastMCP server
│   ├── models/
│   │   ├── enums.py               # Region, RoundName enums
│   │   ├── team.py                # Team, Matchup, Bracket dataclasses
│   │   ├── prediction.py          # Prediction dataclass
│   │   ├── output.py              # BracketOutput, RoundResult
│   │   └── agent_outputs.py       # TeamStats, AdvancedMetrics, etc.
│   ├── utils/
│   │   ├── rate_limiter.py        # Thread-safe token-bucket rate limiter
│   │   ├── cbbd_client.py         # Direct httpx client for CBBD API
│   │   ├── cache.py               # Team data cache
│   │   ├── pdf_extractor.py       # PDF text + vision extraction
│   │   ├── seed_history.py        # Historical seed win rates
│   │   └── weights.py             # Prediction weight redistribution
│   └── data/
│       └── seed_history.json      # Historical seed matchup win rates
├── tests/                         # 202 tests (unit + Hypothesis property tests)
├── deploy/
│   └── agentcore-stack.yaml       # CloudFormation for Bedrock AgentCore Runtime
├── Dockerfile                     # Container for AgentCore deployment
├── requirements.txt               # Runtime dependencies
├── requirements-test.txt          # Test dependencies
└── .env.example                   # Template for API keys
```

## How It Works

1. **PDF Extraction**: pdfplumber attempts text extraction; if fewer than 64 teams are found, falls back to Claude Opus 4.6 vision to read the bracket image
2. **Data Gathering**: For each matchup, 5 sub-agents gather data in parallel:
   - Structured stats (NCAA API, CBBD, CBBpy)
   - Advanced analytics (CBBD efficiency, BartTorvik tempo-free)
   - Matchup analysis (Haversine proximity, seed baseline)
   - Player/injury assessment (CBBpy box scores, web search)
   - Qualitative research (Linkup web search)
3. **Prediction**: Weighted framework combines 8 factors (efficiency margin 25%, matchup factors 20%, momentum 15%, seed history 10%, location 10%, player/injury 10%, experience 5%, qualitative 5%)
4. **Review**: Bracket review agent flags questionable predictions for re-evaluation
5. **Advancement**: Winners advance to the next round; process repeats through Championship

## Prediction Weight Framework

| Factor | Weight | Data Source |
|---|---|---|
| Efficiency Margin | 25% | CBBD adjusted ratings |
| Matchup Factors | 20% | Seed baseline win rates |
| Momentum / Form | 15% | Scoring offense trends |
| Seed History | 10% | Historical seed matchup data |
| Location Advantage | 10% | Haversine campus-to-venue distance |
| Player / Injury | 10% | CBBpy stats + web search |
| Experience / Pedigree | 5% | Tournament history |
| Qualitative | 5% | Web search sentiment |

Weights are automatically redistributed when data sources are unavailable.

## Deployment (AWS Bedrock AgentCore)

The project includes a Dockerfile and CloudFormation template for deploying to AWS Bedrock AgentCore Runtime.

### 1. Build and push the Docker image

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository (first time only)
aws ecr create-repository --repository-name bracket-predictor --region us-east-1

# Build and push
docker build -t bracket-predictor .
docker tag bracket-predictor:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/bracket-predictor:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/bracket-predictor:latest
```

### 2. Store API keys in Secrets Manager

```bash
aws secretsmanager create-secret --name bracket-predictor/linkup-api-key \
  --secret-string "your-linkup-api-key" --region us-east-1

aws secretsmanager create-secret --name bracket-predictor/cbbd-api-key \
  --secret-string "your-cbbd-api-key" --region us-east-1
```

### 3. Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --template-file deploy/agentcore-stack.yaml \
  --stack-name bracket-predictor \
  --capabilities CAPABILITY_IAM \
  --region us-east-1 \
  --parameter-overrides \
    ImageUri=YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/bracket-predictor:latest \
    LinkupApiKeyArn=arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:bracket-predictor/linkup-api-key-XXXXXX \
    CbbdApiKeyArn=arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:bracket-predictor/cbbd-api-key-XXXXXX
```

## License

MIT
