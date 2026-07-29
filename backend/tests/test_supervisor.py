"""
Tests for Phase 2: LangGraph Supervisor Orchestrator

Covers:
  1. Test Case 1: Immediate FINISH -- Mock LLM returns {"next_agent": "FINISH"} and graph exits after 1 step.
  2. Test Case 2: Multi-step sequence -- Mock LLM returns fleet_agent -> notification_agent -> FINISH and state reflects sequence.
  3. Loop prevention -- If an agent attempts to execute twice, supervisor forces FINISH.
  4. Alias mapping -- Verifies "fleet", "inventory", "route" map to canonical agent names.
  5. Intent fallback -- If LLM raises error, fallback correctly routes based on query keywords.
  6. Graph compilation -- Validates StateGraph node and edge wiring.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.graph import END

from orchestrator.state import GlobalLogisticsState
from orchestrator.supervisor import (
    supervisor_node,
    route_supervisor,
    build_logistics_graph,
    run_logistics_workflow,
    VALID_AGENT_TARGETS,
    AGENT_ALIAS_MAP,
)


# =============================================================
#  Fixtures & Mocks
# =============================================================

SAMPLE_STATE: GlobalLogisticsState = {
    "query": "Check fleet status and notify customer",
    "intent": "fleet_check",
    "agent_responses": [],
}


# =============================================================
#  Test Case 1: Immediate FINISH (Single Step Exit)
# =============================================================

@pytest.mark.asyncio
async def test_immediate_finish_exits_graph():
    """When the LLM supervisor returns next_agent="FINISH", the graph should exit immediately after 1 step."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value={
        "routing_decision": {
            "next_agent": "FINISH",
            "reasoning": "No operations required for simple status query.",
            "final_answer": "Everything is operating normally.",
        }
    })

    # Execute workflow with mocked LLM
    final_state = await run_logistics_workflow(
        query="System status check",
        intent="general_check",
        llm_service=mock_llm,
    )

    # 1. Target agent should be FINISH
    assert final_state["target_agent"] == "FINISH"

    # 2. Final answer should be populated
    assert "final_answer" in final_state
    assert final_state["final_answer"] == "Everything is operating normally."

    # 3. Agent responses history should record 1 supervisor step
    history = final_state["agent_responses"]
    assert len(history) == 1
    assert history[0]["agent"] == "supervisor"
    assert history[0]["next_agent"] == "FINISH"


# =============================================================
#  Test Case 2: Multi-Step Routing Sequence
# =============================================================

@pytest.mark.asyncio
@patch("orchestrator.supervisor.fleet_management_agent", new_callable=AsyncMock)
@patch("orchestrator.supervisor.customer_notification_agent", new_callable=AsyncMock)
async def test_multi_step_sequence_fleet_to_notification(mock_notif_agent, mock_fleet_agent):
    """
    Mock LLM sequence:
      Step 1: fleet_agent
      Step 2: notification_agent
      Step 3: FINISH

    Verify state reflects execution of fleet -> notification -> finish.
    """
    # Mock agent node outputs
    mock_fleet_agent.return_value = {
        "fleet": {
            "vehicle_id": 1,
            "registration": "MH-04-AB-1234",
            "status": "available",
            "fuel_level_pct": 95.0,
            "available_vehicles": [],
            "maintenance_alerts": [],
        }
    }
    mock_notif_agent.return_value = {
        "notification": {
            "order_id": 1,
            "customer_name": "Arjun Mehta",
            "customer_email": "arjun@example.com",
            "customer_phone": "+91-98765-43210",
            "channel": "email",
            "event_type": "fleet_update",
            "message_body": "Your delivery vehicle is en route.",
            "notification_id": 0,
        }
    }

    # Mock LLM calls in order: fleet_agent -> notification_agent -> FINISH
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=[
        {
            "routing_decision": {
                "next_agent": "fleet_agent",
                "reasoning": "Query requires checking vehicle maintenance status.",
            }
        },
        {
            "routing_decision": {
                "next_agent": "notification_agent",
                "reasoning": "Fleet check complete; now notify customer.",
            }
        },
        {
            "routing_decision": {
                "next_agent": "FINISH",
                "reasoning": "All tasks completed.",
                "final_answer": "Fleet checked and customer notified.",
            }
        },
    ])

    final_state = await run_logistics_workflow(
        query="Check fleet and notify Arjun",
        intent="fleet_and_notify",
        llm_service=mock_llm,
    )

    # Verify both agent nodes executed
    mock_fleet_agent.assert_called_once()
    mock_notif_agent.assert_called_once()

    # Verify domain sub-states populated
    assert "fleet" in final_state
    assert final_state["fleet"]["registration"] == "MH-04-AB-1234"

    assert "notification" in final_state
    assert final_state["notification"]["customer_name"] == "Arjun Mehta"

    # Verify execution history contains expected sequence
    history = final_state["agent_responses"]
    agents_in_order = [h["agent"] for h in history]

    # Expected order: supervisor -> fleet_agent -> supervisor -> notification_agent -> supervisor
    assert "supervisor" in agents_in_order
    assert "fleet_agent" in agents_in_order
    assert "notification_agent" in agents_in_order

    assert final_state["target_agent"] == "FINISH"
    assert final_state["final_answer"] == "Fleet checked and customer notified."


