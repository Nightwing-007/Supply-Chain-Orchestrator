# Supply Chain Orchestrator 🚛

**Smart Logistics Multi-Agent System** — built for a 2-day hackathon.

Six specialised AI agents, orchestrated by a LangGraph supervisor, manage end-to-end supply chain operations: inventory planning, warehouse ops, demand forecasting, route optimisation, fleet management, and customer notifications.

## Architecture

```
User Query → LangGraph Supervisor → Agent 1..6 → PostgreSQL (shared state) → Response
                                        ↕
                              Gemini 2.5 Flash / GPT-4o-mini
```

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv && .venv\Scripts\activate    # Windows
# python -m venv .venv && source .venv/bin/activate  # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env   # then fill in your API keys

# 4. Set up PostgreSQL database
psql -U postgres -c "CREATE DATABASE supply_chain;"
psql -U postgres -d supply_chain -f db/schema.sql
psql -U postgres -d supply_chain -f db/seed.sql

# 5. Run the server
python main.py

# Or run CLI smoke test
python main.py --cli
```

## Project Structure

| Directory | Purpose |
|---|---|
| `config/` | Centralised settings (env vars, model params) |
| `db/` | Schema, seed data, async connection pool |
| `models/` | Pydantic models for all domains |
| `agents/` | 6 independent AI agents |
| `orchestrator/` | LangGraph supervisor + shared state |
| `services/` | LLM client (Gemini + GitHub Models) |
| `tests/` | pytest-based test suite |

## Tech Stack

- **Python 3.11+** with full `async/await`
- **LangGraph** for multi-agent orchestration
- **Google Gemini 2.5 Flash** (primary LLM)
- **GPT-4o-mini via GitHub Models** (fallback LLM)
- **PostgreSQL + asyncpg** for shared state
- **FastAPI + Uvicorn** for HTTP API
- **Pydantic v2** for data validation

## Development Phases

- **Phase 1 (Day 1):** Build 6 agents as independent async functions with strict JSON I/O
- **Phase 2 (Day 2):** LangGraph supervisor, intent routing, shared state graph
