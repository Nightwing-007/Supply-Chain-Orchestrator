"""
Supply Chain Orchestrator — Premium Streamlit Dashboard

Features:
  - Manual Light/Dark Mode toggle with custom brand color palette
  - Brand Primary Accent: #54c750 (Vibrant Green)
  - Day 1 Single Agent Mode vs Day 2 Multi-Agent Supervisor Mode selector
  - Interactive chat interface with premium styled message bubbles
  - One-click demo query buttons for live hackathon presentations
  - Real-time Agent State Inspector with metric cards and JSON expanders
"""

import time
import requests
import streamlit as st

# ── Page Configuration ────────────────────────────────────────

st.set_page_config(
    page_title="Supply Chain Orchestrator — CampusOS",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand Color Palette ───────────────────────────────────────

PRIMARY   = "#54c750"   # Vibrant Green — buttons, accents, highlights
LIGHT_BG  = "#f0f2f0"   # Off-white / Light Gray — light mode backgrounds
DARK_BG   = "#3e3f3e"   # Deep Gray — dark mode backgrounds
SECONDARY = "#5b5b5b"   # Medium Gray — borders, secondary text
DARK_SURFACE   = "#2e2f2e"  # Slightly darker than DARK_BG for cards
LIGHT_SURFACE  = "#ffffff"  # White card surface for light mode
DARK_TEXT  = "#3e3f3e"
LIGHT_TEXT = "#f0f2f0"

# ── Session State Initialization ──────────────────────────────

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Welcome to the **Supply Chain Orchestrator**.\n\n"
                "**Choose your mode in the sidebar:**\n"
                "- **Day 1: Single Agent** — Query one specialized AI agent directly.\n"
                "- **Day 2: Multi-Agent Supervisor** — Run the full LangGraph orchestrator.\n\n"
                "Type a query below or click a demo prompt to get started!"
            ),
        }
    ]

if "current_state" not in st.session_state:
    st.session_state.current_state = {}


# ── Dynamic CSS Injection ─────────────────────────────────────

