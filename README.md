# March Madness Bracket Predictor 🏀

A multi-AI-agent NCAA Men's Basketball Tournament bracket prediction system built with the [Strands Agents SDK](https://github.com/strands-agents/strands-agents-python) on AWS Bedrock. It accepts a CBS bracket PDF (or JSON input) via CLI, orchestrates 9 specialized sub-agents, and produces structured predictions with confidence scores for every matchup from the Round of 64 through the Championship.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   OrchestratorAgent                      │
│            (deterministic pipeline coordinator)          │
├─────────────────────────────────────────────────────────┤
│  PDF Parser → Structured Data → Qualitative Research    │
│  → Advanced Analytics → Matchup Analyst                 │
│  → Player/Injury → Historical Stats → Prediction        │
│  → Bracket Review                                        │
├─────────────────────────────────────────────────────────┤
│  Data Sources:                                           │
│  • ESPN API (free, no auth — primary source)            │
│  • Linkup Search (web search + page fetch)              │
│  • Bedrock Claude Opus 4.6 (PDF vision extraction)      │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Python 3.12+**
- **AWS Account** with Bedrock access (Claude Opus 4.6)
- **AWS CLI** configured (`aws configure`)
- **API Keys:**
  - `LINKUP_API_KEY` — [Get one at linkup.so](https://app.linkup.so)
  - `CBBD_API_KEY` — [Get one at collegefootballdata.com](https://collegefootballdata.com/key) (optional)
- **No API key needed** for ESPN data (free public API)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/march-madness-bracket-predictor.git
cd march-madness-bracket-predictor
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env  # Edit with your API keys
export LINKUP_API_KEY="your-key"
export AWS_DEFAULT_REGION="us-east-1"

# Run
python -m src.main --bracket bracket.pdf --output predictions.json
```

## Usage

**From a CBS bracket PDF:**
```bash
python -m src.main --bracket bracket.pdf --output predictions.json
```

**From a JSON bracket file:**
```bash
python -m src.main --bracket-json bracket.json --output predictions.json --verbose
```

**Resume from a specific round:**
```bash
python -m src.main --bracket-json bracket.json \
  --round "Sweet 16" --prior-results prior.json --output predictions.json
```

| Argument | Description |
|---|---|
| `--bracket PATH` | CBS bracket PDF file |
| `--bracket-json PATH` | JSON bracket file |
| `--output PATH` | Output JSON file |
| `--verbose` | Show per-agent reasoning |
| `--round ROUND` | Resume from round |
| `--prior-results PATH` | Prior results JSON |

## The 9 Sub-Agents

| Agent | Purpose | Data Source |
|---|---|---|
| PDF Parser | Extract bracket from PDF | pdfplumber + Claude Opus 4.6 |
| Structured Data | Team season statistics | ESPN API (primary) |
| Advanced Analytics | Tempo-free efficiency metrics | ESPN API, BartTorvik |
| Historical Stats | Year-over-year trend analysis | ESPN API (current + previous season) |
| Matchup Analyst | Location advantage + matchup scoring | Haversine formula, seed history |
| Player/Injury | Roster composition + injury impact | ESPN, Linkup web search |
| Team Research | Qualitative scouting reports | Linkup web search |
| Prediction | Weighted winner prediction | All agent outputs combined |
| Bracket Review | Post-round quality check | Prediction analysis |

## Prediction Weight Framework

| Factor | Weight | Source |
|---|---|---|
| Efficiency Margin | 25% | ESPN adjusted ratings |
| Matchup Factors | 20% | Seed baseline win rates |
| Momentum / Form | 15% | Scoring offense + historical improvement (60/40 blend) |
| Seed History | 10% | Historical seed matchup data |
| Location Advantage | 10% | Haversine campus-to-venue distance |
| Player / Injury | 10% | ESPN stats + web search |
| Experience / Pedigree | 5% | Tournament history |
| Qualitative | 5% | Web search sentiment |

## Team Name Normalization

Bracket PDFs often use abbreviations. The system automatically normalizes them:
- `Iowa St.` → Iowa State | `MICHST` → Michigan State
- `SFLA` → South Florida | `N. Iowa` → Northern Iowa
- `NDAKST` → North Dakota State | `Tenn. State` → Tennessee State

The Claude vision prompt also requests full names, and a fuzzy matcher handles any remaining mismatches.

## Running Tests

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -q -m "not slow"    # 206 tests, ~5 seconds
python -m pytest tests/ -q                   # includes slow property tests
```

## Project Structure

```
├── src/
│   ├── main.py                    # CLI entry point
│   ├── server.py                  # HTTP server for AgentCore Runtime
│   ├── agents/                    # 9 specialized sub-agents
│   │   ├── orchestrator.py        # Deterministic pipeline coordinator
│   │   ├── historical_stats.py    # ESPN current + previous season comparison
│   │   └── ...
│   ├── utils/
│   │   ├── espn_client.py         # ESPN API client (free, no auth, cached)
│   │   ├── team_names.py          # Bracket abbreviation normalization
│   │   └── ...
│   └── data/
│       ├── seed_history.json      # Historical seed matchup win rates
│       └── espn_team_ids.json     # Cached ESPN team ID mapping
├── tests/                         # 206 tests
├── deploy/agentcore-stack.yaml    # CloudFormation template
├── Dockerfile                     # Container (FastAPI on port 8080)
└── requirements.txt
```

## Deployment (AWS Bedrock AgentCore)

The container exposes `GET /ping` and `POST /invocations` on port 8080 per AgentCore requirements.

```bash
# Build and push
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker build -t bracket-predictor .
docker tag bracket-predictor:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/bracket-predictor:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/bracket-predictor:latest

# Store secrets
aws secretsmanager create-secret --name bracket-predictor/linkup-api-key \
  --secret-string "your-key" --region us-east-1

# Deploy stack
aws cloudformation deploy --template-file deploy/agentcore-stack.yaml \
  --stack-name bracket-predictor --capabilities CAPABILITY_IAM --region us-east-1 \
  --parameter-overrides ImageUri=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/bracket-predictor:latest \
    LinkupApiKeyArn=arn:aws:secretsmanager:... CbbdApiKeyArn=arn:aws:secretsmanager:...
```

## License

MIT
