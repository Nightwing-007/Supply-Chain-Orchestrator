# Supply Chain Orchestrator 🚛

**Smart Logistics Multi-Agent System Powered by LangGraph, PostgreSQL, and Google Gemini**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue.svg)](https://www.postgresql.org/)
[![LLM API](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash%20%7C%20GPT--4o--mini-green.svg)](https://ai.google.dev/)

---

## Executive Summary

**Supply Chain Orchestrator** is an enterprise-grade, multi-agent logistics intelligence system designed to solve complex supply chain fragmentation. Built using Python, LangGraph, PostgreSQL, and Google Gemini API, the platform coordinates six specialised single AI agents that operate harmoniously across inventory planning, warehouse operations, demand forecasting, route optimisation, fleet management, and customer notifications.

By combining deterministic algorithms (e.g., Cycle Sort, Nearest Neighbor TSP, Exponential Smoothing, PostgreSQL Window Functions) with cloud-based LLM reasoning, Supply Chain Orchestrator bridges operational silos into a self-correcting logistics engine.

---

## The Problem

Modern supply chain management suffers from systemic inefficiencies driven by data fragmentation and delayed decision-making:

- **Siloed Domain Intelligence:** Inventory managers, warehouse dispatchers, and fleet operators rely on disconnected spreadsheets and legacy ERPs, leading to stockouts and capacity bottlenecks.
- **Purely Reactive Planning:** Traditional systems lack predictive capability, failing to anticipate demand spikes or maintenance failures before they disrupt operations.
- **Communication Gaps:** Customers remain uninformed during delivery disruptions because logistics status updates are detached from customer service channels.
- **High Computational Overhead:** Local rule engines struggle to balance multi-variable trade-offs (e.g. traffic hazards vs SLA deadlines) in real time.

---

## The Solution

**Supply Chain Orchestrator** introduces a modular, multi-agent architecture where dedicated single AI agents execute domain-specific tasks and communicate via a shared relational state store.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          LANGGRAPH SUPERVISOR AGENT                              │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
 ┌───────────────────┬───────────────────┼───────────────────┬───────────────────┐
 │                   │                   │                   │                   │
 ▼                   ▼                   ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Agent 1:    │   │  Agent 2:    │   │  Agent 3:    │   │  Agent 4:    │   │  Agent 5:    │   │  Agent 6:    │
│ Inventory    │   │  Warehouse   │   │  Demand      │   │  Route       │   │  Fleet       │   │  Customer    │
│ Planning     │   │  Operations  │   │  Forecasting │   │  Optimisation│   │  Management  │   │ Notification │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │                  │                  │                  │
       └──────────────────┴──────────────────┼──────────────────┴──────────────────┴──────────────────┘
                                             ▼
                        PostgreSQL Shared State Store (sco Schema)
                                             ▲
                                             │
                        Google Gemini 2.5 Flash / GitHub Models
```

### Core Architecture Principles

1. **Hybrid Intelligence (Algorithmic + LLM):** Heavy data processing (distance matrices, rolling window aggregations, bin sorting) is executed deterministically in Python/SQL. The LLM is reserved for qualitative reasoning, context analysis, and natural language drafting.
2. **Resilience & Graceful Degradation:** Every agent implements a deterministic fallback mechanism. If an LLM call times out or fails, the system automatically falls back to rule-based execution without halting the workflow.
3. **Stateless Node Functions:** Each agent is designed as an asynchronous Python function accepting a `GlobalLogisticsState` snapshot and returning strict JSON partial state updates.
4. **Cloud-Only LLM Inference:** All reasoning is offloaded to cloud APIs (Google Gemini 2.5 Flash as primary, GPT-4o-mini via GitHub Models as fallback), ensuring low local memory consumption.

---

## The 6 Specialised AI Agents

| Agent | Core Role | Algorithmic Core | LLM Synergy & Reasoning |
|---|---|---|---|
| **1. Inventory Planning Agent** | Monitors stock levels across warehouses and generates reorder plans. | Low-stock deficit detection (`quantity_on_hand <= reorder_point`), 4-tier priority classification. | Generates structured **Reorder Plans** with restock quantities and justifications for low-stock items. |
| **2. Warehouse Operations Agent** | Manages warehouse capacity, layout efficiency, and pick list ordering. | **Cycle Sort** algorithm by turnover frequency for minimal physical item moves; capacity thresholding (>85%). | Drafts **Warehouse Optimisation Plans** with space reallocation strategies and bottleneck warnings. |
| **3. Demand Forecasting Agent** | Predicts product demand over upcoming 7-day windows. | **PostgreSQL Window Functions** (`AVG() OVER`) + **Simple Exponential Smoothing (SES)** ($\alpha=0.3$). | Analyzes volatility signals (7d vs 30d ratios) to apply qualitative market trend adjustments ($\le \pm 30\%$). |
| **4. Route Optimization Agent** | Sequences delivery stops to minimize travel distance and time. | **Haversine Distance** math + **Nearest Neighbor (Greedy TSP)** route sequencing. | Evaluates live traffic/weather hazards and SLA deadlines to generate **Dynamic Route Adjustment Plans**. |
| **5. Fleet Management Agent** | Tracks fleet telemetry, service schedules, and vehicle health. | Telemetry calculations (`days_since_service`, `mileage_km`, `fuel_level_pct`) and utilization metrics. | Categorises flagged vehicles into **Immediate Grounding**, **Schedule End-of-Week**, or **Local Routes Only**. |
| **6. Customer Notification Agent** | Automates customer updates across Email and SMS channels. | Rule-based template generator for fallback messages categorized by operational event type. | Drafts empathetic, context-aware **Email & SMS messages** (SMS $\le 160$ chars) adapted to news severity. |

---

## Technical Stack

- **Core Runtime:** Python 3.11+ with full `async/await` execution
- **Orchestration:** LangGraph (StateGraph shared state orchestration)
- **Database:** PostgreSQL with `asyncpg` driver and connection pooling
- **Primary LLM:** Google Gemini 2.5 Flash (via `google-genai` SDK)
- **Fallback LLM:** GPT-4o-mini (via GitHub Models / Azure OpenAI endpoint)
- **API Server:** FastAPI + Uvicorn
- **Validation & Serialization:** Pydantic v2 & `pydantic-settings`
- **Testing:** `pytest` + `pytest-asyncio`

---

## Project Structure

```
AgentVerse/
├── README.md                       # Project overview & high-level architecture
├── DEVELOPER.md                    # Step-by-step developer setup & execution guide
├── requirements.txt                # Pinned Python dependencies
├── .env.example                    # Template for environment variables
├── main.py                         # FastAPI web server and CLI entrypoint
│
├── config/
│   └── settings.py                 # Pydantic-settings central configuration
│
├── db/
│   ├── schema.sql                  # PostgreSQL schema DDL (13 tables, enums, indexes)
│   ├── seed.sql                    # Seed data (3 warehouses, 10 products, 5 vehicles, 3 orders)
│   └── connection.py               # Singleton asyncpg connection pool & query helpers
│
├── models/                         # Domain Pydantic models
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
│   └── supervisor.py               # LangGraph supervisor routing logic
│
└── tests/                          # Async unit test suite
    ├── test_inventory_agent.py
    ├── test_warehouse_agent.py
    ├── test_demand_agent.py
    ├── test_route_agent.py
    ├── test_fleet_agent.py
    └── test_notification_agent.py
```

---

## Development Phasing

- **Phase 1 (Day 1) — Complete:** Built all 6 modular agents as independent, stateless async Python functions with strict JSON input/output contracts, complete with unit tests and database audit logging.
- **Phase 2 (Day 2) — In Progress:** LangGraph Supervisor Agent integration, state graph routing, and PostgreSQL state persistence.
