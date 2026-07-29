import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make root flex responsive
content = content.replace(
    '<div className="h-screen w-full flex bg-bg-base text-text-primary font-sans font-light overflow-hidden">',
    '<div className="h-screen w-full flex flex-col lg:flex-row bg-bg-base text-text-primary font-sans font-light overflow-hidden">'
)

# Fix aside width
content = content.replace(
    '<aside className="w-[420px] flex flex-col shrink-0 bg-bg-base border-l border-border-panel shadow-2xl z-10">',
    '<aside className="w-full lg:w-[420px] h-[50vh] lg:h-full flex flex-col shrink-0 bg-bg-base border-t lg:border-t-0 lg:border-l border-border-panel shadow-2xl z-10">'
)

# Fix header tabs to allow horizontal scrolling on mobile
content = content.replace(
    '<nav className="hidden md:flex gap-10 text-sm">',
    '<nav className="flex overflow-x-auto gap-6 lg:gap-10 text-sm hide-scrollbar">'
)
content = content.replace(
    '<header className="h-20 px-16 flex items-center justify-between shrink-0 border-b border-border-panel">',
    '<header className="h-20 px-6 lg:px-16 flex items-center justify-between shrink-0 border-b border-border-panel">'
)
content = content.replace(
    '<main className="flex-1 overflow-y-auto px-16 py-12">',
    '<main className="flex-1 overflow-y-auto px-6 lg:px-16 py-8 lg:py-12">'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated App.jsx for responsiveness")
