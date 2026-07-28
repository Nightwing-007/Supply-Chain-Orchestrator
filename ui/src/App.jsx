import { useState, useRef, useEffect, useCallback } from "react";
import {
  Sun, Moon, Send, Truck, Package, Warehouse as WarehouseIcon,
  TrendingUp, Route, CircleGauge, Bell, Bot, User, Zap,
  ChevronDown, ChevronRight, Activity, AlertTriangle, Check,
} from "lucide-react";
import { runWorkflow, runSingleAgent, checkHealth } from "./api";

/* ── Agent Registry ───────────────────────────────────────── */

const AGENTS = [
  { key: "inventory",    label: "Inventory Planning",    icon: Package,        color: "text-brand-green" },
  { key: "warehouse",    label: "Warehouse Operations",  icon: WarehouseIcon,  color: "text-amber-400" },
  { key: "demand",       label: "Demand Forecasting",    icon: TrendingUp,     color: "text-sky-400" },
  { key: "route",        label: "Route Optimization",    icon: Route,          color: "text-purple-400" },
  { key: "fleet",        label: "Fleet Management",      icon: CircleGauge,    color: "text-rose-400" },
  { key: "notification", label: "Customer Notification", icon: Bell,           color: "text-teal-400" },
];

const DEMO_PROMPTS = [
  { label: "📦 Stock Check",     query: "Check stock levels across all warehouses and generate reorder recommendations." },
  { label: "🏬 Warehouse Ops",   query: "Inspect warehouse utilization and build an optimized pick list." },
  { label: "🛣️ Route Dispatch",  query: "Optimize delivery routes considering current traffic hazards." },
  { label: "🌐 Full Supervisor", query: "Check stock, inspect warehouse capacity, optimize routes, and check fleet health." },
];

