# Supply Chain Orchestrator — Developer Setup & Execution Guide

This document provides step-by-step instructions for engineers to set up, configure, run, and test the **Supply Chain Orchestrator** multi-agent codebase locally.

---

## 1. Prerequisites

Before starting, ensure your system has the following software installed:

- **Python 3.11 or higher**
  > ⚠️ **Important Note on Python Distribution:**
  > You **must** use standard CPython (downloaded from [python.org](https://www.python.org/downloads/) or installed via `pyenv` / `brew`).
  > **Do not use MSYS2 / MinGW Python**, as `pydantic-core` requires Rust/maturin compilation under MSYS2, whereas standard CPython includes pre-built wheels.
- **PostgreSQL 14 or higher** (running locally or accessible via network)
- **Git**

---

## 2. Local Environment Setup

### Step 2.1: Clone the Repository

```bash
git clone https://github.com/your-org/AgentVerse.git
cd AgentVerse
```

### Step 2.2: Create and Activate a Virtual Environment

**On Windows (PowerShell / Command Prompt):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2.3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Verify installation:
```bash
python -c "import langgraph, google.genai, asyncpg, pydantic; print('Dependencies installed successfully!')"
```

---

## 3. Environment Variables Configuration

Copy the example environment file to `.env`:

**On Windows:**
```powershell
copy .env.example .env
```

**On macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` in your code editor and configure the parameters:

```ini
# ── PostgreSQL ──────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:password@localhost:5432/supply_chain

# ── Google Gemini API ───────────────────────────────────────
GOOGLE_API_KEY=your_actual_google_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# ── GitHub Models (Fallback LLM) ─────────────────────────────
GITHUB_TOKEN=your_actual_github_token
GITHUB_MODELS_ENDPOINT=https://models.inference.ai.azure.com
GITHUB_MODEL=gpt-4o-mini

# ── Application Settings ─────────────────────────────────────
LOG_LEVEL=INFO
ENVIRONMENT=development
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10
```

---

## 4. Database Initialization

### Step 4.1: Create the Database

Open a terminal or PostgreSQL client (`psql`) and create the database:

```bash
psql -U postgres -c "CREATE DATABASE supply_chain;"
```

### Step 4.2: Apply Schema DDL & Seed Data

Execute `db/schema.sql` to build the `sco` schema (13 tables, custom enums, and indexes), then execute `db/seed.sql` to insert initial test records:

```bash
# 1. Apply Schema DDL
psql -U postgres -d supply_chain -f db/schema.sql

# 2. Populate Seed Data
psql -U postgres -d supply_chain -f db/seed.sql
```

### Step 4.3: Verify Database Tables

```bash
psql -U postgres -d supply_chain -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'sco';"
```

Expected output:
```
        table_name       
-------------------------
 warehouses
 products
 inventory
 inventory_transactions
 demand_forecasts
 orders
 order_items
 vehicles
 routes
 route_stops
 shipments
 notifications
 agent_task_log
(13 rows)
```

---

## 5. Running the Application

### Option A: Run via FastAPI Web Server

To start the FastAPI application with live hot-reloading:

```bash
python main.py
```

The server will start at `http://localhost:8000`. You can inspect endpoints and open interactive API docs at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Probe:** [http://localhost:8000/health](http://localhost:8000/health)

### Option B: Run CLI Smoke Test

To verify database pool connectivity and system initialization without running a web server:

```bash
python main.py --cli
```

Expected CLI output:
```
10:00:00 │ sco.main                     │ INFO    │ Running in CLI mode…
10:00:00 │ db.connection                │ INFO    │ Creating asyncpg connection pool → postgresql://...
10:00:00 │ db.connection                │ INFO    │ Connection pool created (min=2, max=10)
10:00:00 │ sco.main                     │ INFO    │ Connected to PostgreSQL: PostgreSQL 16.1 ...
10:00:00 │ db.connection                │ INFO    │ Connection pool closed.
10:00:00 │ sco.main                     │ INFO    │ CLI smoke test passed ✅
```

---

## 6. Running the Test Suite

The test suite uses `pytest` and `pytest-asyncio` with mocked database connections (`asyncpg`) and mocked LLM responses (`LLMService`).

### Run All Unit Tests

```bash
pytest tests/ -v
```

### Run Tests for a Specific Agent

```bash
# Test Agent 1: Inventory Planning Agent
pytest tests/test_inventory_agent.py -v

# Test Agent 2: Warehouse Operations Agent
pytest tests/test_warehouse_agent.py -v

# Test Agent 3: Demand Forecasting Agent
pytest tests/test_demand_agent.py -v

# Test Agent 4: Route Optimization Agent
pytest tests/test_route_agent.py -v

# Test Agent 5: Fleet Management Agent
pytest tests/test_fleet_agent.py -v

# Test Agent 6: Customer Notification Agent
pytest tests/test_notification_agent.py -v
```

---

## 7. Development Guidelines

1. **Async Safety:** Always use `async/await` when writing database or LLM calls. Never invoke blocking synchronous I/O on event loops.
2. **LLM Fallbacks:** Every new agent function must implement a deterministic fallback path in case `llm_service.generate()` raises an exception.
3. **Task Logging:** Audit every agent execution by writing an entry to the `sco.agent_task_log` table using `execute_command`.
4. **Data Validation:** Define Pydantic models in `models/` for any new domain entities, ensuring `from_attributes = True` is set.
