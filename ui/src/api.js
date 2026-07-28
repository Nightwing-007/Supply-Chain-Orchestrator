import axios from "axios";

const API = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 90_000,
  headers: { "Content-Type": "application/json" },
});

/** POST /api/workflow — Day 2 Multi-Agent Supervisor */
export async function runWorkflow(query, intent = "general_check") {
  const { data } = await API.post("/api/workflow", { query, intent });
  return data;
}

/** POST /api/agent/{name} — Day 1 Single Agent */
export async function runSingleAgent(agentName, query, currentState = {}) {
  const { data } = await API.post(`/api/agent/${agentName}`, {
    query,
    state: currentState,
  });
  return data;
}

/** GET /health — liveness probe */
export async function checkHealth() {
  const { data } = await API.get("/health");
  return data;
}