# =============================================================
#  Test 3: Infinite Loop Prevention
# =============================================================

@pytest.mark.asyncio
@patch("orchestrator.supervisor.inventory_planning_agent", new_callable=AsyncMock)
async def test_loop_prevention_forces_finish(mock_inventory_agent):
    """If the LLM attempts to select an agent that already executed, supervisor forces FINISH."""
    mock_inventory_agent.return_value = {
        "inventory": {"low_stock_alerts": [], "reorder_recommendations": []}
    }

    # LLM repeatedly tries to call inventory_agent
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value={
        "routing_decision": {
            "next_agent": "inventory_agent",
            "reasoning": "Checking inventory again.",
        }
    })

    final_state = await run_logistics_workflow(
        query="Check stock levels",
        intent="inventory_check",
        llm_service=mock_llm,
    )

    # Inventory agent should run only ONCE, not infinitely
    assert mock_inventory_agent.call_count == 1
    assert final_state["target_agent"] == "FINISH"


# =============================================================
#  Test 4: Alias Mapping
# =============================================================

class TestAliasMapping:
    """Verify alias mapping maps short names to canonical agent names."""

    def test_alias_map_values_are_valid(self):
        for alias, canonical in AGENT_ALIAS_MAP.items():
            assert canonical in VALID_AGENT_TARGETS, f"Alias '{alias}' maps to invalid target '{canonical}'"

    def test_known_aliases(self):
        assert AGENT_ALIAS_MAP["inventory"] == "inventory_agent"
        assert AGENT_ALIAS_MAP["warehouse"] == "warehouse_agent"
        assert AGENT_ALIAS_MAP["demand"] == "demand_agent"
        assert AGENT_ALIAS_MAP["route"] == "route_agent"
        assert AGENT_ALIAS_MAP["fleet"] == "fleet_agent"
        assert AGENT_ALIAS_MAP["notification"] == "notification_agent"
        assert AGENT_ALIAS_MAP["done"] == "FINISH"


# =============================================================
#  Test 5: Intent Fallback on LLM Failure
# =============================================================

@pytest.mark.asyncio
async def test_intent_fallback_on_llm_failure():
    """If the LLM fails, supervisor uses query keywords to determine next agent."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM rate limit"))

    state: GlobalLogisticsState = {
        "query": "Please optimize our delivery routes for traffic",
        "intent": "route_check",
        "agent_responses": [],
    }

    res = await supervisor_node(state, llm_service=mock_llm)

    assert res["target_agent"] == "route_agent"
    assert "Fallback routing" in res["agent_responses"][0]["reasoning"]


# =============================================================
#  Test 6: Graph Structure Validation
# =============================================================

class TestGraphStructure:
    """Validate StateGraph building and compilation."""

    def test_route_supervisor_helper(self):
        assert route_supervisor({"target_agent": "FINISH"}) == END
        assert route_supervisor({"target_agent": "invalid_node"}) == END
        assert route_supervisor({"target_agent": "inventory_agent"}) == "inventory_agent"
        assert route_supervisor({"target_agent": "fleet_agent"}) == "fleet_agent"

    def test_graph_builds_without_error(self):
        graph = build_logistics_graph()
        assert graph is not None
