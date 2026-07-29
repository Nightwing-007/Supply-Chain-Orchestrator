import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the buttons in the dropdown
old_buttons = """                  <button className="w-full text-left px-4 py-2 text-sm hover:bg-border-panel/30 transition-colors">Profile Settings</button>
                  <button className="w-full text-left px-4 py-2 text-sm hover:bg-border-panel/30 transition-colors">API Keys</button>
                  <div className="border-t border-border-panel my-1"></div>
                  <button className="w-full text-left px-4 py-2 text-sm text-accent-critical hover:bg-accent-critical/10 transition-colors">Log Out</button>"""

new_buttons = """                  <button onClick={() => { alert('Profile Settings feature coming soon!'); setIsProfileOpen(false); }} className="w-full text-left px-4 py-2 text-sm hover:bg-border-panel/30 transition-colors">Profile Settings</button>
                  <button onClick={() => { alert('API Keys feature coming soon!'); setIsProfileOpen(false); }} className="w-full text-left px-4 py-2 text-sm hover:bg-border-panel/30 transition-colors">API Keys</button>
                  <div className="border-t border-border-panel my-1"></div>
                  <button onClick={() => { alert('User authentication not yet implemented.'); setIsProfileOpen(false); }} className="w-full text-left px-4 py-2 text-sm text-accent-critical hover:bg-accent-critical/10 transition-colors">Log Out</button>"""

content = content.replace(old_buttons, new_buttons)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated App.jsx with onClick handlers for dropdown")
