"""
Supply Chain Orchestrator — Global Logistics State

Defines the `GlobalLogisticsState` TypedDict used as the shared state
graph in LangGraph (Phase 2). During Phase 1, agents receive/return
subsets of this state as plain dicts.
"""

from typing import Any, Optional, TypedDict


class InventoryState(TypedDict, total=False):
    """Snapshot of inventory data relevant to an agent invocation."""
    warehouse_id: int
    product_id: int
    quantity_on_hand: int
    quantity_reserved: int
    reorder_point: int
    reorder_qty: int
    low_stock_alerts: list[dict[str, Any]]
    reorder_recommendations: list[dict[str, Any]]


class WarehouseState(TypedDict, total=False):
    """Snapshot of warehouse operational data."""
    warehouse_id: int
    warehouse_code: str
    total_capacity: int
    used_capacity: int
    utilization_pct: float
    pending_picks: list[dict[str, Any]]
    optimization_suggestions: list[str]


class FleetState(TypedDict, total=False):
    """Snapshot of fleet & vehicle data."""
    vehicle_id: int
    registration: str
    status: str
    current_lat: float
    current_lon: float
    fuel_level_pct: float
    available_vehicles: list[dict[str, Any]]
    maintenance_alerts: list[dict[str, Any]]


class DemandState(TypedDict, total=False):
    """Demand forecasting context."""
    product_id: int
    warehouse_id: Optional[int]
    forecast_period_days: int
    predicted_qty: int
    confidence: float
    historical_data: list[dict[str, Any]]
    forecast_results: list[dict[str, Any]]


class RouteState(TypedDict, total=False):
    """Route optimization context."""
    route_id: int
    vehicle_id: int
    origin_warehouse_id: int
    stops: list[dict[str, Any]]
    total_distance_km: float
    total_duration_min: int
    optimized_order: list[int]


class NotificationState(TypedDict, total=False):
    """Customer notification context."""
    order_id: int
    customer_name: str
    customer_email: str
    customer_phone: str
    channel: str
    event_type: str  # e.g. "order_shipped", "delivery_eta_updated"
    message_body: str
    notification_id: int


class GlobalLogisticsState(TypedDict, total=False):
    """
    Top-level shared state for the LangGraph supervisor.

    Each agent reads/writes only its relevant sub-state.
    The supervisor merges partial updates after each agent invocation.
    """
    # ── User query ──
    query: str
    intent: str                        # resolved by supervisor
    target_agent: str                  # which agent should handle

    # ── Domain sub-states ──
    inventory: InventoryState
    warehouse: WarehouseState
    fleet: FleetState
    demand: DemandState
    route: RouteState
    notification: NotificationState

    # ── Orchestration metadata ──
    agent_responses: list[dict[str, Any]]
    error: Optional[str]
    final_answer: str
