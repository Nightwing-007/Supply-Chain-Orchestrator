import { useState, useRef, useEffect, useCallback } from "react";
import {
  Sun, Moon, Send, Truck, Package, Warehouse as WarehouseIcon,
  TrendingUp, Route, CircleGauge, Bell, Bot, User, Zap,
  ChevronDown, ChevronRight, Activity, Check
} from "lucide-react";
import { runWorkflow, runSingleAgent, checkHealth } from "./api";

const AGENTS = [
  { key: "inventory",    label: "Inventory Planning",    icon: Package },
  { key: "warehouse",    label: "Warehouse Operations",  icon: WarehouseIcon },
  { key: "demand",       label: "Demand Forecasting",    icon: TrendingUp },
  { key: "route",        label: "Route Optimization",    icon: Route },
  { key: "fleet",        label: "Fleet Management",      icon: CircleGauge },
  { key: "notification", label: "Customer Notification", icon: Bell },
];

const DEMO_PROMPTS = [
  { label: "📦 Stock Check",     query: "Check stock levels across all warehouses and generate reorder recommendations." },
  { label: "🏬 Warehouse Ops",   query: "Inspect warehouse utilization and build an optimized pick list." },
  { label: "🛣️ Route Dispatch",  query: "Optimize delivery routes considering current traffic hazards." },
  { label: "🌐 Full Supervisor", query: "Check stock, inspect warehouse capacity, optimize routes, and check fleet health." },
];

