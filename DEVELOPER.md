# Supply Chain Orchestrator — Developer Setup & Execution Guide

This guide provides technical instructions for software engineers to set up, configure, run, and test the **Supply Chain Orchestrator** multi-agent codebase locally.

---

## 1. Prerequisites

Ensure your development machine has the following software installed:

- **Python 3.11 or 3.12 (Standard CPython)**
  > ⚠️ **Critical Python Distribution Requirement:**  
  > You **must** use standard CPython (downloaded from [python.org](https://www.python.org/downloads/) or installed via `py` launcher).  
  > **Do not use MSYS2 / MinGW Python**, as packages with Rust/C extensions (such as `pydantic-core`, `uuid-utils`, `asyncpg`) do not have pre-compiled wheels for MSYS2 Python and will fail during installation.
- **PostgreSQL 14 or higher** (running locally on port 5432)
- **Git**

---

## 2. Local Environment Setup

### Step 2.1: Clone the Repository

```bash
git clone https://github.com/your-org/AgentVerse.git
cd AgentVerse
```

### Step 2.2: Create and Activate a Virtual Environment

**On Windows (PowerShell):**
```powershell
# Create virtual environment using standard CPython launcher
py -3.12 -m venv .venv

# Allow script execution for current session if needed
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
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
python -c "import langgraph, google.genai, asyncpg, pydantic, fastapi, streamlit; print('All dependencies installed successfully!')"
```

---

## 3. Environment Variables Configuration

Copy the example environment file to `.env`:

**On Windows (PowerShell):**
```powershell
copy .env.example .env
```

**On macOS / Linux:**
```bash
cp .env.example .env
```

Edit `.env` and configure your credentials:

```ini
# ── PostgreSQL ──────────────────────────────────────────────
# Note: If your password contains special characters like '@', URL-encode them (e.g. '@' becomes '%40')
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/supply_chain

# ── Primary LLM: GitHub Models (OpenAI-compatible) ──────────
GITHUB_TOKEN=your_actual_github_token
GITHUB_MODELS_ENDPOINT=https://models.inference.ai.azure.com
GITHUB_MODEL=gpt-4o-mini

# ── Secondary Fallback LLM: Google Gemini ───────────────────
GOOGLE_API_KEY=your_actual_google_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash

# ── Application Settings ─────────────────────────────────────
LOG_LEVEL=INFO
ENVIRONMENT=development
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10
```

---

## 4. Database Initialization

### Step 4.1: Create Database

Open `psql` or run via terminal:

```bash
psql -U postgres -c "CREATE DATABASE supply_chain;"
```

### Step 4.2: Apply Schema DDL & Seed Data

**Option A: From Terminal (PowerShell / Command Prompt)**
```powershell
# Apply DDL Schema
psql -U postgres -d supply_chain -f backend/db/schema.sql

# Insert Seed Dataset
psql -U postgres -d supply_chain -f backend/db/seed.sql
```

**Option B: From inside the `psql` Interactive Prompt (`supply_chain=#`)**
```sql
\c supply_chain
\i db/schema.sql
\i db/seed.sql
```

### Step 4.3: Verify Database Tables

```bash
psql -U postgres -d supply_chain -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'sco';"
```

Expected output:
```
       table_name
------------------------
 warehouses
 inventory
 products
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

## 5. Running the Application (Dual-Terminal Setup)

To run the complete platform, open **two separate terminals**:

### Terminal 1: Launch FastAPI Backend Server

```powershell
cd backend
.\venv\Scripts\activate
python main.py
```
- **Backend API:** `http://localhost:8000`
- **Swagger Interactive API Docs:** `http://localhost:8000/docs`
- **Health Check Probe:** `http://localhost:8000/health`

### Terminal 2: Launch React 19 Frontend UI

```powershell
cd ui
npm install
npm run dev
```
- **Frontend Dashboard & Chat:** `http://localhost:5173`
- Features interactive telemetry charts, single/multi-agent mode toggle, and rich Markdown rendering (`react-markdown`).

---

## 6. Running the Unit Test Suite

The project includes unit tests for all 6 agents, the LangGraph supervisor, and the FastAPI endpoints.

```powershell
# Activate environment
.\.venv\Scripts\activate

# Run all test suites
pytest tests/ -v
```

### Run Tests for Specific Components

```powershell
# 1. Test Agents
pytest tests/test_inventory_agent.py -v
pytest tests/test_warehouse_agent.py -v
pytest tests/test_demand_agent.py -v
pytest tests/test_route_agent.py -v
pytest tests/test_fleet_agent.py -v
pytest tests/test_notification_agent.py -v

# 2. Test LangGraph Supervisor Orchestrator
pytest tests/test_supervisor.py -v

# 3. Test FastAPI REST API
pytest tests/test_main.py -v
```

---

## 7. CLI Smoke Test Mode

To verify database pool connectivity and system initialization without starting the web server:

```powershell
python main.py --cli
```

Expected output:
```
09:43:43 │ sco.main     │ INFO │ Running in CLI mode…
09:43:43 │ db.connection │ INFO │ Creating asyncpg connection pool → postgresql://...
09:43:43 │ db.connection │ INFO │ Connection pool created (min=2, max=10)
09:43:43 │ sco.main     │ INFO │ Connected to PostgreSQL: PostgreSQL 18.4...
09:43:43 │ db.connection │ INFO │ Connection pool closed.
09:43:43 │ sco.main     │ INFO │ CLI smoke test passed ✅
```
