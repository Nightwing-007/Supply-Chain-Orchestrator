"""
Supply Chain Orchestrator — Application Entrypoint & REST API

Provides:
  • FastAPI server with REST endpoints for multi-agent workflow invocation
  • Standalone Single-Agent REST endpoints (Single Agent Mode: POST /api/agent/{agent_name})
  • LangGraph Supervisor Orchestrator REST endpoint (Multi Agent Mode: POST /api/workflow)
  • CORS middleware for frontend/dashboard integration
  • Lifespan context manager managing the PostgreSQL asyncpg connection pool
  • GET /health -- Service liveness probe
  • CLI mode (--cli) for terminal smoke testing
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from config.settings import get_settings
from db.connection import get_pool, close_pool
from orchestrator.supervisor import run_logistics_workflow

# ── Agent Functions Import ────────────────────────────────────

from agents.inventory_agent import inventory_planning_agent
from agents.warehouse_agent import warehouse_operations_agent
from agents.demand_agent import demand_forecasting_agent
from agents.route_agent import route_optimization_agent
from agents.fleet_agent import fleet_management_agent
from agents.notification_agent import customer_notification_agent

# ── Logging Setup ────────────────────────────────────────────

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s │ %(name)-28s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sco.main")


# ── Standalone Agent Resolver (Single Agent Mode) ───────────────────

def get_single_agent_fn(agent_name: str) -> Optional[Callable]:
    """
    Resolve canonical or alias agent name to the corresponding async agent function.
    Evaluated dynamically to allow mock patching during unit testing.
    """
    key = agent_name.strip().lower()
    agent_map = {
        "inventory": inventory_planning_agent,
        "inventory_agent": inventory_planning_agent,
        "inventory_planning": inventory_planning_agent,

        "warehouse": warehouse_operations_agent,
        "warehouse_agent": warehouse_operations_agent,
        "warehouse_operations": warehouse_operations_agent,

        "demand": demand_forecasting_agent,
        "demand_agent": demand_forecasting_agent,
        "demand_forecasting": demand_forecasting_agent,

        "route": route_optimization_agent,
        "route_agent": route_optimization_agent,
        "route_optimization": route_optimization_agent,

        "fleet": fleet_management_agent,
        "fleet_agent": fleet_management_agent,
        "fleet_management": fleet_management_agent,

        "notification": customer_notification_agent,
        "notification_agent": customer_notification_agent,
        "customer_notification": customer_notification_agent,
    }
    return agent_map.get(key)


# ── Pydantic Request & Response Schemas ──────────────────────

class WorkflowRequest(BaseModel):
    """Request payload for starting a multi-agent logistics workflow (Multi Agent Mode)."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language user query",
        json_schema_extra={"example": "Check inventory for low stock and schedule delivery routes"},
    )
    intent: Optional[str] = Field(
        "general_check",
        description="Optional intent classification string",
        json_schema_extra={"example": "inventory_and_route"},
    )


class SingleAgentRequest(BaseModel):
    """Request payload for executing a standalone single AI agent (Single Agent Mode)."""

    query: Optional[str] = Field(
        "Execute agent task",
        description="User query or instruction prompt for the single agent",
        json_schema_extra={"example": "Check inventory stock levels"},
    )
    state: Optional[dict[str, Any]] = Field(
        None,
        description="Optional initial state input dictionary",
    )


class WorkflowResponse(BaseModel):
    """Response payload returned by orchestrator or single agent execution."""

    status: str = Field(..., description="Execution status ('success' or 'failed')")
    state: dict[str, Any] = Field(..., description="Final GlobalLogisticsState snapshot")
    final_answer: Optional[str] = Field(None, description="Human-readable executive summary")
    execution_time_ms: float = Field(..., description="Total execution duration in milliseconds")


class LoginRequest(BaseModel):
    """Payload for shop owner login."""
    username: str
    password: str


class ProductCreateRequest(BaseModel):
    """Payload for creating a new product."""
    sku: str
    name: str
    category: Optional[str] = "General"
    unit_price: Optional[float] = 0.0
    quantity_on_hand: int = 0
    reorder_point: int = 10
    reorder_qty: int = 50


class ProductUpdateRequest(BaseModel):
    """Payload for updating product details or stock counts."""
    name: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    quantity_on_hand: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_qty: Optional[int] = None


