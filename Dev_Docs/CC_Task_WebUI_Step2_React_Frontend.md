# CC Task: Web UI Step 2 — React Frontend

## What this is

A React frontend that connects to the FastAPI backend. Chat with streaming responses, a debug panel showing retrieval details, a conversation list sidebar, and basic system health display.

## Prerequisites

- Web UI Step 1 (Backend API) deployed and verified
- Node.js installed on the Mac. Check with `node --version`. If not installed: `brew install node`
- The backend is running: `python run_server.py`

## Setup — create the Vite project

Run from the project root (`/path/to/Tir`):

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

This creates the `frontend/` directory with a working React + Vite setup.

## Delete generated boilerplate

Remove the files we're replacing:

```bash
cd /path/to/Tir/frontend
rm src/App.css src/App.jsx src/index.css src/assets/react.svg public/vite.svg
```

## Replace `vite.config.js`

Replace the entire file with:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

## Replace `index.html`

Replace the entire file with:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Tír</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

## Replace `src/main.jsx`

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

## Create `src/App.jsx`

```jsx
import { useState, useEffect, useCallback } from 'react'
import Chat from './components/Chat'
import DebugPanel from './components/DebugPanel'
import './styles.css'

function App() {
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [viewingConversation, setViewingConversation] = useState(null)
  const [viewingMessages, setViewingMessages] = useState([])
  const [debugData, setDebugData] = useState(null)
  const [showDebug, setShowDebug] = useState(true)
  const [health, setHealth] = useState(null)
  const [users, setUsers] = useState([])
  const [activeUserId, setActiveUserId] = useState(null)
  const [showDashboard, setShowDashboard] = useState(false)

  // --- Load initial data ---
  useEffect(() => {
    fetchConversations()
    fetchHealth()
    fetchUsers()
    const healthInterval = setInterval(fetchHealth, 30000)
    return () => clearInterval(healthInterval)
  }, [])

  async function fetchConversations() {
    try {
      const resp = await fetch('/api/conversations')
      const data = await resp.json()
      setConversations(data)
    } catch (e) {
      console.error('Failed to fetch conversations:', e)
    }
  }

  async function fetchHealth() {
    try {
      const resp = await fetch('/api/health')
      setHealth(await resp.json())
    } catch (e) {
      console.error('Failed to fetch health:', e)
    }
  }

  async function fetchUsers() {
    try {
      const resp = await fetch('/api/users')
      const data = await resp.json()
      setUsers(data)
      if (data.length > 0) {
        const admin = data.find(u => u.role === 'admin') || data[0]
        setActiveUserId(admin.id)
      }
    } catch (e) {
      console.error('Failed to fetch users:', e)
    }
  }

  function handleNewConversation() {
    setActiveConversationId(null)
    setViewingConversation(null)
    setViewingMessages([])
    setDebugData(null)
  }

  async function handleCloseConversation() {
    if (!activeConversationId) return
    try {
      const resp = await fetch(`/api/conversations/${activeConversationId}/close`, {
        method: 'POST',
      })
      const data = await resp.json()
      console.log('Closed:', data)
      setActiveConversationId(null)
      setDebugData(null)
      fetchConversations()
    } catch (e) {
      console.error('Failed to close conversation:', e)
    }
  }

  async function handleViewConversation(conv) {
    try {
      const resp = await fetch(`/api/conversations/${conv.id}/messages`)
      const messages = await resp.json()
      setViewingConversation(conv)
      setViewingMessages(messages)
      setDebugData(null)
    } catch (e) {
      console.error('Failed to fetch messages:', e)
    }
  }

  function handleBackToChat() {
    setViewingConversation(null)
    setViewingMessages([])
  }

  const handleConversationCreated = useCallback((convId) => {
    setActiveConversationId(convId)
  }, [])

  const handleDebugData = useCallback((data) => {
    setDebugData(data)
  }, [])

  const handleRefresh = useCallback(() => {
    fetchConversations()
    fetchHealth()
  }, [])

  return (
    <div className="app">
      {/* --- Sidebar --- */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Tír</h1>
          {users.length > 1 && (
            <select
              value={activeUserId || ''}
              onChange={e => setActiveUserId(e.target.value)}
              className="user-select"
            >
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="sidebar-actions">
          <button onClick={handleNewConversation} className="btn btn-new">
            New Conversation
          </button>
          {activeConversationId && (
            <button onClick={handleCloseConversation} className="btn btn-close">
              Close Conversation
            </button>
          )}
        </div>

        <div className="conversation-list">
          <h3>Conversations</h3>
          {conversations.length === 0 && (
            <p className="empty-text">No conversations yet</p>
          )}
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`conversation-item ${
                activeConversationId === conv.id ? 'active' : ''
              } ${conv.ended_at ? 'ended' : 'open'}`}
              onClick={() => conv.ended_at
                ? handleViewConversation(conv)
                : setActiveConversationId(conv.id)
              }
            >
              <div className="conv-meta">
                <span className="conv-user">{conv.user_name}</span>
                <span className="conv-date">
                  {new Date(conv.started_at).toLocaleDateString()}
                </span>
              </div>
              <div className="conv-summary">
                {conv.summary || `${conv.message_count} messages`}
              </div>
              {!conv.ended_at && <span className="conv-badge">active</span>}
            </div>
          ))}
        </div>

        {/* --- Health / Dashboard --- */}
        <div className="sidebar-footer">
          <button
            onClick={() => setShowDashboard(!showDashboard)}
            className="btn btn-small"
          >
            {showDashboard ? 'Hide Stats' : 'System Stats'}
          </button>
          {showDashboard && health && (
            <div className="health-stats">
              <div className={`health-item ${health.ollama === 'ok' ? 'ok' : 'err'}`}>
                Ollama: {health.ollama}
              </div>
              <div className="health-item">
                Chunks: {health.chromadb_chunks}
              </div>
              <div className="health-item">
                Conversations: {health.conversations}
              </div>
              <div className="health-item">
                Messages: {health.messages}
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* --- Main content --- */}
      <main className="main-content">
        {viewingConversation ? (
          <div className="conversation-viewer">
            <div className="viewer-header">
              <button onClick={handleBackToChat} className="btn btn-small">
                Back to Chat
              </button>
              <span>
                Conversation with {viewingConversation.user_name} —{' '}
                {new Date(viewingConversation.started_at).toLocaleString()}
              </span>
            </div>
            <div className="messages-container">
              {viewingMessages.map((msg, i) => (
                <div key={i} className={`message message-${msg.role}`}>
                  <div className="message-role">
                    {msg.role === 'user' ? viewingConversation.user_name : 'A'}
                  </div>
                  <div className="message-content">{msg.content}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <Chat
            conversationId={activeConversationId}
            userId={activeUserId}
            onConversationCreated={handleConversationCreated}
            onDebugData={handleDebugData}
            onRefresh={handleRefresh}
          />
        )}
      </main>

      {/* --- Debug panel --- */}
      <div className="debug-toggle" onClick={() => setShowDebug(!showDebug)}>
        {showDebug ? '>' : '<'}
      </div>
      {showDebug && (
        <aside className="debug-panel">
          <DebugPanel data={debugData} />
        </aside>
      )}
    </div>
  )
}

export default App
```

