"""
Supply Chain Orchestrator — Streamlit User Interface & Demo Dashboard

Features:
  - Mode Selection: "Day 1: Single Agent Mode" vs "Day 2: Multi-Agent Supervisor"
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

API_BASE_URL = "http://localhost:8000"
HEALTH_URL = f"{API_BASE_URL}/health"


# ── Session State Initialization ──────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! Welcome to the **Supply Chain Orchestrator**.\n\n"
                "**Choose your mode in the sidebar:**\n"
                "- **Day 1: Single Agent Mode** — Query a specific single AI agent directly.\n"
                "- **Day 2: Multi-Agent Supervisor** — Execute the full LangGraph orchestrator graph.\n\n"
                "Try typing a query below or click a sample prompt!"
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


# ── Sidebar: Mode Selection & Real-Time State Inspector ───────

with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/container-truck.png", width=64)
    st.title("🎛️ Control & Memory Inspector")

    # API Connection Check
    try:
        health_resp = requests.get(HEALTH_URL, timeout=2)
        if health_resp.status_code == 200:
            st.success("🟢 API Server Connected (Port 8000)")
        else:
            st.error("🔴 API Server Unhealthy")
    except Exception:
        st.warning("⚠️ Local API Server Offline. Run `python main.py`.")

    st.markdown("---")

    # ── Mode Selection (Day 1 vs Day 2) ────────────────────────
    st.subheader("⚙️ Orchestration Mode")
    app_mode = st.radio(
        "Select Execution Paradigm:",
        ["Day 2: Multi-Agent Supervisor", "Day 1: Single Agent Mode"],
        index=0,
        help="Switch between Day 1 single agent execution and Day 2 LangGraph supervisor graph.",
    )

    selected_agent_key = "inventory"
    if app_mode == "Day 1: Single Agent Mode":
        st.info("💡 Direct Single-Agent Mode Active (Bypasses LangGraph Supervisor)")
        selected_agent_label = st.selectbox(
            "Target Single AI Agent:",
            [
                "📦 Inventory Planning Agent",
                "🏬 Warehouse Operations Agent",
                "📈 Demand Forecasting Agent",
                "🛣️ Route Optimization Agent",
                "🚚 Fleet Management Agent",
                "💬 Customer Notification Agent",
            ],
            index=0,
        )
        agent_key_map = {
            "📦 Inventory Planning Agent": "inventory",
            "🏬 Warehouse Operations Agent": "warehouse",
            "📈 Demand Forecasting Agent": "demand",
            "🛣️ Route Optimization Agent": "route",
            "🚚 Fleet Management Agent": "fleet",
            "💬 Customer Notification Agent": "notification",
        }
        selected_agent_key = agent_key_map[selected_agent_label]
    else:
        st.success("🌐 Multi-Agent LangGraph Supervisor Active")

    st.markdown("---")

    # ── Real-Time State Inspector ─────────────────────────────
    st.subheader("📊 Live State Inspector (For Judges)")

    state = st.session_state.current_state

    if state:
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

    with st.expander("📦 Inventory Planning State", expanded=False):
        inv_data = state.get("inventory", {})
        if inv_data:
            st.write(f"**Low Stock Alerts:** {len(inv_data.get('low_stock_alerts', []))}")
            st.json(inv_data)
        else:
            st.info("No inventory state updates.")

    with st.expander("🏬 Warehouse Operations State", expanded=False):
        wh_data = state.get("warehouse", {})
        if wh_data:
            st.write(f"**Utilisation:** {wh_data.get('utilization_pct', 0)}%")
            st.json(wh_data)
        else:
            st.info("No warehouse state updates.")

    with st.expander("📈 Demand Forecasting State", expanded=False):
        demand_data = state.get("demand", {})
        if demand_data:
            st.write(f"**Forecast Window:** {demand_data.get('forecast_period_days', 7)} days")
            st.json(demand_data)
        else:
            st.info("No demand state updates.")

    with st.expander("🛣️ Route Optimization State", expanded=False):
        route_data = state.get("route", {})
        if route_data:
            st.write(f"**Distance:** {route_data.get('total_distance_km', 0)} km")
            st.json(route_data)
        else:
            st.info("No route state updates.")

    with st.expander("🚚 Fleet Management State", expanded=False):
        fleet_data = state.get("fleet", {})
        if fleet_data:
            st.write(f"**Alerts Count:** {len(fleet_data.get('maintenance_alerts', []))}")
            st.json(fleet_data)
        else:
            st.info("No fleet state updates.")

    with st.expander("💬 Customer Notification State", expanded=False):
        notif_data = state.get("notification", {})
        if notif_data:
            st.write(f"**Customer:** {notif_data.get('customer_name', 'N/A')}")
            st.json(notif_data)
        else:
            st.info("No notification state updates.")

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
        st.markdown(msg["content"], unsafe_allow_html=True)


# ── Chat Input & Processing ──────────────────────────────────

user_input = st.chat_input(
    f"Type your prompt ({'Single Agent: ' + selected_agent_key if app_mode == 'Day 1: Single Agent Mode' else 'Multi-Agent Supervisor'})..."
)

prompt_to_send = selected_prompt or user_input

if prompt_to_send:
    st.session_state.messages.append({"role": "user", "content": prompt_to_send})
    with st.chat_message("user"):
        st.markdown(prompt_to_send)

    with st.chat_message("assistant"):
        spinner_msg = (
            f"🤖 Executing Single Agent: `{selected_agent_key}`..."
            if app_mode == "Day 1: Single Agent Mode"
            else "🤖 LangGraph Supervisor routing across multi-agent graph..."
        )

        with st.spinner(spinner_msg):
            try:
                t0 = time.perf_counter()

                # Determine target URL & payload based on active mode
                if app_mode == "Day 1: Single Agent Mode":
                    target_url = f"{API_BASE_URL}/api/agent/{selected_agent_key}"
                    payload = {
                        "query": prompt_to_send,
                        "state": st.session_state.current_state,
                    }
                else:
                    target_url = f"{API_BASE_URL}/api/workflow"
                    payload = {
                        "query": prompt_to_send,
                        "intent": "general_check",
                    }

                response = requests.post(target_url, json=payload, timeout=90)
                elapsed_s = round(time.perf_counter() - t0, 2)

                if response.status_code == 200:
                    res_data = response.json()
                    final_state = res_data.get("state", {})
                    st.session_state.current_state = final_state

                    final_answer = res_data.get("final_answer") or final_state.get(
                        "final_answer", "Agent executed successfully."
                    )

                    # Build execution trail badges
                    history = final_state.get("agent_responses", [])
                    executed_agents = [
                        h.get("agent")
                        for h in history
                        if h.get("agent") and h.get("agent") != "supervisor"
                    ]

                    badge_html = "<div><b>Executed Agent(s):</b> "
                    if app_mode == "Day 1: Single Agent Mode":
                        badge_html += f'<span class="agent-badge badge-{selected_agent_key}">{selected_agent_key} (Day 1 Mode)</span>'
                    elif executed_agents:
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
                err_msg = "❌ Connection Error: Could not connect to API server at http://localhost:8000. Ensure `python main.py` is running."
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            except Exception as exc:
                err_msg = f"❌ Unexpected Error: {str(exc)}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
