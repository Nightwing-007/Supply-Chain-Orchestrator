"""
Supply Chain Orchestrator — LangGraph Supervisor Orchestrator

Responsibilities:
  - Acts as the central Routing Engine using LangGraph's StateGraph.
  - Dynamically routes user queries to the appropriate single AI agents:
      1. inventory_agent    (Inventory Planning Agent)
      2. warehouse_agent    (Warehouse Operations Agent)
      3. demand_agent       (Demand Forecasting Agent)
      4. route_agent        (Route Optimization Agent)
      5. fleet_agent        (Fleet Management Agent)
      6. notification_agent (Customer Notification Agent)
  - Iteratively loops: Supervisor ──► Agent ──► Supervisor ──► ... ──► FINISH ──► END.
  - Merges partial state updates into GlobalLogisticsState.
  - Generates a unified final answer when routing decision is "FINISH".

StateGraph Architecture:
  Entry Point: supervisor
  Conditional Edges out of supervisor: route to chosen agent or END
  Unconditional Edges: all 6 agent nodes ──► supervisor
"""

import json
import logging
import time
from typing import Any, Callable

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from orchestrator.state import GlobalLogisticsState
from agents.inventory_agent import inventory_planning_agent
from agents.warehouse_agent import warehouse_operations_agent
from agents.demand_agent import demand_forecasting_agent
from agents.route_agent import route_optimization_agent
from agents.fleet_agent import fleet_management_agent
from agents.notification_agent import customer_notification_agent
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# ── Valid Agent Targets ──────────────────────────────────────

VALID_AGENT_TARGETS = {
    "inventory_agent",
    "warehouse_agent",
    "demand_agent",
    "route_agent",
    "fleet_agent",
    "notification_agent",
    "FINISH",
}

AGENT_ALIAS_MAP = {
    # Alternative names to canonical target names
    "inventory": "inventory_agent",
    "inventory_planning": "inventory_agent",
    "warehouse": "warehouse_agent",
    "warehouse_operations": "warehouse_agent",
    "demand": "demand_agent",
    "demand_forecasting": "demand_agent",
    "route": "route_agent",
    "route_optimization": "route_agent",
    "fleet": "fleet_agent",
    "fleet_management": "fleet_agent",
    "notification": "notification_agent",
    "customer_notification": "notification_agent",
    "finish": "FINISH",
    "end": "FINISH",
    "complete": "FINISH",
    "done": "FINISH",
}

# ── LLM Supervisor Prompt ────────────────────────────────────

SUPERVISOR_SYSTEM_INSTRUCTION = """You are the Chief Logistics Supervisor and Routing Engine for a Smart Supply Chain Multi-Agent System.
Your job is to analyze the user's query, past execution history, and current logistics state to decide which specialised agent should run next, OR declare FINISH if all tasks are complete.

Available Agents:
- inventory_agent    : Stock monitoring, low-stock detection, reorder planning.
- warehouse_agent    : Capacity utilization (>85%), bin allocation, pick list optimization.
- demand_agent       : Rolling sales analysis, Exponential Smoothing (SES), qualitative demand adjustment.
- route_agent        : Haversine distance calculations, Nearest Neighbor TSP, traffic/weather hazard rerouting.
- fleet_agent        : Telemetry analysis (>10k km, >90d, low fuel), predictive maintenance & grounding.
- notification_agent : Customer notification drafting (Email + SMS) for dispatches, delays, or status updates.

Routing Instructions:
1. If the query requires action from an agent that has NOT yet executed, select that agent.
2. If the user query is multi-domain (e.g. check stock AND optimize delivery routes), route to one agent at a time in logical order.
3. If all requested domains have executed, OR if no further agent action is needed, select "FINISH".
4. Always respond with valid JSON matching the exact schema provided.

CRITICAL SYNTHESIS REQUIREMENT FOR FINAL ANSWER:
You are the final synthesizer. When setting next_agent to "FINISH", you MUST explicitly output the raw details, metrics, and drafted content provided by the worker agents in your "final_answer". Do NOT summarize that a task was completed (e.g., do NOT say 'a notification was drafted' or 'inventory was checked'). Instead, actually output the drafted notification text, the specific inventory counts, SKUs, distances, and precise warehouse capacities. Use rich Markdown formatting (bullet points, bold text, blockquotes) to structure this combined report clearly for the user.
"""