class SaleItemSchema(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, default=1)


class SaleCreateRequest(BaseModel):
    customer_name: str
    customer_email: Optional[str] = "customer@example.com"
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = "Main Street Hub"
    delivery_city: Optional[str] = "Mumbai"
    items: list[SaleItemSchema]


# ── FastAPI Lifespan Manager ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    logger.info("🚀 Supply Chain Orchestrator starting up…")
    await get_pool()
    yield
    logger.info("🛑 Shutting down…")
    await close_pool()


# ── App Initialization ───────────────────────────────────────

app = FastAPI(
    title="Supply Chain Orchestrator",
    description="Smart Logistics Multi-Agent System powered by LangGraph, PostgreSQL, and Gemini",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Endpoints ────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Liveness probe to check API service health."""
    return {"status": "ok", "service": "supply-chain-orchestrator"}



@app.get("/api/dashboard", tags=["System"])
async def get_dashboard_data():
    """Fetch live metrics from PostgreSQL for the frontend dashboard."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Active Shipments
            shipments_records = await conn.fetch("""
                SELECT s.tracking_number, s.status, o.delivery_city as destination, COALESCE(s.origin, 'Mumbai Warehouse') as origin
                FROM shipments s
                JOIN orders o ON s.order_id = o.id
                WHERE s.status != 'delivered'
                ORDER BY s.id ASC
                LIMIT 10
            """)
            shipments = [dict(r) for r in shipments_records]

            # 2. Performance Data (Mocked from DB for now as example)
            performance = [
                {'name': 'Mon', 'value': 40},
                {'name': 'Tue', 'value': 60},
                {'name': 'Wed', 'value': 45},
                {'name': 'Thu', 'value': 80},
                {'name': 'Fri', 'value': 50},
                {'name': 'Sat', 'value': 90},
                {'name': 'Sun', 'value': 75},
            ]

            # 3. Flow Data (Mocked from DB for now)
            flow = [
                {'name': 'Node A', 'out': 400, 'in': 240},
                {'name': 'Node B', 'out': 300, 'in': 139},
                {'name': 'Node C', 'out': 200, 'in': 980},
                {'name': 'Node D', 'out': 278, 'in': 390},
            ]

            # 4. Risk Intel
            risks_records = await conn.fetch("""
                SELECT p.name, i.quantity_on_hand, i.reorder_point
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                WHERE i.quantity_on_hand <= i.reorder_point
                LIMIT 2
            """)
            
            risks = []
            for r in risks_records:
                risks.append({
                    "level": "Critical" if r['quantity_on_hand'] == 0 else "Warning",
                    "text": f"Low stock alert for {r['name']}: Only {r['quantity_on_hand']} left (reorder at {r['reorder_point']}).",
                })
            
            if not risks:
                risks = [{
                    "level": "Warning",
                    "text": "System running normally, but monitoring global events."
                }]

            # 5. KPI Summary Metrics
            critical_count = await conn.fetchval("""
                SELECT COUNT(*) FROM inventory WHERE quantity_on_hand <= reorder_point
            """) or 0
            total_items = await conn.fetchval("""
                SELECT COUNT(*) FROM products
            """) or 10
            avg_warehouse_fill = await conn.fetchval("""
                SELECT ROUND(AVG(used_capacity::numeric / NULLIF(total_capacity, 0)::numeric * 100), 1)
                FROM warehouses WHERE is_active = TRUE
            """) or 89.0

            # 6. Detailed Inventory Progress Metrics
            inventory_records = await conn.fetch("""
                SELECT 
                    p.sku, 
                    p.name as product_name, 
                    i.quantity_on_hand, 
                    i.reorder_point, 
                    i.reorder_qty,
                    w.code as warehouse_code
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                JOIN warehouses w ON i.warehouse_id = w.id
                ORDER BY (i.quantity_on_hand::float / NULLIF(i.reorder_point, 0)) ASC
                LIMIT 8
            """)
            inventory_items = [dict(r) for r in inventory_records]

            return {
                "shipments": shipments,
                "performance": performance,
                "flow": flow,
                "risks": risks,
                "kpis": {
                    "critical_alerts": critical_count,
                    "total_items": total_items,
                    "active_shipments": len(shipments),
                    "avg_fill_pct": float(avg_warehouse_fill),
                },
                "inventory_items": inventory_items,
            }
    except Exception as exc:
        logger.exception("Error fetching dashboard data: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {str(exc)}",
        )


@app.post(
    "/api/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    tags=["Workflow Orchestration (Multi Agent Mode)"],
    summary="Execute Multi-Agent LangGraph Workflow",
    description="Exposes the LangGraph Supervisor Orchestrator. Evaluates the user query, routes to appropriate single agents, and returns the unified state.",
)
async def execute_workflow(req: WorkflowRequest) -> WorkflowResponse:
    """Execute multi-agent workflow using LangGraph supervisor."""
    t0 = time.perf_counter()
    logger.info("Received workflow request: '%s' (Intent: %s)", req.query, req.intent)

    try:
        final_state = await run_logistics_workflow(
            query=req.query,
            intent=req.intent or "general_check",
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        if "error" in final_state and not final_state.get("target_agent"):
            logger.error("Workflow returned error state: %s", final_state["error"])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=final_state["error"],
            )

        logger.info("Workflow completed in %.2f ms", elapsed_ms)
        return WorkflowResponse(
            status="success",
            state=final_state,
            final_answer=final_state.get("final_answer"),
            execution_time_ms=elapsed_ms,
        )

    except HTTPException:
        raise
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.exception("Internal error executing workflow: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orchestrator internal execution error: {str(exc)}",
        )


@app.post(
    "/api/agent/{agent_name}",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    tags=["Single Agents (Single Agent Mode)"],
    summary="Execute Standalone Single AI Agent",
    description="Invokes a specific single AI agent directly without triggering the LangGraph supervisor.",
)
async def execute_single_agent(
    agent_name: str,
    req: SingleAgentRequest,
) -> WorkflowResponse:
    """Execute a single AI agent directly (Single Agent Mode)."""
    t0 = time.perf_counter()
    canonical_key = agent_name.strip().lower()
    agent_fn = get_single_agent_fn(canonical_key)

    if agent_fn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found. Valid options: inventory, warehouse, demand, route, fleet, notification.",
        )

    input_state = dict(req.state) if req.state else {}
    if req.query:
        input_state["query"] = req.query

    logger.info("Executing standalone single agent: '%s'", canonical_key)

    try:
        updated_state = await agent_fn(input_state)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        merged_state = {**input_state, **updated_state}
        merged_state["target_agent"] = "FINISH"
        merged_state["agent_responses"] = [
            {"step": 1, "agent": canonical_key, "status": "completed", "duration_ms": elapsed_ms}
        ]

        summary = f"Standalone Single Agent '{canonical_key}' executed successfully."

        return WorkflowResponse(
            status="success",
            state=merged_state,
            final_answer=merged_state.get("final_answer") or summary,
            execution_time_ms=elapsed_ms,
        )

    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.exception("Error executing single agent '%s': %s", canonical_key, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Single Agent '{canonical_key}' execution error: {str(exc)}",
        )


