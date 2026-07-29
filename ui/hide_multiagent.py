import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Change default state
content = content.replace(
    'const [orchestratorMode, setOrchestratorMode] = useState("multi");',
    'const [orchestratorMode, setOrchestratorMode] = useState("single");'
)

# Hide Multi Agent button by adding "hidden" to its class or removing it.
old_buttons = """            <button 
              onClick={() => setOrchestratorMode('multi')}
              className={`text-xs px-2 py-1 rounded transition-colors ${orchestratorMode === 'multi' ? 'bg-bg-panel shadow-sm text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
            >
              Multi Agent
            </button>"""

new_buttons = """            {/* <button 
              onClick={() => setOrchestratorMode('multi')}
              className={`text-xs px-2 py-1 rounded transition-colors ${orchestratorMode === 'multi' ? 'bg-bg-panel shadow-sm text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
            >
              Multi Agent
            </button> */}"""

content = content.replace(old_buttons, new_buttons)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated App.jsx to hide multiagent mode")