SUPERVISOR_PROMPT_TEMPLATE = """Evaluate the current state and decide the next routing step.

## Original User Query
"{query}"

## Current Routing Intent
Intent: {intent}

## Execution History
{history_json}

## Already Executed Steps
{executed_steps}

## Raw State Data Gathered From Worker Agents
{state_summary_json}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "routing_decision": {{
    "next_agent": "<inventory_agent|warehouse_agent|demand_agent|route_agent|fleet_agent|notification_agent|FINISH>",
    "reasoning": "<explanation for choosing this agent or finishing>",
    "final_answer": "<If next_agent is FINISH, provide the EXPLICIT detailed Markdown report incorporating raw metrics, item counts, capacities, and drafted notifications. Else null. Do NOT output vague summaries like 'notification was drafted'. Output the actual notification text, SKUs, and counts!>"
  }}
}}
"""


# ═══════════════════════════════════════════════════════════════
#  Supervisor Node Function
# ═══════════════════════════════════════════════════════════════

async def supervisor_node(
    state: GlobalLogisticsState,
    *,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Supervisor Routing Engine -- Evaluates state & query to choose next agent.

    Args:
        state: Current GlobalLogisticsState snapshot.
        llm_service: Optional injected LLMService (for testability).

    Returns:
        dict with updated target_agent, agent_responses, and final_answer.
    """
    t0 = time.perf_counter()
    query = state.get("query", "Logistics status check")
    intent = state.get("intent", "general_check")
    agent_responses = list(state.get("agent_responses", []))

    # Track which agents have already run in this traversal loop
    executed_steps = [r.get("agent") for r in agent_responses if r.get("agent")]

    # ── Rule-based Intent Fallback ──────────────────────────────
    def _intent_fallback_target() -> str:
        q_lower = query.lower()
        if "stock" in q_lower or "inventory" in q_lower or "reorder" in q_lower:
            return "inventory_agent" if "inventory_agent" not in executed_steps else "FINISH"
        elif "warehouse" in q_lower or "capacity" in q_lower or "bin" in q_lower or "pick" in q_lower:
            return "warehouse_agent" if "warehouse_agent" not in executed_steps else "FINISH"
        elif "forecast" in q_lower or "demand" in q_lower or "predict" in q_lower:
            return "demand_agent" if "demand_agent" not in executed_steps else "FINISH"
        elif "route" in q_lower or "delivery" in q_lower or "traffic" in q_lower or "distance" in q_lower:
            return "route_agent" if "route_agent" not in executed_steps else "FINISH"
        elif "fleet" in q_lower or "vehicle" in q_lower or "maintenance" in q_lower or "mileage" in q_lower:
            return "fleet_agent" if "fleet_agent" not in executed_steps else "FINISH"
        elif "notify" in q_lower or "notification" in q_lower or "email" in q_lower or "sms" in q_lower:
            return "notification_agent" if "notification_agent" not in executed_steps else "FINISH"
        return "FINISH"

    # ── Invoke LLM for Routing Decision ────────────────────────
    if llm_service is None:
        llm_service = LLMService()

    next_agent = "FINISH"
    reasoning = "Completed processing."
    final_answer = None

    try:
        state_summary = {}
        for domain in ["inventory", "warehouse", "demand", "route", "fleet", "notification"]:
            if domain in state and state[domain]:
                state_summary[domain] = state[domain]

        prompt = SUPERVISOR_PROMPT_TEMPLATE.format(
            query=query,
            intent=intent,
            history_json=json.dumps(agent_responses, indent=2) if agent_responses else "None",
            executed_steps=", ".join(executed_steps) if executed_steps else "None",
            state_summary_json=json.dumps(state_summary, indent=2, default=str) if state_summary else "None",
        )
        llm_output = await llm_service.generate(
            prompt,
            system_instruction=SUPERVISOR_SYSTEM_INSTRUCTION,
            temperature=0.1,
            max_output_tokens=2048,
        )

        dec = llm_output.get("routing_decision", {})
        raw_target = str(dec.get("next_agent", "FINISH")).strip().lower()

        # Map alias to canonical name
        canonical = AGENT_ALIAS_MAP.get(raw_target, raw_target)
        if canonical in VALID_AGENT_TARGETS:
            next_agent = canonical
        else:
            next_agent = _intent_fallback_target()

        reasoning = dec.get("reasoning", "LLM routing decision.")
        final_answer = dec.get("final_answer")

        logger.info("Supervisor routed to '%s' (Reasoning: %s)", next_agent, reasoning[:80])

    except Exception as exc:
        logger.warning("LLM supervisor routing failed (%s), using intent fallback", exc)
        next_agent = _intent_fallback_target()
        reasoning = f"Fallback routing due to LLM error: {exc}"

    # ── Prevent infinite loops: if agent already ran, force FINISH
    if next_agent != "FINISH" and next_agent in executed_steps:
        logger.info("Agent '%s' already executed; forcing FINISH", next_agent)
        next_agent = "FINISH"
        reasoning = f"Agent '{next_agent}' already ran; terminating loop."

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # ── Format Step Summary ──────────────────────────────────
    step_record = {
        "step": len(agent_responses) + 1,
        "agent": "supervisor",
        "next_agent": next_agent,
        "reasoning": reasoning,
        "duration_ms": elapsed_ms,
    }
    agent_responses.append(step_record)

    # ── Build Final Answer if Finishing ──────────────────────
    if next_agent == "FINISH" and not final_answer:
        final_answer = _build_default_final_answer(state, agent_responses)

    result_update: dict[str, Any] = {
        "target_agent": next_agent,
        "agent_responses": agent_responses,
    }
    if final_answer:
        result_update["final_answer"] = final_answer

    return result_update


# ═══════════════════════════════════════════════════════════════
#  Graph Construction & Compilation
# ═══════════════════════════════════════════════════════════════

def route_supervisor(state: GlobalLogisticsState) -> str:
    """
    Conditional edge function out of Supervisor node.
    Reads `target_agent` from state; returns canonical node name or END.
    """
    target = state.get("target_agent", "FINISH")
    if target == "FINISH" or target not in VALID_AGENT_TARGETS:
        return END
    return target


def build_logistics_graph(
    llm_service: LLMService | None = None,
) -> CompiledStateGraph:
    """
    Build and compile the LangGraph StateGraph orchestrator.

    Node Topology:
      supervisor  (Entry point & Routing Engine)
      ├── inventory_agent    ──► supervisor
      ├── warehouse_agent    ──► supervisor
      ├── demand_agent       ──► supervisor
      ├── route_agent        ──► supervisor
      ├── fleet_agent        ──► supervisor
      └── notification_agent ──► supervisor

    Returns:
        CompiledStateGraph instance ready for .ainvoke().
    """
    builder = StateGraph(GlobalLogisticsState)

    # ── Wrapped Async Nodes ──────────────────────────────────
    async def supervisor_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        return await supervisor_node(state, llm_service=llm_service)

    async def inventory_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        res = await inventory_planning_agent(state, llm_service=llm_service)
        _record_agent_response(state, "inventory_agent", res)
        return res

    async def warehouse_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        res = await warehouse_operations_agent(state, llm_service=llm_service)
        _record_agent_response(state, "warehouse_agent", res)
        return res

    async def demand_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        res = await demand_forecasting_agent(state, llm_service=llm_service)
        _record_agent_response(state, "demand_agent", res)
        return res

    async def route_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        res = await route_optimization_agent(state, llm_service=llm_service)
        _record_agent_response(state, "route_agent", res)
        return res

    async def fleet_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        res = await fleet_management_agent(state, llm_service=llm_service)
        _record_agent_response(state, "fleet_agent", res)
        return res

    async def notification_wrapper(state: GlobalLogisticsState) -> dict[str, Any]:
        res = await customer_notification_agent(state, llm_service=llm_service)
        _record_agent_response(state, "notification_agent", res)
        return res

    # ── Add Nodes ─────────────────────────────────────────────
    builder.add_node("supervisor", supervisor_wrapper)
    builder.add_node("inventory_agent", inventory_wrapper)
    builder.add_node("warehouse_agent", warehouse_wrapper)
    builder.add_node("demand_agent", demand_wrapper)
    builder.add_node("route_agent", route_wrapper)
    builder.add_node("fleet_agent", fleet_wrapper)
    builder.add_node("notification_agent", notification_wrapper)

    # ── Entry Point ───────────────────────────────────────────
    builder.set_entry_point("supervisor")

    # ── Conditional Edges out of Supervisor ───────────────────
    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "inventory_agent": "inventory_agent",
            "warehouse_agent": "warehouse_agent",
            "demand_agent": "demand_agent",
            "route_agent": "route_agent",
            "fleet_agent": "fleet_agent",
            "notification_agent": "notification_agent",
            END: END,
        },
    )

    # ── Unconditional Edges back to Supervisor ────────────────
    builder.add_edge("inventory_agent", "supervisor")
    builder.add_edge("warehouse_agent", "supervisor")
    builder.add_edge("demand_agent", "supervisor")
    builder.add_edge("route_agent", "supervisor")
    builder.add_edge("fleet_agent", "supervisor")
    builder.add_edge("notification_agent", "supervisor")

    return builder.compile()


# ═══════════════════════════════════════════════════════════════
#  High-Level Execution API
# ═══════════════════════════════════════════════════════════════

async def run_logistics_workflow(
    query: str,
    *,
    intent: str = "general_check",
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Execute the multi-agent Supply Chain Orchestrator graph end-to-end.

    Args:
        query: Human query (e.g. "Check inventory for low stock and schedule delivery routes").
        intent: Optional classification string.
        llm_service: Injected LLM client instance.

    Returns:
        Final GlobalLogisticsState dictionary.
    """
    initial_state: GlobalLogisticsState = {
        "query": query,
        "intent": intent,
        "agent_responses": [],
    }

    compiled_graph = build_logistics_graph(llm_service=llm_service)
    final_state = await compiled_graph.ainvoke(initial_state)
    return dict(final_state)


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _record_agent_response(state: GlobalLogisticsState, agent_name: str, result: dict) -> None:
    """Record agent execution metadata in the state's agent_responses list."""
    history = list(state.get("agent_responses", []))
    history.append({
        "step": len(history) + 1,
        "agent": agent_name,
        "status": "completed" if "error" not in result else "failed",
    })
    result["agent_responses"] = history


def _build_default_final_answer(state: GlobalLogisticsState, history: list[dict]) -> str:
    """Synthesise an explicit, detailed Markdown final report of all agent executions."""
    executed = [h.get("agent") for h in history if h.get("agent") and h.get("agent") != "supervisor"]
    if not executed:
        return f"Logistics query processed. Summary: No agent action was required for '{state.get('query')}'."

    lines = [
        f"## 📋 Supply Chain Orchestrator Executive Report",
        f"**Original Query:** *{state.get('query')}*\n",
    ]

    if "inventory" in state and state["inventory"]:
        inv = state["inventory"]
        lines.append("### 📦 Inventory Planning Report")
        if inv.get("reorder_recommendations"):
            for item in inv.get("reorder_recommendations", []):
                lines.append(f"- **{item.get('product_name', 'Item')}** (`{item.get('sku')}`): Current Stock: **{item.get('current_stock', 0)}** | Reorder Point: {item.get('reorder_point', 0)} | Restock Qty: **{item.get('recommended_restock_qty', 0)}** (Priority: *{item.get('priority', 'medium')}*)")
        if inv.get("summary"):
            lines.append(f"\n{inv['summary']}")
        lines.append("")

    if "warehouse" in state and state["warehouse"]:
        wh = state["warehouse"]
        lines.append("### 🏭 Warehouse Operations Report")
        lines.append(f"- **Capacity Utilization:** **{wh.get('utilization_pct', 89.0)}%**")
        if wh.get("bottleneck_warning"):
            lines.append(f"> ⚠️ **Warning:** {wh['bottleneck_warning']}")
        if wh.get("summary"):
            lines.append(f"\n{wh['summary']}")
        lines.append("")

    if "demand" in state and state["demand"]:
        dem = state["demand"]
        lines.append("### 📈 Demand Forecasting Report")
        if dem.get("forecast_results"):
            for fc in dem.get("forecast_results", []):
                lines.append(f"- **{fc.get('product_name', 'Product')}** (`{fc.get('sku')}`): Baseline: {fc.get('baseline_forecast')} units | Projected Demand: **{fc.get('adjusted_forecast', fc.get('baseline_forecast'))} units**")
        if dem.get("summary"):
            lines.append(f"\n{dem['summary']}")
        lines.append("")

    if "route" in state and state["route"]:
        rt = state["route"]
        lines.append("### 🚚 Route Optimization Report")
        lines.append(f"- **Total Distance:** **{rt.get('total_distance_km', 0)} km** | **Estimated Duration:** **{rt.get('estimated_minutes', 0)} mins**")
        if rt.get("summary"):
            lines.append(f"\n{rt['summary']}")
        lines.append("")

    if "fleet" in state and state["fleet"]:
        fl = state["fleet"]
        lines.append("### 🚛 Fleet Management Report")
        if fl.get("maintenance_alerts"):
            for alert in fl.get("maintenance_alerts", []):
                lines.append(f"- Vehicle **{alert.get('registration')}**: {alert.get('issue')} ➔ Action: **{alert.get('action')}**")
        if fl.get("summary"):
            lines.append(f"\n{fl['summary']}")
        lines.append("")

    if "notification" in state and state["notification"]:
        notif = state["notification"]
        lines.append("### ✉️ Customer Notification Report")
        if notif.get("drafted_email"):
            email = notif["drafted_email"]
            lines.append(f"**Email Subject:** `{email.get('subject')}`")
            lines.append(f"> {email.get('body')}")
        if notif.get("drafted_sms"):
            sms = notif["drafted_sms"]
            lines.append(f"**SMS ({sms.get('recipient')}):** `{sms.get('text')}`")
        if notif.get("summary"):
            lines.append(f"\n{notif['summary']}")
        lines.append("")

    return "\n".join(lines)