# ── Shop Owner Authentication & Product Management ─────────

@app.post("/api/login", tags=["Authentication"])
async def login(req: LoginRequest):
    """Authenticate shop owner with default credentials (admin / password123)."""
    if req.username == "admin" and req.password == "password123":
        return {
            "status": "success",
            "token": "token_admin_session_99",
            "username": "admin",
            "message": "Authentication successful",
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
    )


@app.get("/api/products", tags=["Product Management"])
async def get_products():
    """Retrieve all products along with their current inventory levels."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT 
                    p.id,
                    p.sku,
                    p.name,
                    p.category,
                    p.unit_price,
                    COALESCE(i.quantity_on_hand, 0) as quantity_on_hand,
                    COALESCE(i.reorder_point, 10) as reorder_point,
                    COALESCE(i.reorder_qty, 50) as reorder_qty,
                    w.code as warehouse_code
                FROM products p
                LEFT JOIN inventory i ON i.product_id = p.id
                LEFT JOIN warehouses w ON i.warehouse_id = w.id
                ORDER BY p.id ASC
            """)
            return [dict(r) for r in records]
    except Exception as exc:
        logger.exception("Error fetching products: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error fetching products: {str(exc)}",
        )


@app.post("/api/products", tags=["Product Management"], status_code=status.HTTP_201_CREATED)
async def create_product(req: ProductCreateRequest):
    """Add a new product to the catalog and initialize its inventory row."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Insert product
                p_row = await conn.fetchrow("""
                    INSERT INTO products (sku, name, category, unit_price)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, sku, name, category, unit_price
                """, req.sku, req.name, req.category, req.unit_price)

                product_id = p_row["id"]

                # 2. Get default warehouse
                wh_id = await conn.fetchval("SELECT id FROM warehouses ORDER BY id ASC LIMIT 1") or 1

                # 3. Insert inventory record
                await conn.execute("""
                    INSERT INTO inventory (warehouse_id, product_id, quantity_on_hand, reorder_point, reorder_qty)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (warehouse_id, product_id)
                    DO UPDATE SET quantity_on_hand = EXCLUDED.quantity_on_hand, reorder_point = EXCLUDED.reorder_point
                """, wh_id, product_id, req.quantity_on_hand, req.reorder_point, req.reorder_qty)

                res = dict(p_row)
                res["quantity_on_hand"] = req.quantity_on_hand
                res["reorder_point"] = req.reorder_point
                res["reorder_qty"] = req.reorder_qty
                return res
    except Exception as exc:
        logger.exception("Error creating product: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating product: {str(exc)}",
        )


@app.put("/api/products/{item_id}", tags=["Product Management"])
async def update_product(item_id: int, req: ProductUpdateRequest):
    """Update existing product details and/or inventory stock counts."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check product exists
                p_exists = await conn.fetchval("SELECT id FROM products WHERE id = $1", item_id)
                if not p_exists:
                    raise HTTPException(status_code=404, detail=f"Product with ID {item_id} not found")

                if req.name is not None or req.category is not None or req.unit_price is not None:
                    await conn.execute("""
                        UPDATE products
                        SET name = COALESCE($1, name),
                            category = COALESCE($2, category),
                            unit_price = COALESCE($3, unit_price),
                            updated_at = NOW()
                        WHERE id = $4
                    """, req.name, req.category, req.unit_price, item_id)

                if req.quantity_on_hand is not None or req.reorder_point is not None or req.reorder_qty is not None:
                    await conn.execute("""
                        UPDATE inventory
                        SET quantity_on_hand = COALESCE($1, quantity_on_hand),
                            reorder_point = COALESCE($2, reorder_point),
                            reorder_qty = COALESCE($3, reorder_qty),
                            updated_at = NOW()
                        WHERE product_id = $4
                    """, req.quantity_on_hand, req.reorder_point, req.reorder_qty, item_id)

                updated_row = await conn.fetchrow("""
                    SELECT 
                        p.id,
                        p.sku,
                        p.name,
                        p.category,
                        p.unit_price,
                        COALESCE(i.quantity_on_hand, 0) as quantity_on_hand,
                        COALESCE(i.reorder_point, 10) as reorder_point,
                        COALESCE(i.reorder_qty, 50) as reorder_qty
                    FROM products p
                    LEFT JOIN inventory i ON i.product_id = p.id
                    WHERE p.id = $1
                """, item_id)
                return dict(updated_row)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error updating product %d: %s", item_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating product: {str(exc)}",
        )


