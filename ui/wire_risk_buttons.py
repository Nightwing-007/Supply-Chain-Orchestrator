import os
import re

file_path = r'f:\agentverse\Supply-Chain-Orchestrator\ui\src\App.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Refactor handleSend into submitQuery and handleSend
old_handle_send = """  const handleSend = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    
    const query = chatInput.trim();
    setMessages(prev => [...prev, { role: 'user', content: query }]);
    setChatInput('');
    setIsTyping(true);"""

new_handle_send = """  const submitQuery = async (queryText) => {
    if (!queryText.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content: queryText }]);
    setIsTyping(true);
    // ensure sidebar is visible if on mobile
    if (window.innerWidth < 1024) {
      document.querySelector('aside')?.scrollIntoView({ behavior: 'smooth' });
    }"""

content = content.replace(old_handle_send, new_handle_send)

# Replace 'query' with 'queryText' in the try block
content = content.replace("response = await runWorkflow(query);", "response = await runWorkflow(queryText);")
content = content.replace("response = await runSingleAgent(selectedSingleAgent, query, agentState || {});", "response = await runSingleAgent(selectedSingleAgent, queryText, agentState || {});")

# Add back handleSend
old_catch_end = """    } finally {
      setIsTyping(false);
    }
  };"""

new_catch_end = """    } finally {
      setIsTyping(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const text = chatInput;
    setChatInput('');
    await submitQuery(text);
  };"""

content = content.replace(old_catch_end, new_catch_end)


# 2. Wire up the mitigate button
old_mitigate = """                <button className={`text-xs uppercase tracking-widest font-medium hover:opacity-70 transition-opacity ${
                  risk.level === 'Critical' ? 'text-accent-critical' : 'text-accent-warning'
                }`}>Mitigate</button>"""
new_mitigate = """                <button onClick={() => submitQuery(`Create a mitigation plan for the following risk: ${risk.text}`)} className={`text-xs uppercase tracking-widest font-medium hover:opacity-70 transition-opacity ${
                  risk.level === 'Critical' ? 'text-accent-critical' : 'text-accent-warning'
                }`}>Mitigate</button>"""
content = content.replace(old_mitigate, new_mitigate)


# 3. Wire up the details button
old_details = """                <button className="text-xs uppercase tracking-widest font-medium text-text-secondary hover:text-text-primary transition-colors">Details</button>"""
new_details = """                <button onClick={() => submitQuery(`Provide more details and analysis for the following risk: ${risk.text}`)} className="text-xs uppercase tracking-widest font-medium text-text-secondary hover:text-text-primary transition-colors">Details</button>"""
content = content.replace(old_details, new_details)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Wired up risk buttons to chat API")