## Create `src/components/Chat.jsx`

Create the `src/components/` directory and add:

```jsx
import { useState, useEffect, useRef } from 'react'

function Chat({ conversationId, userId, onConversationCreated, onDebugData, onRefresh }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Load existing messages when conversationId changes
  useEffect(() => {
    if (conversationId) {
      fetchMessages(conversationId)
    } else {
      setMessages([])
    }
  }, [conversationId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input
  useEffect(() => {
    if (!isStreaming) {
      inputRef.current?.focus()
    }
  }, [isStreaming])

  async function fetchMessages(convId) {
    try {
      const resp = await fetch(`/api/conversations/${convId}/messages`)
      const data = await resp.json()
      setMessages(data.map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      })))
    } catch (e) {
      console.error('Failed to fetch messages:', e)
    }
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || isStreaming) return

    setInput('')
    setIsStreaming(true)

    // Add user message to display immediately
    setMessages(prev => [...prev, { role: 'user', content: text }])

    // Add empty assistant message that will be filled by streaming
    setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          conversation_id: conversationId,
          user_id: userId,
        }),
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.trim()) continue

          try {
            const data = JSON.parse(line)

            if (data.type === 'debug') {
              onDebugData(data)
              if (data.conversation_id && !conversationId) {
                onConversationCreated(data.conversation_id)
              }
            } else if (data.type === 'token') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + data.content,
                }
                return updated
              })
            } else if (data.type === 'done') {
              // Mark streaming complete
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = { ...last, streaming: false }
                return updated
              })
            } else if (data.type === 'error') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = {
                  ...last,
                  content: data.message,
                  streaming: false,
                  error: true,
                }
                return updated
              })
            }
          } catch (parseErr) {
            console.warn('Failed to parse stream line:', line, parseErr)
          }
        }
      }
    } catch (e) {
      console.error('Stream failed:', e)
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        updated[updated.length - 1] = {
          ...last,
          content: `Connection error: ${e.message}`,
          streaming: false,
          error: true,
        }
        return updated
      })
    }

    setIsStreaming(false)
    onRefresh()
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat">
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-chat">
            <p>Start a conversation</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`message message-${msg.role} ${msg.error ? 'message-error' : ''}`}
          >
            <div className="message-role">
              {msg.role === 'user' ? 'You' : 'A'}
            </div>
            <div className="message-content">
              {msg.content}
              {msg.streaming && <span className="cursor">|</span>}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder="Type a message... (Enter to send)"
          rows={1}
        />
        <button onClick={sendMessage} disabled={isStreaming || !input.trim()}>
          {isStreaming ? '...' : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default Chat
```

