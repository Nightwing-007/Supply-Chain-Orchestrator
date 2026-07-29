import os

# 1. Update inventory_agent.py
file_path_inv = r'f:\agentverse\Supply-Chain-Orchestrator\backend\agents\inventory_agent.py'
with open(file_path_inv, 'r', encoding='utf-8') as f:
    inv_content = f.read()

# Fix healthy stock return
old_healthy = """        if not low_stock_items:
            result = {
                "inventory": {
                    "low_stock_alerts": [],
                    "reorder_recommendations": [],
                },
            }
            return result"""
new_healthy = """        if not low_stock_items:
            result = {
                "inventory": {
                    "low_stock_alerts": [],
                    "reorder_recommendations": [],
                    "summary": "Inventory levels are healthy. No items require restocking.",
                },
            }
            return result"""
inv_content = inv_content.replace(old_healthy, new_healthy)

# Fix reorder result return
old_reorder = """        # ── Step 5: Assemble state update ────────────────────
        result = {
            "inventory": {
                "low_stock_alerts": alerts,
                "reorder_recommendations": reorder_result.get("reorder_plan", []),
            },
        }"""
new_reorder = """        # ── Step 5: Assemble state update ────────────────────
        result = {
            "inventory": {
                "low_stock_alerts": alerts,
                "reorder_recommendations": reorder_result.get("reorder_plan", []),
                "summary": reorder_result.get("summary") if reorder_result else "Inventory scan completed.",
            },
        }"""
inv_content = inv_content.replace(old_reorder, new_reorder)

# Fix error return
old_error = """        # Return error in state so the supervisor can handle it
        return {
            "inventory": {
                "low_stock_alerts": [],
                "reorder_recommendations": [],
            },
            "error": f"Inventory Planning Agent error: {error_msg}",
        }"""
new_error = """        # Return error in state so the supervisor can handle it
        return {
            "inventory": {
                "low_stock_alerts": [],
                "reorder_recommendations": [],
                "summary": f"Inventory Planning Agent error: {error_msg}",
            },
            "error": f"Inventory Planning Agent error: {error_msg}",
        }"""
inv_content = inv_content.replace(old_error, new_error)

with open(file_path_inv, 'w', encoding='utf-8') as f:
    f.write(inv_content)

# 2. Update App.jsx
file_path_app = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path_app, 'r', encoding='utf-8') as f:
    app_content = f.read()

old_app = """     if (st._adjustment_plan && st._adjustment_plan.summary) return st._adjustment_plan.summary;
     if (st.analysis) return st.analysis;"""
new_app = """     if (st._adjustment_plan && st._adjustment_plan.summary) return st._adjustment_plan.summary;
     if (st.summary) return st.summary;
     if (st.analysis) return st.analysis;"""
app_content = app_content.replace(old_app, new_app)

with open(file_path_app, 'w', encoding='utf-8') as f:
    f.write(app_content)

print("Updated inventory_agent.py and App.jsx")
