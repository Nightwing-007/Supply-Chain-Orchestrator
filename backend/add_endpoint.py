import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\backend\main.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

endpoint_code = """
@app.get("/api/dashboard", tags=["System"])
async def get_dashboard_data():
    \"\"\"Fetch live metrics from PostgreSQL for the frontend dashboard.\"\"\"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Active Shipments
            shipments_records = await conn.fetch(\"\"\"
                SELECT s.tracking_number, s.status, o.delivery_city as destination, 'Origin Warehouse' as origin
                FROM shipments s
                JOIN orders o ON s.order_id = o.id
                WHERE s.status != 'delivered'
                ORDER BY s.created_at DESC
                LIMIT 5
            \"\"\")
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
            risks_records = await conn.fetch(\"\"\"
                SELECT p.name, i.quantity_on_hand, i.reorder_point
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                WHERE i.quantity_on_hand <= i.reorder_point
                LIMIT 2
            \"\"\")
            
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

            return {
                "shipments": shipments,
                "performance": performance,
                "flow": flow,
                "risks": risks
            }
    except Exception as exc:
        logger.exception("Error fetching dashboard data: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {str(exc)}",
        )
"""

if "@app.get(\"/api/dashboard\"" not in content:
    # insert before @app.post("/api/workflow"
    content = content.replace(
        "@app.post(\n    \"/api/workflow\",", 
        endpoint_code + "\n\n@app.post(\n    \"/api/workflow\","
    )
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Endpoint added.")
else:
    print("Endpoint already exists.")
