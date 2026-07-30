import axios from "axios";

const API = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 90_000,
  headers: { "Content-Type": "application/json" },
});

/** POST /api/workflow — Multi Agent Mode Multi-Agent Supervisor */
export async function runWorkflow(query, intent = "general_check") {
  const { data } = await API.post("/api/workflow", { query, intent });
  return data;
}

/** POST /api/agent/{name} — Standalone Single AI Agent */
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

/** GET /api/dashboard — Fetch live metrics */
export async function fetchDashboardData() {
  const { data } = await API.get("/api/dashboard");
  return data;
}

/** POST /api/login — Shop Owner Login */
export async function loginUser(username, password) {
  const { data } = await API.post("/api/login", { username, password });
  return data;
}

/** GET /api/products — Fetch product catalog */
export async function fetchProducts() {
  const { data } = await API.get("/api/products");
  return data;
}

/** POST /api/products — Add new product */
export async function createProduct(productData) {
  const { data } = await API.post("/api/products", productData);
  return data;
}

/** PUT /api/products/{id} — Update product details/stock */
export async function updateProduct(itemId, productData) {
  const { data } = await API.put(`/api/products/${itemId}`, productData);
  return data;
}

/** DELETE /api/products/{id} — Delete a product */
export async function deleteProduct(itemId) {
  const { data } = await API.delete(`/api/products/${itemId}`);
  return data;
}
