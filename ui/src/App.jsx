import { useState, useEffect, useRef } from "react";
import { 
  Search, Moon, Sun, ArrowRight, MessageSquare, Send, AlertTriangle, 
  Package, Activity, Cpu, Database, Network, Server, User,
  RefreshCw, GitBranch, CheckCircle2, ShieldAlert, Lock, ShoppingBag, LogOut
} from "lucide-react";
import { runWorkflow, runSingleAgent, fetchDashboardData } from "./api";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line, Legend } from "recharts";
import ReactMarkdown from "react-markdown";
import Login from "./components/Login";
import ShopManagement from "./components/ShopManagement";

const AGENTS = [
  { id: 'inventory', name: 'Inventory Planning', icon: Database, color: 'text-accent-primary' },
  { id: 'warehouse', name: 'Warehouse Ops', icon: Package, color: 'text-accent-success' },
  { id: 'demand', name: 'Demand Forecasting', icon: Activity, color: 'text-accent-warning' },
  { id: 'route', name: 'Route Optimization', icon: Network, color: 'text-accent-primary' },
  { id: 'fleet', name: 'Fleet Management', icon: Cpu, color: 'text-accent-critical' },
  { id: 'notification', name: 'Customer Notification', icon: MessageSquare, color: 'text-accent-success' },
];

