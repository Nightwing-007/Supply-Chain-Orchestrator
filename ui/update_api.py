import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\api.js'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """
/** GET /api/dashboard — Fetch live metrics */
export async function fetchDashboardData() {
  const { data } = await API.get("/api/dashboard");
  return data;
}
"""

if "fetchDashboardData" not in content:
    content += new_func
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated api.js")
