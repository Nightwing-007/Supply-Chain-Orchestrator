# Supply Chain Orchestrator — CampusOS 🚛

**Smart Logistics Multi-Agent System Powered by LangGraph, PostgreSQL, FastAPI, GitHub Models & Google Gemini**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2014%2B-blue.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite-blue.svg)](https://react.dev/)
[![LLM API](https://img.shields.io/badge/LLM-GPT--4o--mini%20(GitHub)%20%7C%20Gemini%202.0%20Flash-green.svg)](https://github.com/marketplace/models)

---

## Executive Summary

**Supply Chain Orchestrator** is an enterprise-grade, autonomous multi-agent logistics platform built for smart supply chain intelligence. Combining Python, LangGraph, PostgreSQL, FastAPI, React 19, GitHub Models (GPT-4o-mini), and Google Gemini 2.0 Flash, the platform coordinates **6 specialised single AI agents** that operate harmoniously across inventory planning, warehouse operations, demand forecasting, route optimisation, fleet management, and customer communications.

By pairing deterministic domain algorithms (e.g., Cycle Sort, Nearest Neighbor TSP, Exponential Smoothing, PostgreSQL Window Functions, Haversine Distance) with cloud-based LLM reasoning, Supply Chain Orchestrator bridges operational silos into a self-correcting, real-time logistics engine.

---

## System Architecture: The 3-Phase Journey

```
                                  USER / JUDGE INTERFACE
                                ┌────────────────────────┐
                                │   React 19 / Vite UI   │
                                │      (ui/src/App.jsx)  │
                                └───────────┬────────────┘
                                            │ POST /api/workflow
                                            ▼
                                   FASTAPI REST SERVER
                                ┌────────────────────────┐
                                │       (main.py)        │
                                └───────────┬────────────┘
                                            │
                                            ▼
                                LANGGRAPH SUPERVISOR GRAPH
                         ┌─────────────────────────────────────┐
                         │      (orchestrator/supervisor.py)   │
                         └──────────────────┬──────────────────┘
                                            │
       ┌───────────────────┬────────────────┼───────────────────┬───────────────────┐
       │                   │                │                   │                   │
       ▼                   ▼                ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Agent 1:    │   │  Agent 2:    │  │  Agent 3:    │   │  Agent 4:    │   │  Agent 5:    │   │  Agent 6:    │
│ Inventory    │   │  Warehouse   │  │  Demand      │   │  Route       │   │  Fleet       │   │  Customer    │
│ Planning     │   │  Operations  │  │  Forecasting │   │  Optimisation│   │  Management  │   │ Notification │
└──────┬───────┘   └──────┬───────┘  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                 │                  │                  │                  │
       └──────────────────┴─────────────────┼──────────────────┴──────────────────┴──────────────────┘
                                            ▼
                       PostgreSQL Shared State Store (sco Schema)
                                            ▲
                                            │
                       GitHub Models (Primary) / Google Gemini (Fallback)
```

### Phase 1: Modular Single AI Agents & Domain Guardrails (Single Agent Mode)
Built **6 independent, stateless async Python agents** with strict JSON input/output contracts. Each agent features:
- **Domain Guardrails:** Automatically evaluates user intent and gracefully rejects out-of-scope requests with polite redirection to the relevant domain agent or Multi-Agent Supervisor.
- **Conversational Formatting:** Formats chat outputs into detailed, self-contained Markdown with itemized metrics (SKUs, quantities, codes, distances) instead of vague summary phrases.
- **Algorithmic Core:** Heavy math and SQL processing paired with primary LLM inference (GitHub Models GPT-4o-mini) and secondary fallback (Google Gemini 2.0 Flash).

### Phase 2: LangGraph Supervisor Orchestrator & REST API (Multi Agent Mode)
Integrated all 6 agents into a **LangGraph StateGraph shared state network** managed by a central **Supervisor Routing Engine**. The supervisor analyzes state, past execution history, and user query to dynamically route execution to appropriate agents in iterative loops (`Supervisor ──► Agent ──► Supervisor ──► FINISH`). Exposed via a production-ready **FastAPI REST API** (`POST /api/workflow`) with connection pool lifespan hooks and OpenAPI documentation.

### Phase 3: React 19 UI, Real-Time Dashboard & Markdown Chat
Created a modern dark-mode interface in **React 19 + Vite + Tailwind CSS** (`ui/src/App.jsx`). Features:
- Interactive real-time metrics telemetry dashboard rendered with Recharts.
- Conversational chat interface with **`react-markdown`** parsing for rich formatting (bolding, lists, code blocks).
- Mode toggle for Single Agent vs. Multi-Agent Supervisor execution.

---

## The 6 Specialised AI Agents

| Agent | Domain Role | Algorithmic Core | LLM Synergy & Domain Guardrails |
|---|---|---|---|
| **1. Inventory Planning Agent** | Monitors stock levels across warehouses and generates reorder plans. | Low-stock deficit detection (`quantity_on_hand <= reorder_point`), 4-tier priority classification. | Generates structured **Reorder Plans** with itemized SKU restock quantities; rejects out-of-scope queries gracefully. |
| **2. Warehouse Operations Agent** | Manages warehouse capacity, layout efficiency, and pick list ordering. | **Cycle Sort** algorithm by turnover frequency for minimal physical item moves; capacity thresholding (>85%). | Drafts **Warehouse Optimisation Plans** with space reallocation strategies and bottleneck warnings. |
| **3. Demand Forecasting Agent** | Predicts product demand over upcoming 7-day windows. | **PostgreSQL Window Functions** (`AVG() OVER`) + **Simple Exponential Smoothing (SES)** ($\alpha=0.3$). | Analyzes volatility signals to apply qualitative market trend adjustments ($\le \pm 30\%$). |
| **4. Route Optimization Agent** | Sequences delivery stops to minimize travel distance and time. | **Haversine Distance** math + **Nearest Neighbor (Greedy TSP)** route sequencing. | Evaluates live traffic/weather hazards and SLA deadlines to generate **Dynamic Route Adjustment Plans**. |
| **5. Fleet Management Agent** | Tracks fleet telemetry, service schedules, and vehicle health. | Telemetry calculations (`days_since_service`, `mileage_km`, `fuel_level_pct`) and utilization metrics. | Categorises flagged vehicles into **Immediate Grounding**, **Schedule End-of-Week**, or **Local Routes Only**. |
| **6. Customer Notification Agent** | Automates customer updates across Email and SMS channels. | Rule-based template generator for fallback messages categorized by operational event type. | Drafts empathetic, context-aware **Email & SMS messages** (SMS $\le 160$ chars) adapted to news severity. |

---

## Tech Stack

- **Core Language:** Python 3.11+ (Standard CPython) with full `async/await` execution
- **Multi-Agent Orchestration:** LangGraph (`StateGraph` state graph & conditional routing)
- **Database Layer:** PostgreSQL 14+ with `asyncpg` connection pooling
- **REST API Framework:** FastAPI + Uvicorn with CORS middleware
- **Frontend UI:** React 19 + Vite + Tailwind CSS + Lucide Icons + `react-markdown` (`ui/`)
- **Primary LLM:** GitHub Models GPT-4o-mini (via Azure-compatible OpenAI client)
- **Fallback LLM:** Google Gemini 2.0 Flash (via `google-genai` SDK)
- **Validation & Serialization:** Pydantic v2 & `pydantic-settings`
- **Testing:** `pytest` + `pytest-asyncio` + `httpx`

---

## Repository Structure

```
AgentVerse/
├── README.md                       # Full project architecture & showcase
├── DEVELOPER.md                    # Detailed developer setup & execution guide
├── LEARNING_GUIDE.md               # Step-by-step learning guide
├── .gitignore                      # Git ignore rule definitions
│
├── backend/                        # FastAPI Backend & Multi-Agent Core
│   ├── .env.example                # Template for environment variables
│   ├── requirements.txt            # Pinned Python dependencies
│   ├── main.py                     # FastAPI server & CLI entrypoint
│   │
│   ├── config/
│   │   └── settings.py             # Central Pydantic-settings configuration
│   │
│   ├── db/
│   │   ├── schema.sql              # PostgreSQL DDL (13 tables, enums, indexes)
│   │   ├── seed.sql                # Seed dataset
│   │   └── connection.py           # Singleton asyncpg connection pool
│   │
│   ├── services/
│   │   └── llm_service.py          # Unified LLM Gateway (GitHub Models Primary + Gemini Fallback)
│   │
│   ├── models/                     # Pydantic v2 domain schemas
│   ├── agents/                     # The 6 Specialised AI Agents with Domain Guardrails
│   ├── orchestrator/               # LangGraph StateGraph Supervisor Orchestrator
│   └── tests/                      # Async unit test suite (120+ test cases)
│
└── ui/                             # React 19 + Vite UI
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx                 # React Dashboard & Markdown Chat Interface
        └── api.js                  # Axios REST API client
```# Singleton asyncpg connection pool & query execution
│
├── models/                         # Pydantic v2 domain schemas
│   ├── inventory.py
│   ├── warehouse.py
│   ├── demand.py
│   ├── route.py
│   ├── fleet.py
│   └── notification.py
│
├── agents/                         # The 6 Specialised AI Agents
│   ├── inventory_agent.py          # Agent 1: Inventory Planning
│   ├── warehouse_agent.py          # Agent 2: Warehouse Operations
│   ├── demand_agent.py             # Agent 3: Demand Forecasting
│   ├── route_agent.py              # Agent 4: Route Optimization
│   ├── fleet_agent.py              # Agent 5: Fleet Management
│   └── notification_agent.py       # Agent 6: Customer Notification
│
├── orchestrator/
│   ├── state.py                    # GlobalLogisticsState TypedDict definition
│   └── supervisor.py               # LangGraph StateGraph Supervisor Orchestrator
│
├── frontend/
│   └── app.py                      # Streamlit UI & Live State Inspector Dashboard
│
└── tests/                          # Async unit test suite (35+ test cases)
    ├── test_inventory_agent.py
    ├── test_warehouse_agent.py
    ├── test_demand_agent.py
    ├── test_route_agent.py
    ├── test_fleet_agent.py
    ├── test_notification_agent.py
    ├── test_supervisor.py
    └── test_main.py
```