@app.delete("/api/products/{item_id}", tags=["Product Management"])
async def delete_product(item_id: int):
    """Delete a product and its associated inventory records from PostgreSQL."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Check product exists
                p_exists = await conn.fetchval("SELECT id FROM products WHERE id = $1", item_id)
                if not p_exists:
                    raise HTTPException(status_code=404, detail=f"Product with ID {item_id} not found")

                # Delete inventory dependent records first
                await conn.execute("DELETE FROM inventory WHERE product_id = $1", item_id)

                # Delete product
                await conn.execute("DELETE FROM products WHERE id = $1", item_id)

                return {"status": "success", "message": f"Product {item_id} deleted successfully", "id": item_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error deleting product %d: %s", item_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting product: {str(exc)}",
        )


@app.get("/api/sales", tags=["Sales History"])
async def get_sales_history():
    """Retrieve shop sales history including orders, order items, customer details, and summary metrics."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            orders = await conn.fetch("""
                SELECT 
                    o.id,
                    o.order_number,
                    o.customer_name,
                    o.customer_email,
                    o.customer_phone,
                    o.delivery_address,
                    o.delivery_city,
                    o.status,
                    o.priority,
                    o.total_amount,
                    o.placed_at,
                    o.created_at,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'product_id', oi.product_id,
                                'product_name', p.name,
                                'product_sku', p.sku,
                                'quantity', oi.quantity,
                                'unit_price', oi.unit_price
                            )
                        ) FILTER (WHERE oi.product_id IS NOT NULL), '[]'::json
                    ) as items
                FROM orders o
                LEFT JOIN order_items oi ON o.id = oi.order_id
                LEFT JOIN products p ON oi.product_id = p.id
                GROUP BY o.id
                ORDER BY o.created_at DESC
            """)

            order_list = []
            for o in orders:
                d = dict(o)
                if isinstance(d.get("items"), str):
                    try:
                        d["items"] = json.loads(d["items"])
                    except Exception:
                        d["items"] = []
                order_list.append(d)

            total_orders = len(order_list)
            total_revenue = sum(float(o["total_amount"] or 0) for o in order_list)
            delivered_orders = sum(1 for o in order_list if o["status"] == "delivered")
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0.0

            return {
                "summary": {
                    "total_orders": total_orders,
                    "total_revenue": round(total_revenue, 2),
                    "delivered_orders": delivered_orders,
                    "avg_order_value": round(avg_order_value, 2),
                },
                "orders": order_list,
            }
    except Exception as exc:
        logger.exception("Error fetching sales history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error fetching sales history: {str(exc)}",
        )


@app.post("/api/sales", tags=["Sales History"], status_code=status.HTTP_201_CREATED)
async def create_sale(req: SaleCreateRequest):
    """Process a new sale, deduct sold product quantities from inventory, and insert order into PostgreSQL."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                total_amount = 0.0
                item_details = []

                for item in req.items:
                    p = await conn.fetchrow("SELECT id, sku, name, unit_price FROM products WHERE id = $1", item.product_id)
                    if not p:
                        raise HTTPException(status_code=404, detail=f"Product with ID {item.product_id} not found")

                    stock = await conn.fetchval("SELECT quantity_on_hand FROM inventory WHERE product_id = $1", item.product_id) or 0
                    if stock < item.quantity:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Insufficient stock for '{p['name']}'. Available: {stock}, Requested: {item.quantity}",
                        )

                    unit_price = float(p["unit_price"] or 0)
                    total_amount += unit_price * item.quantity
                    item_details.append({
                        "product_id": p["id"],
                        "sku": p["sku"],
                        "name": p["name"],
                        "quantity": item.quantity,
                        "unit_price": unit_price
                    })

                order_count = await conn.fetchval("SELECT COUNT(*) FROM orders") + 1
                order_number = f"ORD-2026-{order_count:05d}"

                order_id = await conn.fetchval("""
                    INSERT INTO orders (order_number, customer_name, customer_email, customer_phone, delivery_address, delivery_city, status, total_amount)
                    VALUES ($1, $2, $3, $4, $5, $6, 'confirmed'::sco.order_status, $7)
                    RETURNING id
                """, order_number, req.customer_name, req.customer_email, req.customer_phone, req.delivery_address, req.delivery_city, total_amount)

                for detail in item_details:
                    await conn.execute("""
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                        VALUES ($1, $2, $3, $4)
                    """, order_id, detail["product_id"], detail["quantity"], detail["unit_price"])

                    await conn.execute("""
                        UPDATE inventory
                        SET quantity_on_hand = GREATEST(0, quantity_on_hand - $1),
                            updated_at = NOW()
                        WHERE product_id = $2
                    """, detail["quantity"], detail["product_id"])

                return {
                    "status": "success",
                    "order_id": order_id,
                    "order_number": order_number,
                    "total_amount": round(total_amount, 2),
                    "items_sold": len(item_details),
                    "message": f"Sale completed! Order #{order_number} created and inventory updated."
                }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing sale transaction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing sale transaction: {str(exc)}",
        )


# ── CLI Mode ─────────────────────────────────────────────────

async def cli_mode():
    """Run a quick smoke test from the command line."""
    logger.info("Running in CLI mode…")
    pool = await get_pool()

    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
        logger.info("Connected to PostgreSQL: %s", version[:60])

    await close_pool()
    logger.info("CLI smoke test passed ✅")


# ── Main Entrypoint ──────────────────────────────────────────

if __name__ == "__main__":
    if "--cli" in sys.argv:
        asyncio.run(cli_mode())
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.environment.lower() == "development",
        )