const fmtMs = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`);

export default function App() {
  const [theme, setTheme]             = useState("dark");
  const [mode, setMode]               = useState("day2");
  const [selectedAgent, setAgent]     = useState("inventory");
  const [messages, setMessages]       = useState([
    {
      role: "assistant",
      text: "👋 Welcome to the **Supply Chain Orchestrator**.\n\nChoose **Day 1** (single agent) or **Day 2** (multi-agent supervisor) in the sidebar, then type a query or click a demo prompt!",
      agents: ["supervisor"],
      elapsed: 120,
    },
  ]);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [globalState, setGlobalState] = useState({});
  const [apiOnline, setApiOnline]     = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const chatEndRef = useRef(null);

  const isDark = theme === "dark";

  useEffect(() => {
    checkHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    const interval = setInterval(() => {
      checkHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false));
    }, 15_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

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
      // Handle "API Offline" State as requested
      setMessages((prev) => [...prev, { role: "assistant", text: "⚠️ API Offline: Cannot connect to the Supply Chain Orchestrator.", isError: true }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, mode, selectedAgent, globalState]);

  const globalLayout = `h-screen w-full flex overflow-hidden font-sans transition-colors duration-300 ${isDark ? "bg-brand-dark text-brand-light" : "bg-brand-light text-brand-dark"}`;
  const secondaryBg = isDark ? "bg-brand-gray/20" : "bg-white/60";

  return (
    <div className={globalLayout}>
      {/* ════════════  SIDEBAR  ════════════ */}
      <aside className={`${sidebarOpen ? "w-80" : "w-0 overflow-hidden"} flex-shrink-0 border-r border-brand-gray flex flex-col transition-all duration-300 z-20`}>
        <div className="p-6 flex-1 overflow-y-auto flex flex-col gap-4">

          {/* Branding Header */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-green flex items-center justify-center text-black font-bold shadow">
              <Truck size={22} />
            </div>
            <div>
              <h1 className="text-lg font-extrabold tracking-tight">SCO Dashboard</h1>
              <div className="flex items-center gap-1.5 text-xs font-medium opacity-70">
                <span className={`w-2 h-2 rounded-full ${apiOnline ? "bg-brand-green animate-pulse-glow" : "bg-red-500"}`} />
                {apiOnline === true ? "API Connected" : apiOnline === false ? "API Offline" : "Checking..."}
              </div>
            </div>
          </div>

          {/* Theme Toggle */}
          <div className={`flex rounded-xl p-1 border border-brand-gray ${secondaryBg}`}>
            <button onClick={() => setTheme("light")}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition ${!isDark ? "bg-brand-green text-black" : "opacity-60 hover:opacity-100"}`}>
              <Sun size={14} /> Light
            </button>
            <button onClick={() => setTheme("dark")}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition ${isDark ? "bg-brand-green text-black" : "opacity-60 hover:opacity-100"}`}>
              <Moon size={14} /> Dark
            </button>
          </div>

          {/* Orchestration Mode */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wider opacity-60">Orchestration Mode</span>
            <div className={`flex rounded-xl p-1 border border-brand-gray ${secondaryBg}`}>
              <button onClick={() => setMode("day1")}
                className={`flex-1 py-2 rounded-lg text-xs font-semibold transition ${mode === "day1" ? "bg-brand-green text-black" : "opacity-60 hover:opacity-100"}`}>
                Day 1
              </button>
              <button onClick={() => setMode("day2")}
                className={`flex-1 py-2 rounded-lg text-xs font-semibold transition ${mode === "day2" ? "bg-brand-green text-black" : "opacity-60 hover:opacity-100"}`}>
                Day 2
              </button>
            </div>
          </div>

          {/* Target Agent Selector */}
          {mode === "day1" && (
            <div className="flex flex-col gap-2 animate-fade-in">
              <span className="text-xs font-bold uppercase tracking-wider opacity-60">Target Agent</span>
              <div className="flex flex-col gap-2">
                {AGENTS.map((a) => {
                  const Icon = a.icon;
                  const selected = selectedAgent === a.key;
                  return (
                    <button key={a.key} onClick={() => setAgent(a.key)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs transition border ${selected ? "bg-brand-green text-black border-brand-green font-bold" : `border-brand-gray ${secondaryBg} hover:border-brand-green`}`}>
                      <Icon size={16} />
                      <span>{a.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="border-t border-brand-gray my-2" />

          {/* Live Metrics Grid */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wider opacity-60">Live Metrics</span>
            <div className="grid grid-cols-2 gap-4">
              <MetricCard label="Low Stock"  value={((globalState.inventory || {}).low_stock_alerts || []).length} isDark={isDark} />
              <MetricCard label="WH Util"    value={`${(globalState.warehouse || {}).utilization_pct || 0}%`} isDark={isDark} />
              <MetricCard label="Route Dist" value={`${(globalState.route || {}).total_distance_km || 0} km`} isDark={isDark} />
              <MetricCard label="Fleet Util" value={`${(globalState.fleet || {})._fleet_utilization_pct || 0}%`} isDark={isDark} />
            </div>
          </div>

          <div className="border-t border-brand-gray my-2" />

          {/* State Inspector */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wider opacity-60">State Inspector</span>
            <div className="flex flex-col gap-2">
              {["inventory", "warehouse", "demand", "route", "fleet", "notification"].map((key) => (
                <StateExpander key={key} label={key} data={globalState[key]} isDark={isDark} />
              ))}
            </div>
          </div>
        </div>
      </aside>

      {/* ════════════  MAIN PANEL  ════════════ */}
      <main className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <header className="px-6 py-4 border-b border-brand-gray flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen((o) => !o)}
              className={`p-2 rounded-xl border border-brand-gray hover:opacity-80 transition ${secondaryBg}`}>
              {sidebarOpen ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
            </button>
            <div>
              <h1 className="text-base font-bold tracking-tight">Supply Chain Orchestrator</h1>
            </div>
          </div>
        </header>

        {/* Chat History Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg, i) => (
            <ChatBubble key={i} msg={msg} isDark={isDark} />
          ))}
          {loading && (
            <div className="flex items-start gap-3 animate-fade-in">
              <div className="w-10 h-10 rounded-2xl border border-brand-green flex items-center justify-center text-brand-green shrink-0">
                <Bot size={20} className="animate-pulse" />
              </div>
              <div className={`p-4 rounded-2xl border border-brand-gray ${secondaryBg}`}>
                <span className="text-xs font-semibold text-brand-green">Executing...</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-6 border-t border-brand-gray shrink-0">
          <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
            className={`flex items-center gap-4 rounded-full border border-brand-gray p-2 pl-6 transition focus-within:border-brand-green ${secondaryBg}`}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask the orchestrator..."
              disabled={loading}
              className="flex-1 bg-transparent text-sm focus:outline-none disabled:opacity-50"
            />
            <button type="submit" disabled={loading || !input.trim()}
              className="p-3 rounded-full bg-brand-green text-black font-bold hover:opacity-80 transition disabled:opacity-40 shadow shrink-0">
              <Send size={18} />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ label, value, isDark }) {
  const secondaryBg = isDark ? "bg-brand-gray/20" : "bg-white/60";
  return (
    <div className={`rounded-xl border border-brand-gray p-4 text-center ${secondaryBg}`}>
      <div className="text-2xl font-extrabold text-brand-green">{value}</div>
      <div className="text-[0.65rem] uppercase tracking-wider font-bold opacity-60 mt-1">{label}</div>
    </div>
  );
}

function StateExpander({ label, data, isDark }) {
  const [open, setOpen] = useState(false);
  const secondaryBg = isDark ? "bg-brand-gray/20" : "bg-white/60";

  return (
    <div className={`rounded-xl border border-brand-gray overflow-hidden ${secondaryBg}`}>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold hover:opacity-80 transition">
        <span>{label.toUpperCase()}</span>
        <ChevronDown size={16} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-4 py-3 text-xs border-t border-brand-gray max-h-52 overflow-y-auto">
          {data ? (
            <pre className="whitespace-pre-wrap break-words font-mono text-[0.7rem]">
              {JSON.stringify(data, null, 2)}
            </pre>
          ) : (
            <p className="italic opacity-60">No data</p>
          )}
        </div>
      )}
    </div>
  );
}

function ChatBubble({ msg, isDark }) {
  const isUser = msg.role === "user";
  const secondaryBg = isDark ? "bg-brand-gray/20" : "bg-white/60";

  return (
    <div className={`flex items-start gap-3 animate-fade-in ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 font-bold ${
        isUser ? "bg-brand-green text-black" : "border border-brand-green text-brand-green"
      }`}>
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className={`max-w-[78%] rounded-2xl p-4 text-sm leading-relaxed ${
        isUser
          ? "bg-brand-green text-black rounded-tr-sm"
          : `${msg.isError ? "border-red-500 text-red-400" : "border-brand-gray"} border ${secondaryBg} rounded-tl-sm`
      }`}>
        <div className="whitespace-pre-wrap">
          {msg.text}
        </div>
      </div>
    </div>
  );
}
