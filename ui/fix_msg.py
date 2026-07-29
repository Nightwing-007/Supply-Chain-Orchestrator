import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the specific line in handleSend
old_line = "content: response.final_response || response.message || \"Execution completed successfully.\""
new_line = "content: response.final_answer || response.final_response || response.message || \"Execution completed successfully.\""

if old_line in content:
    content = content.replace(old_line, new_line)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed App.jsx")
else:
    print("Line not found in App.jsx")
