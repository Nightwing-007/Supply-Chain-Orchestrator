import os

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the specific line in handleSend again to be smarter
old_line = "content: response.final_answer || response.final_response || response.message || \"Execution completed successfully.\""
new_line = """
content: (function() {
  if (response.final_answer && !response.final_answer.startsWith("Standalone Single Agent")) return response.final_answer;
  if (response.state && response.state[selectedSingleAgent]) {
     const st = response.state[selectedSingleAgent];
     if (st._adjustment_plan && st._adjustment_plan.summary) return st._adjustment_plan.summary;
     if (st.analysis) return st.analysis;
     if (st.message) return st.message;
  }
  return response.final_answer || response.final_response || "Execution completed successfully.";
})()
""".strip()

if old_line in content:
    content = content.replace(old_line, new_line)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed App.jsx with smart response parsing")
else:
    print("Line not found in App.jsx")
