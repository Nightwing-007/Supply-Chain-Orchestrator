"""
Supply Chain Orchestrator — Streamlit User Interface & Demo Dashboard

Features:
  - Sleek dark-mode glassmorphism interface ("Supply Chain Orchestrator - CampusOS")
  - Interactive chat interface powered by FastAPI backend & LangGraph supervisor
  - One-click sample query triggers for judges & recruiters
  - Real-time agent state inspector sidebar displaying domain sub-states
    (Inventory, Warehouse, Demand, Route, Fleet, Notification)
  - Live JSON state inspector for deep-dive debugging
"""

import json
import time
import requests
import streamlit as st

# ── Page Configuration ────────────────────────────────────────

st.set_page_config(
    page_title="Supply Chain Orchestrator - CampusOS",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for Dark Theme & Glassmorphism Aesthetics ──────

CUSTOM_CSS = """
<style>
    /* Dark Theme Core Settings */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Header Container */
    .header-container {
        background: linear-gradient(135deg, #161b22 0%, #21262d 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #58a6ff 0%, #bc8cff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .header-subtitle {
        color: #8b949e;
        font-size: 1.05rem;
        margin-top: 0;
    }

    /* Metric Cards */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #58a6ff;
    }
    .metric-label {
        color: #8b949e;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Chat Messages */
    .stChatMessage {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }

    /* Agent Badges */
    .agent-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .badge-inventory { background-color: #1f6feb; color: #ffffff; }
    .badge-warehouse { background-color: #d29922; color: #000000; }
    .badge-demand    { background-color: #238636; color: #ffffff; }
    .badge-route     { background-color: #a371f7; color: #ffffff; }
    .badge-fleet     { background-color: #f85149; color: #ffffff; }
    .badge-notif     { background-color: #388bfd; color: #ffffff; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── API Backend Configuration ─────────────────────────────────

BACKEND_URL = "http://localhost:8000/api/workflow"
HEALTH_URL = "http://localhost:8000/health"


# ── Session State Initialization ──────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! I am the **Supply Chain Orchestrator Supervisor**.\n\n"
                "I route your logistics requests across 6 specialized AI agents:\n"
                "- 📦 **Inventory Planning** (Stock levels & reordering)\n"
                "- 🏬 **Warehouse Operations** (Capacity & bin allocation)\n"
                "- 📈 **Demand Forecasting** (Exponential Smoothing & trends)\n"
                "- 🛣️ **Route Optimization** (Nearest Neighbor TSP & traffic)\n"
                "- 🚚 **Fleet Management** (Telemetry & maintenance)\n"
                "- 💬 **Customer Notification** (Empathetic Email & SMS)\n\n"
                "Try typing a query below or select a sample query!"
            ),
        }
    ]

if "current_state" not in st.session_state:
    st.session_state.current_state = {}


# ── Header Component ──────────────────────────────────────────

st.markdown(
    """
    <div class="header-container">
        <div class="header-title">Supply Chain Orchestrator — CampusOS 🚛</div>
        <div class="header-subtitle">
            Smart Logistics Multi-Agent System powered by LangGraph, PostgreSQL & Google Gemini
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Sidebar: Real-Time Agent Memory & State Inspector ──────────

with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/container-truck.png", width=64)
    st.title("🧠 Agent State Inspector")
    st.caption("Live Shared GlobalLogisticsState Monitor (For Judges)")

    # Backend Connection Status Check
    try:
        health_resp = requests.get(HEALTH_URL, timeout=2)
        if health_resp.status_code == 200:
            st.success("🟢 API Server Connected (Port 8000)")
        else:
            st.error("🔴 API Server Unhealthy")
    except Exception:
        st.warning("⚠️ Local API Server Offline. Please run `python main.py`.")

    st.markdown("---")

    state = st.session_state.current_state

    # Top-Level Summary Metrics
    if state:
        st.subheader("📊 Fleet & Ops Snapshot")
        col1, col2 = st.columns(2)

        inv_alerts = len(state.get("inventory", {}).get("low_stock_alerts", []))
        wh_util = state.get("warehouse", {}).get("utilization_pct", 0.0)
        route_km = state.get("route", {}).get("total_distance_km", 0.0)
        fleet_util = state.get("fleet", {}).get("_fleet_utilization_pct", 0.0)

        with col1:
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{inv_alerts}</div><div class="metric-label">Low Stock Items</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{route_km} km</div><div class="metric-label">Route Dist</div></div>',
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{wh_util}%</div><div class="metric-label">WH Utilisation</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{fleet_util}%</div><div class="metric-label">Fleet Util</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

    # ── Domain Sub-State Expanders ────────────────────────────

    st.subheader("🔍 Domain Sub-States")

    # 1. Inventory State
    with st.expander("📦 Inventory Planning State", expanded=False):
        inv_data = state.get("inventory", {})
        if inv_data:
            st.write(f"**Low Stock Alerts:** {len(inv_data.get('low_stock_alerts', []))}")
            st.write(f"**Reorder Plans:** {len(inv_data.get('reorder_recommendations', []))}")
            st.json(inv_data)
        else:
            st.info("No inventory state updates yet.")

    # 2. Warehouse State
    with st.expander("🏬 Warehouse Operations State", expanded=False):
        wh_data = state.get("warehouse", {})
        if wh_data:
            st.write(f"**Utilisation:** {wh_data.get('utilization_pct', 0)}%")
            st.write(f"**Pending Picks:** {len(wh_data.get('pending_picks', []))}")
            st.json(wh_data)
        else:
            st.info("No warehouse state updates yet.")

    # 3. Demand Forecasting State
    with st.expander("📈 Demand Forecasting State", expanded=False):
        demand_data = state.get("demand", {})
        if demand_data:
            st.write(f"**Forecast Period:** {demand_data.get('forecast_period_days', 7)} days")
            st.write(f"**Forecasted Products:** {len(demand_data.get('forecast_results', []))}")
            st.json(demand_data)
        else:
            st.info("No demand state updates yet.")

    # 4. Route Optimization State
    with st.expander("🛣️ Route Optimization State", expanded=False):
        route_data = state.get("route", {})
        if route_data:
            st.write(f"**Distance:** {route_data.get('total_distance_km', 0)} km")
            st.write(f"**Stops:** {len(route_data.get('stops', []))}")
            st.json(route_data)
        else:
            st.info("No route state updates yet.")

    # 5. Fleet Management State
    with st.expander("🚚 Fleet Management State", expanded=False):
        fleet_data = state.get("fleet", {})
        if fleet_data:
            st.write(f"**Vehicle ID:** {fleet_data.get('vehicle_id', 'N/A')}")
            st.write(f"**Maintenance Alerts:** {len(fleet_data.get('maintenance_alerts', []))}")
            st.json(fleet_data)
        else:
            st.info("No fleet state updates yet.")

    # 6. Customer Notification State
    with st.expander("💬 Customer Notification State", expanded=False):
        notif_data = state.get("notification", {})
        if notif_data:
            st.write(f"**Customer:** {notif_data.get('customer_name', 'N/A')}")
            st.write(f"**Event Type:** {notif_data.get('event_type', 'N/A')}")
            st.json(notif_data)
        else:
            st.info("No notification state updates yet.")

    # 7. Complete Raw JSON State
    with st.expander("⚙️ Complete GlobalLogisticsState JSON", expanded=False):
        if state:
            st.json(state)
        else:
            st.info("State graph uninitialized.")


# ── Sample Quick Prompt Buttons for Live Demos ────────────────

st.markdown("##### ⚡ Quick Demo Queries (Click to Run)")

demo_cols = st.columns(4)

selected_prompt = None

with demo_cols[0]:
    if st.button("📦 Stock Check", use_container_width=True):
        selected_prompt = "Check stock levels across all warehouses and generate reorder recommendations."

with demo_cols[1]:
    if st.button("🏬 Warehouse Ops", use_container_width=True):
        selected_prompt = "Inspect warehouse utilization and build an optimized pick list."

with demo_cols[2]:
    if st.button("🛣️ Route Dispatch", use_container_width=True):
        selected_prompt = "Optimize delivery routes considering current traffic hazards."

with demo_cols[3]:
    if st.button("🌐 Full Multi-Agent", use_container_width=True):
        selected_prompt = "Check stock levels, inspect warehouse capacity, optimize delivery routes, and check fleet health."


# ── Chat Messages Display ─────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── Chat Input & Agent Processing ─────────────────────────────

user_input = st.chat_input("Ask Supply Chain Orchestrator a query (e.g., 'Check fleet telemetry and notify customer')...")

# Override with selected quick prompt button if clicked
prompt_to_send = selected_prompt or user_input

if prompt_to_send:
    # 1. Add user query to chat history
    st.session_state.messages.append({"role": "user", "content": prompt_to_send})
    with st.chat_message("user"):
        st.markdown(prompt_to_send)

    # 2. Call FastAPI backend and display assistant spinner
    with st.chat_message("assistant"):
        with st.spinner("🤖 LangGraph Supervisor routing to AI agents..."):
            try:
                t0 = time.perf_counter()
                response = requests.post(
                    BACKEND_URL,
                    json={"query": prompt_to_send, "intent": "general_check"},
                    timeout=90,
                )
                elapsed_s = round(time.perf_counter() - t0, 2)

                if response.status_code == 200:
                    res_data = response.json()
                    final_state = res_data.get("state", {})
                    st.session_state.current_state = final_state

                    final_answer = res_data.get("final_answer") or final_state.get(
                        "final_answer", "Workflow completed successfully."
                    )

                    # Build execution trail badges
                    history = final_state.get("agent_responses", [])
                    executed_agents = [
                        h.get("agent")
                        for h in history
                        if h.get("agent") and h.get("agent") != "supervisor"
                    ]

                    badge_html = "<div><b>Executed Agents:</b> "
                    if executed_agents:
                        for ag in executed_agents:
                            badge_cls = f"badge-{ag.split('_')[0]}"
                            badge_html += f'<span class="agent-badge {badge_cls}">{ag}</span>'
                    else:
                        badge_html += '<span class="agent-badge badge-inventory">Supervisor Only</span>'
                    badge_html += f" <i>(Execution time: {elapsed_s}s)</i></div><br>"

                    full_response = f"{badge_html}\n{final_answer}"
                    st.markdown(full_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.rerun()

                else:
                    err_msg = f"❌ Error {response.status_code}: {response.text}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})

            except requests.exceptions.ConnectionError:
                err_msg = "❌ Connection Error: Could not connect to API server at http://localhost:8000. Please start it using `python main.py`."
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            except Exception as exc:
                err_msg = f"❌ Unexpected Error: {str(exc)}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
