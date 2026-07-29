import { useState, useEffect, useRef } from "react";
import { Search, Moon, Sun, ArrowRight, MessageSquare, Send, AlertTriangle, Package, Activity } from "lucide-react";

export default function App() {
  const [isDark, setIsDark] = useState(true);
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef(null);

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) root.classList.add("dark");
    else root.classList.remove("dark");
  }, [isDark]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = async (e) => {
    e.preventDefault();
    const query = chatInput.trim();
    if (!query) return;
    
    setMessages(prev => [...prev, { role: 'user', content: query }]);
    setChatInput('');
    setIsTyping(true);

    try {
      const response = await fetch('http://localhost:8000/api/workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      });
      
      const data = await response.json();
      
      if (response.ok && data.final_answer) {
        setMessages(prev => [...prev, { role: 'bot', content: data.final_answer }]);
      } else if (response.ok) {
        setMessages(prev => [...prev, { role: 'bot', content: "Workflow executed successfully, but no final answer was provided." }]);
      } else {
        setMessages(prev => [...prev, { role: 'bot', content: `Error: ${data.detail || 'Failed to process request'}` }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'bot', content: `Connection error: ${error.message}` }]);
    } finally {
      setIsTyping(false);
    }
  };

  const renderDashboard = () => (
    <>
      <header className="mb-16">
        <h1 className="text-4xl font-light tracking-tight mb-2">Live Telemetry</h1>
        <p className="text-text-secondary">Monitoring global supply chain metrics.</p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-16 gap-y-16">
        <section className="xl:col-span-2">
          <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
            <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Route Tracking</h2>
            <span className="text-xs font-mono text-text-secondary">AWAITING_DATA</span>
          </div>
          <div className="h-[400px] w-full flex flex-col items-center justify-center text-text-secondary bg-border-panel/30">
            <span className="text-sm">Map Visualization Slot</span>
          </div>
        </section>

        <section>
          <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
            <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Performance</h2>
            <span className="text-xs text-text-secondary">Last 7 Days</span>
          </div>
          <div className="h-48 w-full flex items-end gap-[2px] bg-border-panel/10 p-4">
            {[40, 60, 45, 80, 50, 90, 75].map((h, i) => (
              <div key={i} className="flex-1 bg-border-panel hover:bg-text-primary transition-colors" style={{ height: `${h}%` }} />
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-end justify-between mb-4 border-b border-border-panel pb-3">
            <h2 className="text-sm font-medium tracking-wide text-text-secondary uppercase">Flow Graph</h2>
            <button className="text-xs text-text-primary hover:underline uppercase tracking-wider font-medium">Interact</button>
          </div>
          <div className="h-48 w-full flex flex-col items-center justify-center text-text-secondary bg-border-panel/30">
            <span className="text-sm">Node-Link Graph Slot</span>
          </div>
        </section>
      </div>
    </>
  );

  const renderShipments = () => (
    <>
      <header className="mb-16">
        <h1 className="text-4xl font-light tracking-tight mb-2">Active Shipments</h1>
        <p className="text-text-secondary">Tracking 1,284 ongoing freight movements.</p>
      </header>

      <div className="w-full">
        <div className="grid grid-cols-5 border-b border-border-panel pb-4 mb-4 text-xs font-medium tracking-widest text-text-secondary uppercase">
          <div className="col-span-2">Shipment ID</div>
          <div>Origin</div>
          <div>Destination</div>
          <div className="text-right">Status</div>
        </div>
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((item) => (
            <div key={item} className="grid grid-cols-5 items-center border-b border-border-panel/50 pb-4 pt-2 text-sm">
              <div className="col-span-2 flex items-center gap-3">
                <Package size={16} className="text-text-secondary" />
                <span className="font-mono">SHP-293{item}4X</span>
              </div>
              <div className="text-text-secondary">Shanghai, CN</div>
              <div className="text-text-secondary">Rotterdam, NL</div>
              <div className="text-right flex items-center justify-end gap-2 text-accent-primary">
                <Activity size={14} />
                <span>In Transit</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );

  const renderRisks = () => (
    <>
      <header className="mb-16">
        <h1 className="text-4xl font-light tracking-tight mb-2">Risk Intel</h1>
        <p className="text-text-secondary">Automated vulnerability and disruption tracking.</p>
      </header>

      <div className="space-y-6">
        {[
          { level: 'Critical', text: 'Port Congestion at Long Beach expected to delay 4 inbound vessels by 72h.', icon: AlertTriangle, color: 'text-accent-critical', bg: 'bg-accent-critical/10', border: 'border-accent-critical/20' },
          { level: 'Warning', text: 'Typhoon approaching South China Sea, potential rerouting for 12 shipments.', icon: AlertTriangle, color: 'text-accent-warning', bg: 'bg-accent-warning/10', border: 'border-accent-warning/20' }
        ].map((risk, i) => (
          <div key={i} className={`p-6 border ${risk.border} ${risk.bg} flex items-start gap-4`}>
            <risk.icon size={20} className={risk.color} />
            <div>
              <h3 className={`text-sm font-medium uppercase tracking-wider mb-2 ${risk.color}`}>{risk.level}</h3>
              <p className="text-sm font-light leading-relaxed">{risk.text}</p>
              <div className="mt-4 flex gap-4">
                <button className={`text-xs uppercase tracking-widest font-medium ${risk.color} hover:opacity-70 transition-opacity`}>Mitigate</button>
                <button className="text-xs uppercase tracking-widest font-medium text-text-secondary hover:text-text-primary transition-colors">Details</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );

  return (
    <div className="h-screen w-full flex bg-bg-base text-text-primary font-sans font-light overflow-hidden">
      
      {/* LEFT COLUMN: MAIN STAGE */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-border-panel">
        
        {/* Strictly Aligned Header */}
        <header className="h-20 px-16 flex items-center justify-between shrink-0 border-b border-border-panel">
          <div className="flex items-center gap-16">
            <div className="flex items-center gap-4 cursor-pointer group">
              <div className="w-5 h-5 bg-text-primary flex items-center justify-center group-hover:bg-accent-primary transition-colors">
                <div className="w-1.5 h-1.5 bg-bg-base"></div>
              </div>
              <span className="font-medium tracking-tight text-lg">Orchestrator</span>
            </div>
            
            <nav className="hidden md:flex gap-10 text-sm">
              {['Dashboard', 'Shipments', 'Risks'].map((tab) => (
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
          
          <div className="flex items-center gap-8 text-text-secondary">
            <div className="hidden sm:flex items-center gap-3 cursor-pointer hover:text-text-primary transition-colors">
              <Search size={16} />
              <span className="text-sm">Search</span>
              <span className="text-xs font-mono opacity-50">⌘K</span>
            </div>
            <button onClick={() => setIsDark(!isDark)} className="hover:text-text-primary transition-colors cursor-pointer">
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <div className="w-8 h-8 bg-border-panel flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity ml-2">
              <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix&backgroundColor=transparent" alt="User" className="w-full h-full opacity-80" />
            </div>
          </div>
        </header>

        {/* Content Area - Exact padding match with header */}
        <main className="flex-1 overflow-y-auto px-16 py-12">
          {activeTab === "Dashboard" && renderDashboard()}
          {activeTab === "Shipments" && renderShipments()}
          {activeTab === "Risks" && renderRisks()}
        </main>
      </div>

      {/* RIGHT COLUMN: COPILOT - Fixed width, strictly aligned padding */}
      <aside className="w-[420px] flex flex-col shrink-0 bg-bg-base">
        
        <div className="h-20 px-10 flex items-center shrink-0 border-b border-border-panel">
          <span className="text-sm font-medium tracking-tight">Copilot</span>
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          
          <div className="px-10 py-8 border-b border-border-panel shrink-0 bg-border-panel/10">
            <h3 className="text-xs font-medium text-text-secondary uppercase tracking-widest mb-8">Risk Summary</h3>
            <div className="grid grid-cols-2 gap-8">
              <div>
                <div className="text-4xl font-light text-accent-critical mb-2">--</div>
                <div className="text-xs text-text-secondary uppercase tracking-wider">Critical</div>
              </div>
              <div>
                <div className="text-4xl font-light text-accent-warning mb-2">--</div>
                <div className="text-xs text-text-secondary uppercase tracking-wider">Warnings</div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-10 py-8 flex flex-col gap-6 text-sm">
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col justify-end text-text-secondary">
                <div className="space-y-5 w-full">
                  {['Analyze performance', 'Identify bottlenecks', 'Show critical alerts'].map((action) => (
                    <div key={action} onClick={() => setChatInput(action)} className="flex items-center gap-4 cursor-pointer hover:text-text-primary transition-colors group pb-2 border-b border-transparent hover:border-border-panel">
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
                      {msg.role === 'user' ? 'You' : 'Copilot'}
                    </div>
                    <div className={`p-4 max-w-[90%] font-light leading-relaxed border ${
                      msg.role === 'user' 
                        ? 'border-text-primary bg-text-primary text-bg-base' 
                        : 'border-border-panel bg-border-panel/30 text-text-primary'
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex flex-col items-start gap-2">
                    <div className="text-[10px] font-medium uppercase tracking-widest text-text-secondary">Copilot</div>
                    <div className="px-5 py-4 border border-border-panel bg-border-panel/30 flex items-center gap-2">
                      <div className="w-1 h-1 bg-text-secondary animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-1 h-1 bg-text-secondary animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-1 h-1 bg-text-secondary animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </>
            )}
          </div>

          <div className="px-10 py-6 shrink-0 border-t border-border-panel">
            <form onSubmit={handleSend} className="relative flex items-center">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask Copilot..."
                className="w-full bg-transparent text-sm focus:outline-none placeholder:text-text-placeholder pr-8 border-b border-border-panel focus:border-text-primary transition-colors py-3"
              />
              <button
                type="submit"
                disabled={!chatInput.trim()}
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