## Create `src/components/DebugPanel.jsx`

```jsx
function DebugPanel({ data }) {
  if (!data) {
    return (
      <div className="debug-content">
        <h2>Debug</h2>
        <p className="empty-text">Send a message to see retrieval debug info</p>
      </div>
    )
  }

  return (
    <div className="debug-content">
      <h2>Debug</h2>

      <div className="debug-section">
        <h3>Retrieval</h3>
        {data.retrieval_skipped ? (
          <p className="debug-note">Skipped (greeting detected)</p>
        ) : (
          <>
            <p>{data.chunks_retrieved} chunks retrieved</p>
            <p>System prompt: {data.system_prompt_length.toLocaleString()} chars</p>
            <p>History: {data.history_message_count} messages</p>
          </>
        )}
      </div>

      {!data.retrieval_skipped && data.retrieved_chunks.length > 0 && (
        <div className="debug-section">
          <h3>Retrieved Chunks</h3>
          {data.retrieved_chunks.map((chunk, i) => (
            <div key={i} className="debug-chunk">
              <div className="chunk-header">
                <span className="chunk-type">{chunk.source_type}</span>
                <span className="chunk-score">
                  score: {chunk.adjusted_score?.toFixed(4) || 'n/a'}
                </span>
              </div>
              <div className="chunk-signals">
                {chunk.vector_rank != null && (
                  <span className="signal signal-vec">
                    Vec #{chunk.vector_rank}
                    {chunk.vector_distance != null &&
                      ` (d=${chunk.vector_distance.toFixed(3)})`}
                  </span>
                )}
                {chunk.bm25_rank != null && (
                  <span className="signal signal-bm25">
                    BM25 #{chunk.bm25_rank}
                  </span>
                )}
                {chunk.vector_rank != null && chunk.bm25_rank != null && (
                  <span className="signal signal-both">both signals</span>
                )}
              </div>
              <div className="chunk-text">{chunk.text}</div>
            </div>
          ))}
        </div>
      )}

      {data.conversation_id && (
        <div className="debug-section">
          <h3>Context</h3>
          <p className="debug-id">Conv: {data.conversation_id.substring(0, 8)}...</p>
        </div>
      )}
    </div>
  )
}

export default DebugPanel
```

## Create `src/styles.css`