def inject_theme_css(theme: str):
    """Inject raw CSS that adapts to the active theme."""

    is_dark = theme == "dark"

    bg_color        = DARK_BG       if is_dark else LIGHT_BG
    surface_color   = DARK_SURFACE  if is_dark else LIGHT_SURFACE
    text_color      = LIGHT_TEXT    if is_dark else DARK_TEXT
    muted_text      = "#a0a0a0"     if is_dark else "#6e6e6e"
    border_color    = SECONDARY     if is_dark else "#c8c8c8"
    sidebar_bg      = DARK_SURFACE  if is_dark else "#e4e6e4"
    input_bg        = "#353635"     if is_dark else "#ffffff"
    chat_user_bg    = PRIMARY
    chat_user_text  = "#ffffff"
    chat_asst_bg    = surface_color
    chat_asst_text  = text_color
    hover_glow      = "rgba(84, 199, 80, 0.25)"
    header_grad_a   = "#2a2b2a" if is_dark else "#dfe1df"
    header_grad_b   = "#3a3b3a" if is_dark else "#f0f2f0"

    css = f"""
    <style>
        /* ── Import Google Font ─────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* ── Global Foundation ──────────────────────────────── */
        *, *::before, *::after {{ font-family: 'Inter', sans-serif !important; }}
        .stApp {{
            background-color: {bg_color} !important;
            color: {text_color} !important;
        }}
        .stApp > header {{ background-color: transparent !important; }}

        /* ── Sidebar ────────────────────────────────────────── */
        section[data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
            border-right: 1px solid {border_color} !important;
        }}
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] .stRadio label,
        section[data-testid="stSidebar"] span {{
            color: {text_color} !important;
        }}

        /* ── Branded Header Container ───────────────────────── */
        .brand-header {{
            background: linear-gradient(135deg, {header_grad_a} 0%, {header_grad_b} 100%);
            border: 1px solid {border_color};
            border-left: 4px solid {PRIMARY};
            border-radius: 12px;
            padding: 28px 36px;
            margin-bottom: 28px;
            box-shadow: 0 4px 20px rgba(0,0,0,{"0.35" if is_dark else "0.08"});
        }}
        .brand-header h1 {{
            font-size: 2.1rem;
            font-weight: 800;
            color: {PRIMARY} !important;
            margin: 0 0 6px 0;
            letter-spacing: -0.5px;
        }}
        .brand-header p {{
            color: {muted_text};
            font-size: 1rem;
            margin: 0;
        }}

        /* ── Metric Cards ───────────────────────────────────── */
        .metric-card {{
            background: {surface_color};
            border: 1px solid {border_color};
            border-radius: 10px;
            padding: 18px 14px;
            text-align: center;
            transition: all 0.25s ease;
        }}
        .metric-card:hover {{
            border-color: {PRIMARY};
            box-shadow: 0 0 16px {hover_glow};
            transform: translateY(-2px);
        }}
        .metric-value {{
            font-size: 1.75rem;
            font-weight: 700;
            color: {PRIMARY} !important;
        }}
        .metric-label {{
            color: {muted_text};
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-top: 4px;
        }}

        /* ── Streamlit Primary Buttons → Brand Green ─────────── */
        .stButton > button,
        button[kind="primary"] {{
            background-color: {PRIMARY} !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }}
        .stButton > button:hover,
        button[kind="primary"]:hover {{
            background-color: #47b043 !important;
            box-shadow: 0 0 14px {hover_glow} !important;
            transform: translateY(-1px) !important;
        }}

        /* ── Chat Message Bubbles ───────────────────────────── */
        [data-testid="stChatMessage"] {{
            border-radius: 14px !important;
            padding: 14px 18px !important;
            margin-bottom: 12px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,{"0.25" if is_dark else "0.06"}) !important;
            border: 1px solid {border_color} !important;
            background-color: {chat_asst_bg} !important;
            color: {chat_asst_text} !important;
        }}

        /* ── Streamlit Input Boxes ──────────────────────────── */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        [data-testid="stChatInputTextArea"] {{
            background-color: {input_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border_color} !important;
            border-radius: 10px !important;
        }}
        [data-testid="stChatInputTextArea"]:focus {{
            border-color: {PRIMARY} !important;
            box-shadow: 0 0 0 2px {hover_glow} !important;
        }}

        /* ── Expanders ──────────────────────────────────────── */
        .streamlit-expanderHeader {{
            background-color: {surface_color} !important;
            color: {text_color} !important;
            border-radius: 8px !important;
        }}
        details[data-testid="stExpander"] {{
            border: 1px solid {border_color} !important;
            border-radius: 10px !important;
            background-color: {surface_color} !important;
        }}
        details[data-testid="stExpander"] summary {{
            color: {text_color} !important;
        }}

        /* ── Select Boxes & Radios ──────────────────────────── */
        .stSelectbox > div > div,
        .stRadio > div {{
            color: {text_color} !important;
        }}
        .stSelectbox [data-baseweb="select"] > div {{
            background-color: {input_bg} !important;
            border-color: {border_color} !important;
            color: {text_color} !important;
        }}

        /* ── Agent Badges ───────────────────────────────────── */
        .agent-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 14px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-right: 6px;
            margin-bottom: 6px;
            letter-spacing: 0.3px;
        }}
        .badge-inventory   {{ background-color: {PRIMARY}; color: #fff; }}
        .badge-warehouse   {{ background-color: #e5a100; color: #1a1a1a; }}
        .badge-demand      {{ background-color: #3498db; color: #fff; }}
        .badge-route       {{ background-color: #9b59b6; color: #fff; }}
        .badge-fleet       {{ background-color: #e74c3c; color: #fff; }}
        .badge-notification {{ background-color: #1abc9c; color: #fff; }}
        .badge-notif       {{ background-color: #1abc9c; color: #fff; }}

        /* ── Theme Toggle Button ────────────────────────────── */
        .theme-toggle-label {{
            font-size: 0.82rem;
            color: {muted_text};
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 4px;
        }}

        /* ── Mode Indicator Pill ────────────────────────────── */
        .mode-pill {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}
        .mode-pill-day1 {{
            background: rgba(84, 199, 80, 0.15);
            color: {PRIMARY};
            border: 1px solid {PRIMARY};
        }}
        .mode-pill-day2 {{
            background: rgba(52, 152, 219, 0.15);
            color: #3498db;
            border: 1px solid #3498db;
        }}

        /* ── Scrollbar ──────────────────────────────────────── */
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: {bg_color}; }}
        ::-webkit-scrollbar-thumb {{ background: {SECONDARY}; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: {PRIMARY}; }}

        /* ── Divider Lines ──────────────────────────────────── */
        hr {{ border-color: {border_color} !important; opacity: 0.5; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ── Apply Theme CSS ───────────────────────────────────────────

inject_theme_css(st.session_state.theme)


# ── API Backend Configuration ─────────────────────────────────

API_BASE_URL = "http://localhost:8000"
HEALTH_URL = f"{API_BASE_URL}/health"


# ── Branded Header ────────────────────────────────────────────

theme_icon = "🌙" if st.session_state.theme == "dark" else "☀️"
st.markdown(
    f"""
    <div class="brand-header">
        <h1>🚛 Supply Chain Orchestrator</h1>
        <p>Smart Logistics Multi-Agent System &mdash; LangGraph &bull; PostgreSQL &bull; Google Gemini &bull; CampusOS</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Sidebar ───────────────────────────────────────────────────

