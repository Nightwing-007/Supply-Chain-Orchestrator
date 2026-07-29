import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace sidebar header
content = content.replace(
    '<span className="text-sm font-medium tracking-tight">Gemini</span>',
    '<span className="text-sm font-medium tracking-tight">CHAT</span>'
)

# Replace message role label
content = content.replace(
    "{msg.role === 'user' ? 'You' : 'Gemini'}",
    "{msg.role === 'user' ? 'You' : 'CHAT'}"
)

# Replace typing indicator label
content = content.replace(
    '<div className="text-[10px] font-medium uppercase tracking-widest text-text-secondary">Gemini</div>',
    '<div className="text-[10px] font-medium uppercase tracking-widest text-text-secondary">CHAT</div>'
)

# Replace input placeholder
content = content.replace(
    'placeholder={orchestratorMode === \'multi\' ? "Ask Gemini to run a workflow..." : `Talk to ${AGENTS.find(a => a.id === selectedSingleAgent)?.name}...`}',
    'placeholder={orchestratorMode === \'multi\' ? "Ask CHAT to run a workflow..." : `Talk to ${AGENTS.find(a => a.id === selectedSingleAgent)?.name}...`}'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced Gemini with CHAT in App.jsx")