```css
/* --- Reset & Base --- */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
  height: 100vh;
  overflow: hidden;
}

#root {
  height: 100vh;
}

/* --- Layout --- */
.app {
  display: flex;
  height: 100vh;
}

/* --- Sidebar --- */
.sidebar {
  width: 260px;
  background: #16213e;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #2a2a4a;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #2a2a4a;
}

.sidebar-header h1 {
  font-size: 20px;
  color: #7faacc;
  margin-bottom: 8px;
}

.user-select {
  width: 100%;
  padding: 6px 8px;
  background: #1a1a2e;
  color: #e0e0e0;
  border: 1px solid #2a2a4a;
  border-radius: 4px;
  font-size: 13px;
}

.sidebar-actions {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-list h3 {
  font-size: 12px;
  text-transform: uppercase;
  color: #888;
  padding: 8px;
  letter-spacing: 0.5px;
}

.conversation-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  position: relative;
}

.conversation-item:hover {
  background: #1a1a2e;
}

.conversation-item.active {
  background: #2a2a4a;
}

.conversation-item.ended {
  opacity: 0.7;
}

.conv-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}

.conv-user {
  color: #7faacc;
  font-weight: 500;
}

.conv-date {
  color: #666;
}

.conv-summary {
  font-size: 12px;
  color: #999;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  background: #2d6a4f;
  color: #b7e4c7;
  padding: 2px 6px;
  border-radius: 8px;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #2a2a4a;
}

.health-stats {
  margin-top: 8px;
}

.health-item {
  font-size: 12px;
  padding: 3px 0;
  color: #999;
}

.health-item.ok {
  color: #6bcb77;
}

.health-item.err {
  color: #e74c3c;
}

/* --- Main content --- */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* --- Chat --- */
.chat {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #555;
  font-size: 16px;
}

.message {
  margin-bottom: 16px;
  max-width: 800px;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #888;
}

.message-user .message-role {
  color: #7faacc;
}

.message-assistant .message-role {
  color: #6bcb77;
}

.message-content {
  font-size: 15px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.message-error .message-content {
  color: #e74c3c;
}

.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* --- Input area --- */
.input-area {
  padding: 16px 20px;
  border-top: 1px solid #2a2a4a;
  display: flex;
  gap: 10px;
  background: #16213e;
}

.input-area textarea {
  flex: 1;
  padding: 10px 14px;
  background: #1a1a2e;
  color: #e0e0e0;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  font-size: 15px;
  font-family: inherit;
  resize: none;
  outline: none;
}

.input-area textarea:focus {
  border-color: #7faacc;
}

.input-area textarea:disabled {
  opacity: 0.5;
}

.input-area button {
  padding: 10px 20px;
  background: #7faacc;
  color: #1a1a2e;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.input-area button:hover:not(:disabled) {
  background: #99c2dd;
}

.input-area button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* --- Conversation viewer --- */
.conversation-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.viewer-header {
  padding: 12px 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #888;
  background: #16213e;
}

/* --- Debug toggle --- */
.debug-toggle {
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #16213e;
  border-left: 1px solid #2a2a4a;
  border-right: 1px solid #2a2a4a;
  cursor: pointer;
  color: #555;
  font-size: 14px;
  user-select: none;
}

.debug-toggle:hover {
  color: #999;
}

/* --- Debug panel --- */
.debug-panel {
  width: 320px;
  background: #16213e;
  overflow-y: auto;
  border-left: 1px solid #2a2a4a;
}

.debug-content {
  padding: 16px;
}

.debug-content h2 {
  font-size: 16px;
  color: #7faacc;
  margin-bottom: 12px;
}

.debug-content h3 {
  font-size: 13px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.debug-section {
  margin-bottom: 20px;
}

.debug-section p {
  font-size: 13px;
  margin-bottom: 4px;
}

.debug-note {
  color: #888;
  font-style: italic;
}

.debug-id {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}

.debug-chunk {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid #2a2a4a;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 11px;
}

.chunk-type {
  color: #7faacc;
  text-transform: uppercase;
  font-weight: 600;
}

.chunk-score {
  color: #888;
  font-family: monospace;
}

.chunk-signals {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.signal {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}

.signal-vec {
  background: #1a3a2a;
  color: #6bcb77;
}

.signal-bm25 {
  background: #2a2a3e;
  color: #a38cd5;
}

.signal-both {
  background: #2d4a3a;
  color: #99ddaa;
  font-weight: 600;
}

.chunk-text {
  font-size: 12px;
  color: #999;
  line-height: 1.4;
  max-height: 100px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* --- Buttons --- */
.btn {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.btn-new {
  background: #2d6a4f;
  color: #b7e4c7;
}

.btn-new:hover {
  background: #3a7d5f;
}

.btn-close {
  background: #5a2a2a;
  color: #e8a0a0;
}

.btn-close:hover {
  background: #6a3a3a;
}

.btn-small {
  padding: 5px 10px;
  font-size: 12px;
  background: #2a2a4a;
  color: #999;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-small:hover {
  background: #3a3a5a;
}

.empty-text {
  color: #555;
  font-size: 13px;
  padding: 8px;
}

/* --- Scrollbar --- */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #2a2a4a;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #3a3a5a;
}
```

## Verify — dev mode runs

Make sure the backend is running in one terminal:

```bash
cd /path/to/Tir
python run_server.py
```

In a second terminal:

```bash
cd /path/to/Tir/frontend
npm run dev
```

Open `http://localhost:5173` in a browser. You should see:
- Left sidebar with "Tír" header and conversation list
- Center area with "Start a conversation" prompt
- Right panel with "Debug" header

## Verify — send a message

Type a message and press Enter. You should see:
1. Your message appears immediately
2. The assistant's response streams in token by token
3. The debug panel shows retrieval info (chunks retrieved, scores, distances)

## Verify — greeting skip

Type "hello" — debug panel should show "Skipped (greeting detected)".

## Verify — conversation list

After sending messages and closing a conversation (Close Conversation button), the conversation should appear in the sidebar. Clicking it should show the transcript (read-only).

## Verify — system stats

Click "System Stats" in the sidebar footer. Should show Ollama status, chunk count, conversation and message counts.

## Build for production

When ready to serve from FastAPI (no need for Vite dev server):

```bash
cd /path/to/Tir/frontend
npm run build
```

This creates `frontend/dist/`. The FastAPI backend serves these files at `/`. Access at `http://localhost:8000`.

## What NOT to do

- Do NOT modify any Python files — this spec is frontend only
- Do NOT install Tailwind, styled-components, or any CSS framework — plain CSS is intentional
- Do NOT add react-router-dom — single-page state-based navigation is simpler and sufficient
- Do NOT use localStorage — the React state is sufficient for this app (and localStorage is unreliable in some environments)
- Do NOT remove the Vite proxy config — it's required for development mode

## What comes next

The web UI is functional after this step. Future additions:
- Tool call display in debug panel (Phase 3)
- Autonomous session viewer (Phase 4)
- System prompt viewer in debug panel
- Conversation search