with st.sidebar:

    # ── Theme Toggle ──────────────────────────────────────────
    st.markdown('<p class="theme-toggle-label">Appearance</p>', unsafe_allow_html=True)
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("☀️ Light", use_container_width=True,
                      key="light_btn", disabled=(st.session_state.theme == "light")):
            st.session_state.theme = "light"
            st.rerun()
    with col_t2:
        if st.button("🌙 Dark", use_container_width=True,
                      key="dark_btn", disabled=(st.session_state.theme == "dark")):
            st.session_state.theme = "dark"
            st.rerun()

    st.markdown("---")

    # ── API Health ────────────────────────────────────────────
    try:
        health_resp = requests.get(HEALTH_URL, timeout=2)
        if health_resp.status_code == 200:
            st.success("🟢 API Connected — Port 8000")
        else:
            st.error("🔴 API Unhealthy")
    except Exception:
        st.warning("⚠️ API Offline — Run `python main.py`")

    st.markdown("---")

    # ── Orchestration Mode ────────────────────────────────────
    st.subheader("⚙️ Orchestration Mode")
    app_mode = st.radio(
        "Select Mode:",
        ["Day 2: Multi-Agent Supervisor", "Day 1: Single Agent Mode"],
        index=0,
        help="Day 1 bypasses the supervisor and queries a single agent. Day 2 uses the full LangGraph graph.",
    )

    selected_agent_key = "inventory"
    if app_mode == "Day 1: Single Agent Mode":
        st.markdown('<span class="mode-pill mode-pill-day1">🔬 Day 1 — Single Agent</span>',
                    unsafe_allow_html=True)
        selected_agent_label = st.selectbox(
            "Target Agent:",
            [
                "📦 Inventory Planning",
                "🏬 Warehouse Operations",
                "📈 Demand Forecasting",
                "🛣️ Route Optimization",
                "🚚 Fleet Management",
                "💬 Customer Notification",
            ],
            index=0,
        )
        agent_key_map = {
            "📦 Inventory Planning": "inventory",
            "🏬 Warehouse Operations": "warehouse",
            "📈 Demand Forecasting": "demand",
            "🛣️ Route Optimization": "route",
            "🚚 Fleet Management": "fleet",
            "💬 Customer Notification": "notification",
        }
        selected_agent_key = agent_key_map[selected_agent_label]
    else:
        st.markdown('<span class="mode-pill mode-pill-day2">🌐 Day 2 — Multi-Agent Supervisor</span>',
                    unsafe_allow_html=True)

    st.markdown("---")

    # ── Live State Inspector ──────────────────────────────────
    st.subheader("📊 Live Metrics")
    state = st.session_state.current_state

    if state:
        col1, col2 = st.columns(2)

        inv_alerts = len(state.get("inventory", {}).get("low_stock_alerts", []))
        wh_util = state.get("warehouse", {}).get("utilization_pct", 0.0)
        route_km = state.get("route", {}).get("total_distance_km", 0.0)
        fleet_util = state.get("fleet", {}).get("_fleet_utilization_pct", 0.0)

        with col1:
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{inv_alerts}</div>'
                f'<div class="metric-label">Low Stock</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{route_km} km</div>'
                f'<div class="metric-label">Route Dist</div></div>',
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{wh_util}%</div>'
                f'<div class="metric-label">WH Util</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="metric-card"><div class="metric-value">{fleet_util}%</div>'
                f'<div class="metric-label">Fleet Util</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

    # ── Domain Sub-State Expanders ────────────────────────────
    st.subheader("🔍 Agent Sub-States")

    with st.expander("📦 Inventory", expanded=False):
        inv_data = state.get("inventory", {})
        if inv_data:
            st.write(f"**Low Stock Alerts:** {len(inv_data.get('low_stock_alerts', []))}")
            st.json(inv_data)
        else:
            st.info("No data yet.")

    with st.expander("🏬 Warehouse", expanded=False):
        wh_data = state.get("warehouse", {})
        if wh_data:
            st.write(f"**Utilisation:** {wh_data.get('utilization_pct', 0)}%")
            st.json(wh_data)
        else:
            st.info("No data yet.")

    with st.expander("📈 Demand", expanded=False):
        demand_data = state.get("demand", {})
        if demand_data:
            st.write(f"**Forecast Window:** {demand_data.get('forecast_period_days', 7)} days")
            st.json(demand_data)
        else:
            st.info("No data yet.")

    with st.expander("🛣️ Route", expanded=False):
        route_data = state.get("route", {})
        if route_data:
            st.write(f"**Distance:** {route_data.get('total_distance_km', 0)} km")
            st.json(route_data)
        else:
            st.info("No data yet.")

    with st.expander("🚚 Fleet", expanded=False):
        fleet_data = state.get("fleet", {})
        if fleet_data:
            st.write(f"**Alerts:** {len(fleet_data.get('maintenance_alerts', []))}")
            st.json(fleet_data)
        else:
            st.info("No data yet.")

    with st.expander("💬 Notifications", expanded=False):
        notif_data = state.get("notification", {})
        if notif_data:
            st.write(f"**Customer:** {notif_data.get('customer_name', 'N/A')}")
            st.json(notif_data)
        else:
            st.info("No data yet.")

    with st.expander("⚙️ Full GlobalLogisticsState", expanded=False):
        if state:
            st.json(state)
        else:
            st.info("State graph not initialized.")