export default function App() {
  const [isDark, setIsDark] = useState(true);
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [agentState, setAgentState] = useState(null);
  
  const [orchestratorMode, setOrchestratorMode] = useState("single");
  const [selectedSingleAgent, setSelectedSingleAgent] = useState("inventory");
  
  // Dashboard Data State
  const [dashboardData, setDashboardData] = useState(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(true);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Authentication State
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);

  const chatEndRef = useRef(null);

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) root.classList.add("dark");
    else root.classList.remove("dark");
  }, [isDark]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const data = await fetchDashboardData();
        setDashboardData(data);
      } catch (err) {
        console.error("Failed to fetch dashboard data", err);
      } finally {
        setIsLoadingDashboard(false);
      }
    };
    loadDashboard();
    
    // Refresh every 30 seconds
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, []);

  const submitQuery = async (queryText) => {
    if (!queryText.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content: queryText }]);
    setIsTyping(true);
    if (window.innerWidth < 1024) {
      document.querySelector('aside')?.scrollIntoView({ behavior: 'smooth' });
    }

    try {
      let response;
      if (orchestratorMode === "multi") {
        response = await runWorkflow(queryText);
      } else {
        response = await runSingleAgent(selectedSingleAgent, queryText, agentState || {});
      }
      
      setMessages(prev => [...prev, { 
        role: 'bot', 
        isError: response.state && response.state[selectedSingleAgent]?.llm_debug_error ? true : false,
        content: (function() {
          if (response.final_answer && !response.final_answer.startsWith("Standalone Single Agent")) return response.final_answer;
          if (response.state && response.state[selectedSingleAgent]) {
             const st = response.state[selectedSingleAgent];
             if (st.llm_debug_error) return `⚠️ LLM ERROR: ${st.llm_debug_error}`;
             if (st._adjustment_plan && st._adjustment_plan.summary) return st._adjustment_plan.summary;
             if (st.analysis) return st.analysis;
             if (st.message) return st.message;
             if (st.summary) return st.summary;
             if (Object.keys(st).length > 0) {
               return `Agent executed successfully. Result:\n${JSON.stringify(st, null, 2)}`;
             }
          }
          return response.final_answer || response.final_response || "Execution completed successfully.";
        })() 
      }]);
      
      if (response.state) {
         setAgentState(response.state);
      } else if (response.agent_state) {
         setAgentState(prev => ({
           ...prev,
           [selectedSingleAgent]: response.agent_state
         }));
      }
    } catch (err) {
      setMessages(prev => [...prev, { 
        role: 'bot', 
        content: "Error connecting to backend. Please ensure the FastAPI server is running and the database is configured." 
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const text = chatInput;
    setChatInput('');
    await submitQuery(text);
  };

  const renderKPIBar = () => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
      {/* 1. Critical Alerts */}
      <div className="p-6 bg-border-panel/10 border border-border-panel rounded-xl flex items-center justify-between relative overflow-hidden">
        <div>
          <span className="text-xs uppercase tracking-widest font-medium text-text-secondary">Critical Alerts</span>
          <div className="text-3xl font-light tracking-tight mt-1 flex items-center gap-3">
            {dashboardData?.kpis?.critical_alerts ?? 4}
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
          </div>
        </div>
        <div className="p-3 bg-red-500/10 text-red-400 rounded-lg border border-red-500/20">
          <AlertTriangle size={22} />
        </div>
      </div>

      {/* 2. Total Items Tracked */}
      <div className="p-6 bg-border-panel/10 border border-border-panel rounded-xl flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-widest font-medium text-text-secondary">Total Items Tracked</span>
          <div className="text-3xl font-light tracking-tight mt-1">
            {dashboardData?.kpis?.total_items ?? 10} <span className="text-xs text-text-secondary font-mono">SKUs</span>
          </div>
        </div>
        <div className="p-3 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
          <Database size={22} />
        </div>
      </div>

      {/* 3. Active Shipments */}
      <div className="p-6 bg-border-panel/10 border border-border-panel rounded-xl flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-widest font-medium text-text-secondary">Active Shipments</span>
          <div className="text-3xl font-light tracking-tight mt-1">
            {dashboardData?.kpis?.active_shipments ?? dashboardData?.shipments?.length ?? 4} <span className="text-xs text-text-secondary font-mono">EN ROUTE</span>
          </div>
        </div>
        <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
          <Package size={22} />
        </div>
      </div>

      {/* 4. Avg Warehouse Fill % */}
      <div className="p-6 bg-border-panel/10 border border-border-panel rounded-xl flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-widest font-medium text-text-secondary">Avg Warehouse Fill</span>
          <div className="text-3xl font-light tracking-tight mt-1">
            {dashboardData?.kpis?.avg_fill_pct ?? 89.0}%
          </div>
        </div>
        <div className="p-3 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/20">
          <Activity size={22} />
        </div>
      </div>
    </div>
  );

  const renderInventoryGauges = () => (
    <div className="space-y-4">
      {(dashboardData?.inventory_items || [
        { sku: 'SKU-ELEC-001', product_name: 'Wireless Bluetooth Headphones', quantity_on_hand: 5, reorder_point: 100, warehouse_code: 'WH-MUM-01' },
        { sku: 'SKU-ELEC-002', product_name: '27" 4K Gaming Monitor', quantity_on_hand: 2, reorder_point: 50, warehouse_code: 'WH-MUM-01' },
        { sku: 'SKU-HOME-001', product_name: 'Ergonomic Mesh Office Chair', quantity_on_hand: 0, reorder_point: 30, warehouse_code: 'WH-MUM-01' },
        { sku: 'SKU-HOME-002', product_name: 'Motorized Standing Desk Converter', quantity_on_hand: 3, reorder_point: 40, warehouse_code: 'WH-MUM-01' },
      ]).map((item, idx) => {
        const stockRatio = item.reorder_point > 0 ? (item.quantity_on_hand / item.reorder_point) : 1;
        const fillPercentage = Math.min(Math.round(stockRatio * 100), 100);
        let barColor = "bg-emerald-500";
        let badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        let statusLabel = "Healthy";

        if (item.quantity_on_hand === 0 || stockRatio <= 0.25) {
          barColor = "bg-red-500";
          badgeColor = "bg-red-500/10 text-red-400 border-red-500/20";
          statusLabel = item.quantity_on_hand === 0 ? "OUT OF STOCK" : "Critical Deficit";
        } else if (item.quantity_on_hand <= item.reorder_point) {
          barColor = "bg-amber-500";
          badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/20";
          statusLabel = "Low Stock Alert";
        }

        return (
          <div key={idx} className="p-6 border border-border-panel bg-border-panel/10 rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs px-2 py-0.5 bg-border-panel rounded text-text-secondary">{item.sku}</span>
                  <h3 className="font-medium text-base tracking-wide">{item.product_name}</h3>
                </div>
                <p className="text-xs text-text-secondary mt-1">Warehouse Hub: <span className="font-mono">{item.warehouse_code || 'WH-MUM-01'}</span></p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-3 py-1 rounded-full border font-medium ${badgeColor}`}>
                  {statusLabel}
                </span>
                <button
                  onClick={() => submitQuery(`Check inventory and create an auto-restock plan for SKU ${item.sku} (${item.product_name})`)}
                  className="text-xs font-medium uppercase tracking-wider px-3 py-1.5 bg-accent-primary/20 text-accent-primary border border-accent-primary/30 rounded-lg hover:bg-accent-primary hover:text-bg-base transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <RefreshCw size={13} />
                  Auto-Restock
                </button>
              </div>
            </div>

            {/* Visual Progress Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono text-text-secondary">
                <span>Available: <strong className="text-text-primary">{item.quantity_on_hand} units</strong></span>
                <span>Reorder Threshold: <strong className="text-text-primary">{item.reorder_point} units</strong></span>
              </div>
              <div className="w-full bg-border-panel/40 h-2.5 rounded-full overflow-hidden">
                <div className={`h-full transition-all duration-500 ${barColor}`} style={{ width: `${Math.max(fillPercentage, 4)}%` }}></div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );

  const renderDashboard = () => (
    <>
      <header className="mb-12">
        <h1 className="text-4xl font-light tracking-tight mb-2">Live Telemetry</h1>
        <p className="text-text-secondary">Monitoring global supply chain metrics directly from PostgreSQL.</p>
      </header>

      {/* Top 4-Column KPI Summary Bar */}
      {renderKPIBar()}

      {isLoadingDashboard ? (
        <div className="text-text-secondary text-sm">Loading real-time data from database...</div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-16 gap-y-16">
          {/* Inventory Stock vs. Reorder Threshold Comparison Chart */}
          <section className="xl:col-span-2">
            <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
              <div>
                <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Inventory Stock vs. Reorder Threshold</h2>
                <p className="text-xs text-text-secondary mt-0.5">Real-time comparison of available stock against safety thresholds across SKUs</p>
              </div>
              <span className="text-xs font-mono text-text-secondary text-accent-primary">LIVE DB</span>
            </div>
            <div className="h-[360px] w-full bg-border-panel/10 p-6 rounded-xl border border-border-panel">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart 
                  data={dashboardData?.inventory_items || [
                    { sku: 'SKU-ELEC-001', quantity_on_hand: 5, reorder_point: 100 },
                    { sku: 'SKU-ELEC-002', quantity_on_hand: 2, reorder_point: 50 },
                    { sku: 'SKU-HOME-001', quantity_on_hand: 0, reorder_point: 30 },
                    { sku: 'SKU-HOME-002', quantity_on_hand: 3, reorder_point: 40 },
                    { sku: 'SKU-ELEC-003', quantity_on_hand: 220, reorder_point: 25 },
                    { sku: 'SKU-GROC-001', quantity_on_hand: 1200, reorder_point: 100 },
                  ]} 
                  margin={{ top: 10, right: 20, left: -10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="sku" stroke="var(--color-text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--color-text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1e293b', 
                      borderColor: '#334155', 
                      color: '#fff',
                      borderRadius: '0.5rem',
                      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)'
                    }}
                    itemStyle={{ color: '#fff' }}
                    formatter={(value, name) => [
                      `${value} units`, 
                      name === 'quantity_on_hand' ? 'Available Stock' : 'Reorder Threshold'
                    ]}
                  />
                  <Legend 
                    wrapperStyle={{ paddingTop: '10px' }}
                    formatter={(value) => (
                      <span className="text-xs font-medium text-text-secondary">
                        {value === 'quantity_on_hand' ? 'Available Stock' : 'Reorder Threshold'}
                      </span>
                    )}
                  />
                  <Bar dataKey="quantity_on_hand" name="quantity_on_hand" fill="#10b981" radius={[4, 4, 0, 0]} barSize={20} />
                  <Bar dataKey="reorder_point" name="reorder_point" fill="#64748b" radius={[4, 4, 0, 0]} barSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="xl:col-span-2">
            <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
              <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Route Tracking (Load over time)</h2>
              <span className="text-xs font-mono text-text-secondary text-accent-primary">ACTIVE</span>
            </div>
            <div className="h-[360px] w-full flex flex-col items-center justify-center bg-border-panel/10 p-4 rounded-xl border border-border-panel">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dashboardData?.flow || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorOut" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-accent-primary)" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="var(--color-accent-primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-panel)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--color-text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--color-text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--color-bg-panel)', borderColor: 'var(--color-border-panel)', color: 'var(--color-text-primary)' }}
                    itemStyle={{ color: 'var(--color-text-primary)' }}
                  />
                  <Area type="monotone" dataKey="out" stroke="var(--color-accent-primary)" fillOpacity={1} fill="url(#colorOut)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section>
            <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
              <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Performance</h2>
              <span className="text-xs text-text-secondary">Last 7 Days</span>
            </div>
            <div className="h-48 w-full bg-border-panel/10 p-4 rounded-xl border border-border-panel">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dashboardData?.performance || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-panel)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--color-text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--color-bg-panel)', borderColor: 'var(--color-border-panel)', color: 'var(--color-text-primary)' }}
                  />
                  <Line type="monotone" dataKey="value" stroke="var(--color-accent-success)" strokeWidth={2} dot={{ r: 4, fill: 'var(--color-bg-panel)' }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section>
            <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
              <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Flow Analysis</h2>
              <button className="text-xs text-text-primary hover:underline uppercase tracking-wider font-medium">Interact</button>
            </div>
            <div className="h-48 w-full bg-border-panel/10 p-4 rounded-xl border border-border-panel">
               <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dashboardData?.flow || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-panel)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--color-text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--color-bg-panel)', borderColor: 'var(--color-border-panel)' }}
                  />
                  <Line type="monotone" dataKey="in" stroke="var(--color-accent-warning)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        </div>
      )}
    </>
  );

  const renderShipments = () => (
    <>
      <header className="mb-12">
        <h1 className="text-4xl font-light tracking-tight mb-2">Active Shipments</h1>
        <p className="text-text-secondary">
          {isLoadingDashboard 
            ? 'Loading active shipments...' 
            : `Tracking ${dashboardData?.shipments?.length || 0} ongoing freight movements.`}
        </p>
      </header>

      {renderKPIBar()}

      <div className="w-full">
        <div className="grid grid-cols-5 border-b border-border-panel pb-4 mb-4 text-xs font-medium tracking-widest text-text-secondary uppercase">
          <div className="col-span-2">Shipment ID</div>
          <div>Origin</div>
          <div>Destination</div>
          <div className="text-right">Status</div>
        </div>
        <div className="space-y-2">
          {dashboardData?.shipments?.map((shipment, idx) => (
            <div key={idx} className="grid grid-cols-5 items-center border-b border-border-panel/50 pb-4 pt-2 text-sm">
              <div className="col-span-2 flex items-center gap-3">
                <Package size={16} className="text-text-secondary" />
                <span className="font-mono">{shipment.tracking_number}</span>
              </div>
              <div className="text-text-secondary">{shipment.origin || 'Warehouse A'}</div>
              <div className="text-text-secondary">{shipment.destination || 'N/A'}</div>
              <div className="text-right flex items-center justify-end gap-2 text-accent-primary">
                <Activity size={14} />
                <span className="capitalize">{shipment.status.replace('_', ' ')}</span>
              </div>
            </div>
          ))}
          {!isLoadingDashboard && (!dashboardData?.shipments || dashboardData.shipments.length === 0) && (
             <div className="text-sm text-text-secondary py-4">No active shipments found in the database.</div>
          )}
        </div>
      </div>
    </>
  );

  const renderRisks = () => (
    <>
      <header className="mb-12">
        <h1 className="text-4xl font-light tracking-tight mb-2">Risk Intel & Inventory Gauges</h1>
        <p className="text-text-secondary">Automated vulnerability tracking and real-time inventory threshold gauges.</p>
      </header>

      {renderKPIBar()}

      <div className="space-y-8">
        <section>
          <h2 className="text-sm font-medium uppercase tracking-widest text-text-secondary mb-4">Stock Health Gauges & Thresholds</h2>
          {renderInventoryGauges()}
        </section>

        <section>
          <h2 className="text-sm font-medium uppercase tracking-widest text-text-secondary mb-4">System Disruption Alerts</h2>
          <div className="space-y-4">
            {isLoadingDashboard ? (
              <div className="text-text-secondary text-sm">Analyzing supply chain risks...</div>
            ) : dashboardData?.risks?.map((risk, i) => (
              <div key={i} className={`p-6 border flex items-start gap-4 rounded-xl ${
                risk.level === 'Critical' ? 'border-accent-critical/20 bg-accent-critical/10' : 'border-accent-warning/20 bg-accent-warning/10'
              }`}>
                <AlertTriangle size={20} className={risk.level === 'Critical' ? 'text-accent-critical' : 'text-accent-warning'} />
                <div className="flex-1">
                  <h3 className={`text-sm font-medium uppercase tracking-wider mb-2 ${
                    risk.level === 'Critical' ? 'text-accent-critical' : 'text-accent-warning'
                  }`}>{risk.level}</h3>
                  <p className="text-sm font-light leading-relaxed">{risk.text}</p>
                  <div className="mt-4 flex gap-4">
                    <button onClick={() => submitQuery(`Create a mitigation plan for the following risk: ${risk.text}`)} className={`text-xs uppercase tracking-widest font-medium hover:opacity-70 transition-opacity ${
                      risk.level === 'Critical' ? 'text-accent-critical' : 'text-accent-warning'
                    }`}>Mitigate</button>
                    <button onClick={() => submitQuery(`Provide more details and analysis for the following risk: ${risk.text}`)} className="text-xs uppercase tracking-widest font-medium text-text-secondary hover:text-text-primary transition-colors">Details</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );

  const renderAgents = () => {
    return (
      <>
        <header className="mb-16">
          <h1 className="text-4xl font-light tracking-tight mb-2">Agent State Inspector</h1>
          <p className="text-text-secondary">Real-time status and internal state of all 6 AI orchestrator agents.</p>
        </header>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {AGENTS.map((agent) => (
            <div key={agent.id} className="p-6 border border-border-panel bg-border-panel/10 rounded-xl flex flex-col gap-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 bg-border-panel/30 rounded-lg ${agent.color}`}>
                    <agent.icon size={20} />
                  </div>
                  <h3 className="font-medium tracking-wide">{agent.name}</h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${agentState && agentState[agent.id] ? 'bg-accent-success' : 'bg-accent-warning'}`}></span>
                    <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${agentState && agentState[agent.id] ? 'bg-accent-success' : 'bg-accent-warning'}`}></span>
                  </span>
                  <span className="text-xs uppercase tracking-widest text-text-secondary">{agentState && agentState[agent.id] ? 'Idle' : 'Awaiting Workflow'}</span>
                </div>
              </div>
              <div className="mt-2 bg-bg-base border border-border-panel rounded-lg p-4 overflow-x-auto h-48 custom-scrollbar">
                <pre className="text-xs font-mono text-text-secondary">
                  {agentState && agentState[agent.id] 
                    ? JSON.stringify(agentState[agent.id], null, 2) 
                    : `// No state available for ${agent.id}
// Run a workflow via Gemini to populate.`}
                </pre>
              </div>
            </div>
          ))}
        </div>
      </>
    );
  };

  const renderShopPortal = () => {
    if (!isAuthenticated) {
      return (
        <div className="flex flex-col items-center justify-center py-20 space-y-6 text-center">
          <div className="p-4 bg-accent-primary/10 text-accent-primary rounded-2xl border border-accent-primary/20">
            <Lock size={40} />
          </div>
          <div className="space-y-2 max-w-md">
            <h2 className="text-2xl font-light text-text-primary">Shop Owner Authentication Required</h2>
            <p className="text-sm text-text-secondary">You must be logged in as an authorized Shop Owner to manage product catalogs and stock levels.</p>
          </div>
          <button
            onClick={() => setIsLoginModalOpen(true)}
            className="px-6 py-3 bg-accent-primary text-bg-base font-medium rounded-xl text-sm hover:opacity-90 transition-opacity cursor-pointer shadow-lg"
          >
            Owner Login (admin / password123)
          </button>
        </div>
      );
    }

    return (
      <ShopManagement
        onTriggerRestock={(product) => {
          submitQuery(`Check inventory stock and generate restock order plan for SKU ${product.sku} (${product.name})`);
        }}
      />
    );
  };

  return (
    <div className="h-screen w-full flex flex-col lg:flex-row bg-bg-base text-text-primary font-sans font-light overflow-hidden relative">
      
      {/* Login Modal */}
      {isLoginModalOpen && (
        <Login
          onLoginSuccess={() => {
            setIsAuthenticated(true);
            setIsLoginModalOpen(false);
          }}
          onCancel={() => setIsLoginModalOpen(false)}
        />
      )}

      {/* LEFT COLUMN: MAIN STAGE */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-border-panel">
        
        {/* Strictly Aligned Header */}
        <header className="h-20 px-6 lg:px-16 flex items-center justify-between shrink-0 border-b border-border-panel">
          <div className="flex items-center gap-16">
            <div className="flex items-center gap-4 cursor-pointer group">
              <div className="w-5 h-5 bg-text-primary flex items-center justify-center group-hover:bg-accent-primary transition-colors rounded-sm">
                <div className="w-1.5 h-1.5 bg-bg-base"></div>
              </div>
              <span className="font-medium tracking-tight text-lg">Orchestrator</span>
            </div>
            
            <nav className="flex overflow-x-auto gap-6 lg:gap-10 text-sm hide-scrollbar">
              {['Dashboard', 'Shipments', 'Risks', 'Agents', 'Shop Portal'].map((tab) => (
                <div key={tab} onClick={() => setActiveTab(tab)} className="relative cursor-pointer group h-20 flex items-center">
                  <span className={`transition-colors ${activeTab === tab ? 'text-text-primary font-medium' : 'text-text-secondary group-hover:text-text-primary'}`}>
                    {tab}
                  </span>
                  {activeTab === tab && (
                    <div className="absolute bottom-0 left-0 w-full h-[2px] bg-text-primary"></div>
                  )}
                </div>
              ))}
            </nav>
          </div>
          
          <div className="flex items-center gap-6 text-text-secondary">
            {!isAuthenticated ? (
              <button
                onClick={() => setIsLoginModalOpen(true)}
                className="px-3.5 py-1.5 bg-accent-primary/10 text-accent-primary border border-accent-primary/20 rounded-lg text-xs font-medium hover:bg-accent-primary hover:text-bg-base transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <Lock size={13} /> Owner Login
              </button>
            ) : (
              <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full text-xs font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Owner: admin</span>
              </div>
            )}

            <button onClick={() => setIsDark(!isDark)} className="hover:text-text-primary transition-colors cursor-pointer">
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <div className="relative ml-2">
              <div 
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="w-8 h-8 bg-border-panel flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity rounded-full overflow-hidden"
              >
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix&backgroundColor=transparent" alt="User" className="w-full h-full opacity-80" />
              </div>
              
              {isProfileOpen && (
                <div className="absolute right-0 mt-3 w-48 bg-bg-panel border border-border-panel rounded-xl shadow-2xl py-2 z-50">
                  <div className="px-4 py-2 border-b border-border-panel mb-1">
                    <p className="text-sm font-medium">{isAuthenticated ? 'Shop Owner (admin)' : 'Logistics Admin'}</p>
                    <p className="text-xs text-text-secondary truncate">{isAuthenticated ? 'admin@shop.local' : 'admin@orchestrator.local'}</p>
                  </div>
                  {isAuthenticated ? (
                    <button 
                      onClick={() => { setIsAuthenticated(false); setIsProfileOpen(false); }} 
                      className="w-full text-left px-4 py-2 text-sm text-accent-critical hover:bg-accent-critical/10 transition-colors flex items-center gap-2"
                    >
                      <LogOut size={14} /> Log Out
                    </button>
                  ) : (
                    <button 
                      onClick={() => { setIsLoginModalOpen(true); setIsProfileOpen(false); }} 
                      className="w-full text-left px-4 py-2 text-sm text-accent-primary hover:bg-accent-primary/10 transition-colors flex items-center gap-2"
                    >
                      <Lock size={14} /> Owner Login
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Content Area - Exact padding match with header */}
        <main className="flex-1 overflow-y-auto px-6 lg:px-16 py-8 lg:py-12">
          {activeTab === "Dashboard" && renderDashboard()}
          {activeTab === "Shipments" && renderShipments()}
          {activeTab === "Risks" && renderRisks()}
          {activeTab === "Agents" && renderAgents()}
          {activeTab === "Shop Portal" && renderShopPortal()}
        </main>
      </div>

      {/* RIGHT COLUMN: CHAT PANEL */}
      <aside className="w-full lg:w-[440px] h-[50vh] lg:h-full flex flex-col shrink-0 bg-bg-base border-t lg:border-t-0 lg:border-l border-border-panel shadow-2xl z-10">
        
        <div className="h-20 px-6 lg:px-8 flex items-center justify-between shrink-0 border-b border-border-panel">
          <span className="text-sm font-medium tracking-tight">CHAT</span>
          <div className="flex items-center gap-2 bg-border-panel/30 p-1 rounded-md">
            <button 
              onClick={() => setOrchestratorMode('single')}
              className={`text-xs px-2.5 py-1 rounded transition-colors cursor-pointer ${orchestratorMode === 'single' ? 'bg-bg-panel shadow-sm text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
            >
              Single Agent
            </button>
            <button 
              onClick={() => setOrchestratorMode('multi')}
              className={`text-xs px-2.5 py-1 rounded transition-colors cursor-pointer ${orchestratorMode === 'multi' ? 'bg-bg-panel shadow-sm text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
            >
              Multi-Agent Supervisor
            </button>
          </div>
        </div>

        {/* Single Agent Selection Dropdown */}
        {orchestratorMode === 'single' && (
          <div className="px-6 lg:px-8 py-3.5 border-b border-border-panel shrink-0 bg-border-panel/5 flex items-center gap-4">
            <span className="text-xs font-medium text-text-secondary uppercase tracking-widest">Select Agent:</span>
            <select 
              value={selectedSingleAgent}
              onChange={(e) => setSelectedSingleAgent(e.target.value)}
              className="bg-bg-panel text-text-primary text-sm p-1.5 rounded border border-border-panel focus:outline-none focus:border-text-primary flex-1 cursor-pointer"
            >
              {AGENTS.map(agent => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Multi-Agent Supervisor Execution Pipeline */}
        {orchestratorMode === "multi" && (
          <div className="px-6 lg:px-8 py-3 border-b border-border-panel bg-border-panel/10 shrink-0">
            <div className="text-[10px] font-medium uppercase tracking-widest text-text-secondary mb-2 flex items-center justify-between">
              <span>Multi-Agent Routing Pipeline</span>
              <span className="text-accent-primary font-mono">{isTyping ? "PROCESSING" : "READY"}</span>
            </div>
            <div className="flex items-center gap-2 overflow-x-auto py-1 hide-scrollbar">
              <div className="flex items-center gap-1 px-2.5 py-1 bg-border-panel/40 border border-border-panel rounded-full text-xs font-medium shrink-0">
                <GitBranch size={12} className="text-accent-primary" />
                <span>Supervisor</span>
              </div>
              <ArrowRight size={12} className="text-text-secondary shrink-0" />
              {AGENTS.map((ag) => {
                const isExecuted = agentState && agentState[ag.id];
                return (
                  <div
                    key={ag.id}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs transition-colors shrink-0 ${
                      isExecuted
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium"
                        : "bg-border-panel/20 text-text-secondary border border-border-panel/30"
                    }`}
                  >
                    <ag.icon size={12} />
                    <span>{ag.name}</span>
                  </div>
                );
              })}
              <ArrowRight size={12} className="text-text-secondary shrink-0" />
              <div className="flex items-center gap-1 px-2.5 py-1 bg-accent-primary/20 text-accent-primary border border-accent-primary/30 rounded-full text-xs font-medium shrink-0">
                <CheckCircle2 size={12} />
                <span>FINISH</span>
              </div>
            </div>
          </div>
        )}

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 lg:px-8 py-6 flex flex-col gap-6 text-sm">
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col justify-end text-text-secondary">
                <div className="space-y-4 w-full">
                  {['Check inventory stock levels & create reorder plan', 'Optimize delivery routes for active orders', 'Analyze demand forecast & trend volatility'].map((action) => (
                    <div key={action} onClick={() => setChatInput(action)} className="flex items-center gap-3 cursor-pointer hover:text-text-primary transition-colors group pb-2 border-b border-transparent hover:border-border-panel">
                      <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity text-text-primary" />
                      <span className="text-sm font-light">{action}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} gap-2`}>
                    <div className="text-[10px] font-medium uppercase tracking-widest text-text-secondary">
                      {msg.role === 'user' ? 'You' : 'CHAT'}
                    </div>
                    <div className={`p-4 max-w-[90%] font-light leading-relaxed border rounded-2xl break-words ${
                      msg.role === 'user' 
                        ? 'border-text-primary bg-text-primary text-bg-base rounded-tr-sm whitespace-pre-wrap' 
                        : (msg.isError ? 'border-accent-critical bg-accent-critical/10 text-accent-critical rounded-tl-sm shadow-sm' : 'border-border-panel bg-border-panel/30 text-text-primary rounded-tl-sm shadow-sm')
                    }`}>
                      {msg.role === 'user' ? (
                        msg.content
                      ) : (
                        <ReactMarkdown 
                          components={{
                            p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
                            ul: ({node, ...props}) => <ul className="list-disc list-inside my-2 space-y-1.5 pl-1" {...props} />,
                            ol: ({node, ...props}) => <ol className="list-decimal list-inside my-2 space-y-1.5 pl-1" {...props} />,
                            li: ({node, ...props}) => <li className="ml-1 leading-snug" {...props} />,
                            strong: ({node, ...props}) => <strong className="font-semibold text-text-primary" {...props} />,
                            h1: ({node, ...props}) => <h1 className="text-base font-semibold mb-2 mt-3" {...props} />,
                            h2: ({node, ...props}) => <h2 className="text-sm font-semibold mb-2 mt-3" {...props} />,
                            h3: ({node, ...props}) => <h3 className="text-xs font-semibold mb-1 mt-2" {...props} />,
                            code: ({node, ...props}) => <code className="bg-border-panel/50 px-1.5 py-0.5 rounded text-xs font-mono text-accent-primary" {...props} />,
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      )}
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex flex-col items-start gap-2">
                    <div className="text-[10px] font-medium uppercase tracking-widest text-text-secondary">CHAT</div>
                    <div className="px-5 py-4 border border-border-panel bg-border-panel/30 rounded-2xl rounded-tl-sm flex items-center gap-2 shadow-sm">
                      <div className="w-1.5 h-1.5 bg-text-secondary rounded-full animate-pulse" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-1.5 h-1.5 bg-text-secondary rounded-full animate-pulse" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-1.5 h-1.5 bg-text-secondary rounded-full animate-pulse" style={{ animationDelay: '300ms' }}></div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </>
            )}
          </div>

          <div className="px-6 lg:px-8 py-5 shrink-0 border-t border-border-panel bg-bg-base">
            <form onSubmit={handleSend} className="relative flex items-center">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder={orchestratorMode === 'multi' ? "Ask CHAT to run a workflow..." : `Talk to ${AGENTS.find(a => a.id === selectedSingleAgent)?.name}...`}
                className="w-full bg-transparent text-sm focus:outline-none placeholder:text-text-placeholder pr-8 border-b border-border-panel focus:border-text-primary transition-colors py-3"
              />
              <button
                type="submit"
                disabled={!chatInput.trim() || isTyping}
                className="absolute right-0 text-text-secondary hover:text-text-primary disabled:opacity-0 transition-colors cursor-pointer"
              >
                <Send size={16} />
              </button>
            </form>
          </div>

        </div>
      </aside>

    </div>
  );
}
