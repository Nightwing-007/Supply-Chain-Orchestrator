# Supply Chain Orchestrator — Autonomous Multi-Agent Logistics

> An enterprise-grade, autonomous supply chain command center powered by LangGraph multi-agent orchestration, a 3-tier resilient LLM fallback architecture, and real-time PostgreSQL telemetry.

---

## 📖 Overview

Modern global supply chains suffer from severe fragmentation—siloed inventory monitoring, delayed restock triggers, and disjointed communication between logistics teams. 

**Supply Chain Orchestrator** bridges this gap by unifying live telemetry with autonomous AI agents. Powered by a multi-agent LangGraph supervisor, the system continuously analyzes stock levels, forecasts demand spikes, optimizes freight routing, and automatically drafts restock notifications—all surfaced through a Wayne Enterprises-grade tactical command dashboard.

---

## ✨ Key Features

- **🌐 Live Telemetry Command Dashboard**: Real-time KPI summary bar, interactive Recharts visualizations comparing stock levels against safety reorder thresholds, and en-route shipment tracking powered directly by PostgreSQL telemetry.
- **🛒 Authorized Shop Owner Portal**: Secure authentication (`admin` / `password123`) granting direct control over product catalogs, inventory quantities, reorder thresholds, and real-time CRUD operations.
- **🤖 Multi-Agent LangGraph Supervisor**: Autonomous supervisor agent that evaluates complex supply chain queries, routes sub-tasks in parallel to domain-specialized worker agents, and synthesizes structured Markdown reporting.
- **⚡ Resilient 3-Tier LLM Fallback Architecture**: Zero-downtime AI gateway that seamlessly failovers across multiple tier-1 providers if rate limits or outages occur.
- **💎 Tactical Glassmorphism UI**: Built with React 19, Tailwind CSS, and Framer Motion, featuring fluid dark/light theme switching, debounced search filters, and hardware-accelerated animations.

---

## 🏗️ System Architecture

```
                       ┌─────────────────────────────────────────┐
                       │          React 19 Command UI            │
                       └───────────────────┬─────────────────────┘
                                           │ API / WebSockets
                                           ▼
                       ┌─────────────────────────────────────────┐
                       │          FastAPI Web Server             │
                       └───────────────────┬─────────────────────┘
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             ▼                                                           ▼
┌─────────────────────────┐                                 ┌─────────────────────────┐
│   PostgreSQL Telemetry  │                                 │ LangGraph Orchestrator  │
│  (products & inventory) │                                 │  (Multi-Agent Network)  │
└─────────────────────────┘                                 └────────────┬────────────┘
                                                                         │
                                                                         ▼
                                                    ┌─────────────────────────────────────────┐
                                                    │    Unified 3-Tier LLM Gateway           │
                                                    └────────────────────┬────────────────────┘
                                                                         │
                                       ┌─────────────────────────────────┼─────────────────────────────────┐
                                       │ Failover 1                      │ Failover 2                      │
                                       ▼                                 ▼                                 ▼
                         ┌──────────────────────────┐      ┌──────────────────────────┐      ┌──────────────────────────┐
                         │   Tier 1: Groq API       │ ────►│ Tier 2: GitHub Models    │ ────►│  Tier 3: Google Gemini   │
                         │ (Llama-3.3-70B-Versatile)│      │      (GPT-4o-Mini)       │      │     (Gemini-2.0-Flash)   │
                         └──────────────────────────┘      └──────────────────────────┘      └──────────────────────────┘
```

### 🧠 Resilient 3-Tier LLM Gateway

To guarantee enterprise-grade reliability and avoid single-point API outages during automated workflows, all agents invoke LLM services through a unified fallback chain:

1. **Tier 1 (Primary): Groq API** — Executes `llama-3.3-70b-versatile` via ultra-fast LPUs using `AsyncOpenAI`.
2. **Tier 2 (Secondary): GitHub Models** — Automatically triggers if Groq encounters rate limits (`429`) or errors, routing to `gpt-4o-mini` via Azure OpenAI compatible endpoints.
3. **Tier 3 (Tertiary): Google Gemini** — Final fallback executing `gemini-2.0-flash` via the official `google-genai` SDK.

### 👥 Specialized Multi-Agent Network

1. **Supervisor Agent**: Parses incoming queries, decides execution strategy (single agent vs multi-agent workflow), delegates to worker nodes, and synthesizes final Markdown reports.
2. **Inventory Planning Agent**: Identifies stockout risks, compares available inventory against safety thresholds, and drafts reorder plans.
3. **Warehouse Ops Agent**: Monitors bin capacity, warehouse fill percentages, and storage constraints across regional hubs.
4. **Demand Forecasting Agent**: Analyzes historical sales velocity and seasonal trends to predict stock depletion windows.
5. **Route Optimization Agent**: Evaluates freight transit routes and active shipment bottlenecks to minimize delays.
6. **Fleet Management Agent**: Tracks vehicle assignments, driver availability, and maintenance schedules.
7. **Customer Notification Agent**: Formats and dispatches automated alerts for restock events and delivery updates.

---

## 🛠️ Tech Stack

| Domain | Technologies Used |
|---|---|
| **Frontend** | React 19, Vite, Tailwind CSS, Framer Motion, Recharts, React Hot Toast, Lucide Icons |
| **Backend** | Python 3.12, FastAPI, LangGraph, AsyncOpenAI, Google GenAI SDK, Pydantic v2 |
| **Database** | PostgreSQL 15+, Asyncpg connection pooling |
| **Testing** | Pytest, Pytest-Asyncio, Oxlint |

---

## 🚀 Setup & Installation

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** & **npm**
- **PostgreSQL 15+** (running locally or via cloud instance)

---

### 1. Environment Configuration

Navigate to the `backend/` directory and copy the environment template:

```bash
cd backend
cp .env.example .env
```

Edit `.env` with your database credentials and API keys:

```env
DATABASE_URL=postgresql://postgres:password123@localhost:5432/supply_chain
GROQ_API_KEY=gsk_your_groq_api_key_here
GITHUB_TOKEN=ghp_your_github_token_here
GOOGLE_API_KEY=AIzaSy_your_gemini_api_key_here
```

---

### 2. Backend Setup & Server Execution

From the root directory:

```bash
# Navigate to backend
cd backend

# Create and activate Python virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed PostgreSQL Database & Run Migrations
python seed_db.py

# Start FastAPI Dev Server
python main.py
```

The FastAPI backend will start running at `http://localhost:8000`. You can inspect interactive OpenAPI documentation at `http://localhost:8000/docs`.

---

### 3. Frontend Setup & Execution

Open a new terminal window:

```bash
# Navigate to UI directory
cd ui

# Install dependencies
npm install

# Run Vite development server
npm run dev
```

Open your browser and navigate to `http://localhost:5173`.

---

### 🧪 Running Tests

To run the automated backend test suite (22 unit & integration tests covering authentication, CRUD operations, supervisor routing, and fallback gateway logic):

```bash
cd backend
python -m pytest tests/ -v
```

---

## 🔐 Credentials for Demo

- **Shop Owner Portal Login**:
  - **Username**: `admin`
  - **Password**: `password123`