# ── Quick Demo Prompts ────────────────────────────────────────

st.markdown("##### ⚡ Quick Demo Queries")

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
    if st.button("🌐 Full Supervisor", use_container_width=True):
        selected_prompt = "Check stock levels, inspect warehouse capacity, optimize delivery routes, and check fleet health."


# ── Chat History Display ──────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)


# ── Chat Input & API Dispatch ─────────────────────────────────

user_input = st.chat_input(
    f"{'🔬 ' + selected_agent_key.title() + ' Agent' if app_mode == 'Day 1: Single Agent Mode' else '🌐 Multi-Agent Supervisor'} — Type your query..."
)

prompt_to_send = selected_prompt or user_input

if prompt_to_send:
    st.session_state.messages.append({"role": "user", "content": prompt_to_send})
    with st.chat_message("user"):
        st.markdown(prompt_to_send)

    with st.chat_message("assistant"):
        spinner_label = (
            f"🔬 Running Single Agent: {selected_agent_key}..."
            if app_mode == "Day 1: Single Agent Mode"
            else "🌐 LangGraph Supervisor routing multi-agent graph..."
        )

        with st.spinner(spinner_label):
            try:
                t0 = time.perf_counter()

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
                        badge_html += (
                            f'<span class="agent-badge badge-{selected_agent_key}">'
                            f'{selected_agent_key} (Day 1)</span>'
                        )
                    elif executed_agents:
                        for ag in executed_agents:
                            badge_cls = f"badge-{ag.split('_')[0]}"
                            badge_html += f'<span class="agent-badge {badge_cls}">{ag}</span>'
                    else:
                        badge_html += '<span class="agent-badge badge-inventory">Supervisor</span>'
                    badge_html += f" <i>({elapsed_s}s)</i></div><br>"

                    full_response = f"{badge_html}\n{final_answer}"
                    st.markdown(full_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.rerun()

                else:
                    err_msg = f"❌ Error {response.status_code}: {response.text}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})

            except requests.exceptions.ConnectionError:
                err_msg = (
                    "❌ Connection Error: Could not reach API at http://localhost:8000. "
                    "Ensure `python main.py` is running in a separate terminal."
                )
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            except Exception as exc:
                err_msg = f"❌ Unexpected Error: {str(exc)}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
