import React, { useState, useEffect, useRef } from 'react';
import { Send, Check, AlertCircle, Bot, User, Layers } from 'lucide-react';
import './App.css';

const API_BASE = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello! I am your Constructor Agent. How can I help you modify the workflow today?" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [workflows, setWorkflows] = useState([]);
  const [pendingEdits, setPendingEdits] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const fetchWorkflows = async () => {
    try {
      const res = await fetch(`${API_BASE}/workflows`);
      const data = await res.json();
      setWorkflows(data);
    } catch (err) {
      console.error("Failed to fetch workflows", err);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input })
      });
      const data = await res.json();

      if (data.clarification) {
        setMessages(prev => [...prev, { role: 'assistant', content: data.clarification }]);
      } else if (data.explanation) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.explanation,
          edits: data.edits
        }]);
        if (data.edits) {
          setPendingEdits(data.edits);
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error. Please check if the backend is running." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (edits) => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edits })
      });
      const data = await res.json();

      if (data.success) {
        setMessages(prev => [...prev, { role: 'assistant', content: "Changes applied successfully and validated! ✅" }]);
        setPendingEdits(null);
        fetchWorkflows();
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Validation failed: ${data.errors.join(', ')}. I might need to try again or you can clarify.`,
          isError: true
        }]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <h2><Layers size={20} style={{ marginRight: '8px' }} /> Workflows</h2>
        <div className="workflow-list">
          {workflows.map((wf, idx) => (
            <div key={idx} className="workflow-item">{wf}</div>
          ))}
        </div>
      </div>

      <div className="main-chat">
        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '4px', opacity: 0.6, fontSize: '0.8rem' }}>
                {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
                <span>{msg.role === 'user' ? 'You' : 'Constructor Agent'}</span>
              </div>
              <div>{msg.content}</div>
              {msg.edits && (
                <div className="proposed-changes">
                  <div style={{ fontSize: '0.85rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>Proposed Edits:</div>
                  <ul style={{ fontSize: '0.8rem', paddingLeft: '1.2rem', margin: '0.5rem 0' }}>
                    {msg.edits.map((e, i) => <li key={i}>{e.name}</li>)}
                  </ul>
                  <button className="approve-btn" onClick={() => handleApprove(msg.edits)}>
                    Approve and Apply
                  </button>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="message assistant">
              <div className="loading-dots">
                <div className="dot"></div>
                <div className="dot"></div>
                <div className="dot"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <input
            className="chat-input"
            placeholder="Type your instruction (e.g., 'If age > 18, use adult_registration tool')"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          />
          <button className="send-btn" onClick={handleSend}>
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
