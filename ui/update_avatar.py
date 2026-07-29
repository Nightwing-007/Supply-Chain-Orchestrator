import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add state
if 'const [isProfileOpen, setIsProfileOpen]' not in content:
    content = content.replace(
        'const [isLoadingDashboard, setIsLoadingDashboard] = useState(true);',
        'const [isLoadingDashboard, setIsLoadingDashboard] = useState(true);\n  const [isProfileOpen, setIsProfileOpen] = useState(false);'
    )

# 2. Add dropdown UI
old_avatar = """<div className="w-8 h-8 bg-border-panel flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity ml-2 rounded-full overflow-hidden">
              <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix&backgroundColor=transparent" alt="User" className="w-full h-full opacity-80" />
            </div>"""

new_avatar = """<div className="relative ml-2">
              <div 
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="w-8 h-8 bg-border-panel flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity rounded-full overflow-hidden"
              >
                <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix&backgroundColor=transparent" alt="User" className="w-full h-full opacity-80" />
              </div>
              
              {isProfileOpen && (
                <div className="absolute right-0 mt-3 w-48 bg-bg-panel border border-border-panel rounded-xl shadow-2xl py-2 z-50">
                  <div className="px-4 py-2 border-b border-border-panel mb-1">
                    <p className="text-sm font-medium">Logistics Admin</p>
                    <p className="text-xs text-text-secondary truncate">admin@orchestrator.local</p>
                  </div>
                  <button className="w-full text-left px-4 py-2 text-sm hover:bg-border-panel/30 transition-colors">Profile Settings</button>
                  <button className="w-full text-left px-4 py-2 text-sm hover:bg-border-panel/30 transition-colors">API Keys</button>
                  <div className="border-t border-border-panel my-1"></div>
                  <button className="w-full text-left px-4 py-2 text-sm text-accent-critical hover:bg-accent-critical/10 transition-colors">Log Out</button>
                </div>
              )}
            </div>"""

content = content.replace(old_avatar, new_avatar)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated App.jsx with profile dropdown")