/* ── Helper: format elapsed time ──────────────────────────── */
const fmtMs = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`);

/* ── App Component ────────────────────────────────────────── */

export default function App() {
  const [theme, setTheme]             = useState("dark");
  const [mode, setMode]               = useState("day2");        // day1 | day2
  const [selectedAgent, setAgent]     = useState("inventory");
  const [messages, setMessages]       = useState([
    { role: "assistant", text: "👋 Welcome to the **Supply Chain Orchestrator**.\n\nChoose **Day 1** (single agent) or **Day 2** (multi-agent supervisor) in the sidebar, then type a query or click a demo prompt!" },
  ]);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [globalState, setGlobalState] = useState({});
  const [apiOnline, setApiOnline]     = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const chatEndRef = useRef(null);

  const isDark = theme === "dark";

  // ── Health Check on mount ─────────────────────────────────
  useEffect(() => {
    checkHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    const interval = setInterval(() => {
      checkHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    }, 15_000);
    return () => clearInterval(interval);
  }, []);

  // ── Auto-scroll chat ──────────────────────────────────────
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ── Submit handler ────────────────────────────────────────
  const handleSubmit = useCallback(async (overrideQuery) => {
    const query = overrideQuery || input.trim();
    if (!query || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setLoading(true);

    try {
      const t0 = performance.now();
      let res;
      if (mode === "day1") {
        res = await runSingleAgent(selectedAgent, query, globalState);
      } else {
        res = await runWorkflow(query);
      }
      const elapsed = performance.now() - t0;

      const state = res.state || {};
      setGlobalState(state);

      const agents = (state.agent_responses || [])
        .map((r) => r.agent)
        .filter((a) => a && a !== "supervisor");

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.final_answer || "Agent executed successfully.",
          agents: mode === "day1" ? [selectedAgent] : agents,
          elapsed,
          mode,
        },
      ]);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Unknown error";
      setMessages((prev) => [...prev, { role: "assistant", text: `❌ Error: ${detail}`, isError: true }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, mode, selectedAgent, globalState]);

  // ── Theme classes ─────────────────────────────────────────
  const bg    = isDark ? "bg-brand-dark"  : "bg-brand-light";
  const surf  = isDark ? "bg-[#2e2f2e]"  : "bg-white";
  const txt   = isDark ? "text-gray-100"  : "text-brand-dark";
  const muted = isDark ? "text-gray-400"  : "text-brand-gray";
  const brd   = isDark ? "border-brand-gray/40" : "border-gray-300";

  return (
    <div className={`flex h-screen ${bg} ${txt} transition-colors duration-300`}>

      {/* ════════════  SIDEBAR  ════════════ */}
      <aside className={`${sidebarOpen ? "w-80" : "w-0 overflow-hidden"} flex-shrink-0 ${surf} border-r ${brd} flex flex-col transition-all duration-300`}>
        <div className="p-5 flex-1 overflow-y-auto">

          {/* Branding */}
          <div className="flex items-center gap-2 mb-5">
            <Truck className="text-brand-green" size={28} />
            <h1 className="text-lg font-bold tracking-tight">SCO Dashboard</h1>
          </div>

          {/* Theme Toggle */}
          <div className={`flex rounded-lg ${isDark ? "bg-brand-dark" : "bg-gray-200"} p-1 mb-5`}>
            <button onClick={() => setTheme("light")}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-sm font-medium transition ${theme === "light" ? "bg-brand-green text-white shadow" : muted}`}>
              <Sun size={14} /> Light
            </button>
            <button onClick={() => setTheme("dark")}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-sm font-medium transition ${theme === "dark" ? "bg-brand-green text-white shadow" : muted}`}>
              <Moon size={14} /> Dark
            </button>
          </div>

          {/* API Status */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium mb-5 ${apiOnline === true ? "bg-brand-green/10 text-brand-green" : apiOnline === false ? "bg-rose-500/10 text-rose-400" : "bg-yellow-500/10 text-yellow-400"}`}>
            <span className={`w-2 h-2 rounded-full ${apiOnline === true ? "bg-brand-green" : apiOnline === false ? "bg-rose-400" : "bg-yellow-400"}`} />
            {apiOnline === true ? "API Connected — :8000" : apiOnline === false ? "API Offline" : "Checking…"}
          </div>

          {/* Mode Toggle */}
          <h2 className={`text-xs font-semibold uppercase tracking-wider ${muted} mb-2`}>Orchestration Mode</h2>
          <div className={`flex rounded-lg ${isDark ? "bg-brand-dark" : "bg-gray-200"} p-1 mb-4`}>
            <button onClick={() => setMode("day1")}
              className={`flex-1 py-2 rounded-md text-xs font-semibold transition ${mode === "day1" ? "bg-brand-green text-white shadow" : muted}`}>
              Day 1 — Single
            </button>
            <button onClick={() => setMode("day2")}
              className={`flex-1 py-2 rounded-md text-xs font-semibold transition ${mode === "day2" ? "bg-brand-green text-white shadow" : muted}`}>
              Day 2 — Multi
            </button>
          </div>

          {/* Agent Selector (Day 1 only) */}
          {mode === "day1" && (
            <div className="mb-5 animate-fade-in-up">
              <h2 className={`text-xs font-semibold uppercase tracking-wider ${muted} mb-2`}>Target Agent</h2>
              <div className="space-y-1">
                {AGENTS.map((a) => {
                  const Icon = a.icon;
                  const active = selectedAgent === a.key;
                  return (
                    <button key={a.key} onClick={() => setAgent(a.key)}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition
                        ${active ? "bg-brand-green/15 text-brand-green border border-brand-green/40" : `${surf} ${muted} hover:bg-brand-green/5 border border-transparent`}`}>
                      <Icon size={16} className={active ? "text-brand-green" : ""} />
                      {a.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <hr className={`${brd} my-4`} />

          {/* Live Metrics */}
          <h2 className={`text-xs font-semibold uppercase tracking-wider ${muted} mb-3`}>Live Metrics</h2>
          <div className="grid grid-cols-2 gap-2 mb-4">
            <MetricCard label="Low Stock"  value={((globalState.inventory || {}).low_stock_alerts || []).length}  isDark={isDark} />
            <MetricCard label="WH Util"    value={`${(globalState.warehouse || {}).utilization_pct || 0}%`}      isDark={isDark} />
            <MetricCard label="Route Dist" value={`${(globalState.route || {}).total_distance_km || 0} km`}      isDark={isDark} />
            <MetricCard label="Fleet Util" value={`${(globalState.fleet || {})._fleet_utilization_pct || 0}%`}   isDark={isDark} />
          </div>

          <hr className={`${brd} my-4`} />

          {/* JSON State Inspector */}
          <h2 className={`text-xs font-semibold uppercase tracking-wider ${muted} mb-3`}>State Inspector</h2>
          {["inventory", "warehouse", "demand", "route", "fleet", "notification"].map((key) => (
            <StateExpander key={key} label={key} data={globalState[key]} isDark={isDark} brd={brd} surf={surf} muted={muted} />
          ))}
          <StateExpander label="Full State" data={Object.keys(globalState).length > 0 ? globalState : null} isDark={isDark} brd={brd} surf={surf} muted={muted} />
        </div>
      </aside>

      {/* ════════════  MAIN AREA  ════════════ */}
      <main className="flex-1 flex flex-col min-w-0">

        {/* Top Bar */}
        <header className={`flex items-center justify-between px-6 py-3 border-b ${brd} ${surf}`}>
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen((o) => !o)} className={`p-1.5 rounded-lg hover:bg-brand-green/10 transition ${muted}`}>
              {sidebarOpen ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
            </button>
            <div>
              <h1 className="text-base font-bold tracking-tight flex items-center gap-2">
                <span className="text-brand-green">🚛</span> Supply Chain Orchestrator
              </h1>
              <p className={`text-xs ${muted}`}>LangGraph • PostgreSQL • Google Gemini • CampusOS</p>
            </div>
          </div>
          <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${mode === "day1" ? "border-brand-green/50 text-brand-green bg-brand-green/10" : "border-sky-400/50 text-sky-400 bg-sky-400/10"}`}>
            {mode === "day1" ? `🔬 Single Agent — ${AGENTS.find(a => a.key === selectedAgent)?.label}` : "🌐 Multi-Agent Supervisor"}
          </span>
        </header>

        {/* Demo Prompt Bar */}
        <div className={`flex items-center gap-2 px-6 py-2.5 border-b ${brd} ${surf} overflow-x-auto`}>
          <Zap size={14} className="text-brand-green flex-shrink-0" />
          <span className={`text-xs font-semibold ${muted} flex-shrink-0 mr-1`}>Quick Demos:</span>
          {DEMO_PROMPTS.map((d) => (
            <button key={d.label} onClick={() => handleSubmit(d.query)} disabled={loading}
              className={`flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium border ${brd} hover:border-brand-green hover:text-brand-green transition disabled:opacity-40`}>
              {d.label}
            </button>
          ))}
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.map((msg, i) => (
            <ChatBubble key={i} msg={msg} isDark={isDark} brd={brd} surf={surf} muted={muted} />
          ))}
          {loading && (
            <div className="flex items-start gap-3 animate-fade-in-up">
              <div className="w-8 h-8 rounded-full bg-brand-green/20 flex items-center justify-center flex-shrink-0">
                <Bot size={16} className="text-brand-green" />
              </div>
              <div className={`px-4 py-3 rounded-2xl ${surf} border ${brd}`}>
                <span className="typing-dot" />{" "}
                <span className="typing-dot" />{" "}
                <span className="typing-dot" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
          className={`flex items-center gap-3 px-6 py-4 border-t ${brd} ${surf}`}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={mode === "day1"
              ? `Query ${AGENTS.find(a => a.key === selectedAgent)?.label}…`
              : "Ask the Multi-Agent Supervisor…"}
            disabled={loading}
            className={`flex-1 px-4 py-2.5 rounded-xl border ${brd} ${isDark ? "bg-brand-dark" : "bg-gray-100"} ${txt}
              placeholder:${muted} focus:outline-none focus:ring-2 focus:ring-brand-green/50 focus:border-brand-green transition disabled:opacity-50`}
          />
          <button type="submit" disabled={loading || !input.trim()}
            className="p-2.5 rounded-xl bg-brand-green text-white hover:bg-green-600 active:scale-95 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-brand-green/25">
            <Send size={18} />
          </button>
        </form>
      </main>
    </div>
  );
}


/* ── Sub-Components ───────────────────────────────────────── */

function MetricCard({ label, value, isDark }) {
  return (
    <div className={`rounded-lg border ${isDark ? "border-brand-gray/40 bg-brand-dark" : "border-gray-300 bg-gray-50"} p-3 text-center
      hover:border-brand-green hover:shadow-[0_0_12px_rgba(84,199,80,0.15)] transition group`}>
      <div className="text-xl font-bold text-brand-green group-hover:scale-105 transition-transform">{value}</div>
      <div className={`text-[0.65rem] uppercase tracking-wider font-semibold ${isDark ? "text-gray-500" : "text-brand-gray"}`}>{label}</div>
    </div>
  );
}

function StateExpander({ label, data, isDark, brd, surf, muted }) {
  const [open, setOpen] = useState(false);
  const icon_map = { inventory: "📦", warehouse: "🏬", demand: "📈", route: "🛣️", fleet: "🚚", notification: "💬" };
  const icon = icon_map[label] || "⚙️";

  return (
    <div className={`mb-1.5 rounded-lg border ${brd} overflow-hidden`}>
      <button onClick={() => setOpen(!open)} className={`w-full flex items-center justify-between px-3 py-2 text-xs font-medium ${surf} hover:bg-brand-green/5 transition`}>
        <span>{icon} {label.charAt(0).toUpperCase() + label.slice(1)}</span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""} ${muted}`} />
      </button>
      {open && (
        <div className={`px-3 py-2 text-xs ${isDark ? "bg-brand-dark" : "bg-gray-50"} border-t ${brd} max-h-52 overflow-y-auto`}>
          {data ? (
            <pre className={`whitespace-pre-wrap break-words ${muted}`}>{JSON.stringify(data, null, 2)}</pre>
          ) : (
            <p className={muted}>No data yet.</p>
          )}
        </div>
      )}
    </div>
  );
}

function ChatBubble({ msg, isDark, brd, surf, muted }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex items-start gap-3 animate-fade-in-up ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
        ${isUser ? "bg-brand-green" : msg.isError ? "bg-rose-500/20" : "bg-brand-green/20"}`}>
        {isUser ? <User size={16} className="text-white" /> : <Bot size={16} className={msg.isError ? "text-rose-400" : "text-brand-green"} />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed
        ${isUser
          ? "bg-brand-green text-white rounded-tr-sm"
          : `${surf} border ${brd} rounded-tl-sm ${msg.isError ? "border-rose-500/40" : ""}`}`}>

        {/* Agent badges */}
        {msg.agents && msg.agents.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {msg.agents.map((a) => (
              <span key={a} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.65rem] font-semibold bg-brand-green/15 text-brand-green border border-brand-green/30">
                <Check size={10} /> {a}
              </span>
            ))}
            {msg.elapsed != null && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.65rem] font-medium ${isDark ? "bg-gray-700 text-gray-300" : "bg-gray-200 text-gray-600"}`}>
                <Activity size={10} /> {fmtMs(msg.elapsed)}
              </span>
            )}
          </div>
        )}

        {/* Text (simple markdown-ish bold) */}
        <div className="whitespace-pre-wrap">
          {msg.text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
            part.startsWith("**") && part.endsWith("**")
              ? <strong key={i}>{part.slice(2, -2)}</strong>
              : <span key={i}>{part}</span>
          )}
        </div>
      </div>
    </div>
  );
}
