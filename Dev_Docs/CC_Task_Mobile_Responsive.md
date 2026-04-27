# CC Task: Mobile Responsive Layout

## What this is

Make the web UI work on iPhone. On screens narrower than 768px, the three-column layout collapses to a single panel with a tab bar at the bottom to switch between Chat, Conversations, and Debug.

## Files to modify

- `frontend/src/App.jsx` — add mobile detection and tab state
- `frontend/src/styles.css` — add media queries and tab bar styles

## Changes to `frontend/src/App.jsx`

Add a `activeTab` state and a mobile detection hook. Replace the return JSX to conditionally render based on screen width.

Replace the entire `App.jsx` with:

```jsx
import { useState, useEffect, useCallback } from 'react'
import Chat from './components/Chat'
import DebugPanel from './components/DebugPanel'
import './styles.css'

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < breakpoint)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < breakpoint)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [breakpoint])
  return isMobile
}

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
  const [activeTab, setActiveTab] = useState('chat')
  const isMobile = useIsMobile()

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
    if (isMobile) setActiveTab('chat')
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
      if (isMobile) setActiveTab('chat')
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

  // --- Sidebar content (shared between desktop sidebar and mobile tab) ---
  const sidebarContent = (
    <>
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
    </>
  )

  // --- Main chat/viewer content (shared) ---
  const mainContent = viewingConversation ? (
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
  )

  // --- Mobile layout ---
  if (isMobile) {
    return (
      <div className="app mobile">
        <div className="mobile-content">
          {activeTab === 'chat' && (
            <main className="main-content">{mainContent}</main>
          )}
          {activeTab === 'conversations' && (
            <aside className="sidebar mobile-sidebar">{sidebarContent}</aside>
          )}
          {activeTab === 'debug' && (
            <aside className="debug-panel mobile-debug">
              <DebugPanel data={debugData} />
            </aside>
          )}
        </div>
        <nav className="tab-bar">
          <button
            className={`tab-btn ${activeTab === 'conversations' ? 'active' : ''}`}
            onClick={() => setActiveTab('conversations')}
          >
            Convos
          </button>
          <button
            className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            Chat
          </button>
          <button
            className={`tab-btn ${activeTab === 'debug' ? 'active' : ''}`}
            onClick={() => setActiveTab('debug')}
          >
            Debug
          </button>
        </nav>
      </div>
    )
  }

  // --- Desktop layout (unchanged) ---
  return (
    <div className="app">
      <aside className="sidebar">{sidebarContent}</aside>
      <main className="main-content">{mainContent}</main>
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

## Changes to `frontend/src/styles.css`

Add the following at the end of the existing CSS file:

```css
/* --- Mobile layout --- */
@media (max-width: 767px) {
  .app.mobile {
    flex-direction: column;
  }

  .mobile-content {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .mobile-content > * {
    flex: 1;
    width: 100%;
    height: 100%;
  }

  .mobile-sidebar {
    width: 100%;
    border-right: none;
    overflow-y: auto;
  }

  .mobile-debug {
    width: 100%;
    border-left: none;
    overflow-y: auto;
  }

  .tab-bar {
    display: flex;
    border-top: 1px solid #2a2a4a;
    background: #16213e;
    flex-shrink: 0;
  }

  .tab-btn {
    flex: 1;
    padding: 12px 0;
    background: transparent;
    color: #888;
    border: none;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }

  .tab-btn.active {
    color: #7faacc;
    border-top: 2px solid #7faacc;
  }

  .tab-btn:hover {
    color: #999;
  }

  .input-area {
    padding: 10px 12px;
  }

  .input-area textarea {
    font-size: 16px; /* Prevents iOS zoom on focus */
  }

  .messages-container {
    padding: 12px;
  }

  .message {
    max-width: 100%;
  }

  .debug-toggle {
    display: none;
  }
}
```

## Verify — desktop unchanged

Open `http://localhost:5173` (or :8000) on desktop. Layout should look exactly the same as before — three columns, sidebar, chat, debug panel.

## Verify — mobile layout

Open the same URL on iPhone (make sure your phone and Mac are on the same network — use `http://<mac-ip>:5173` or `http://<mac-ip>:8000`). You should see:

- Chat fills the screen
- Tab bar at the bottom with Convos / Chat / Debug
- Tapping Convos shows the conversation list (full screen)
- Tapping Debug shows the debug panel (full screen)
- Tapping Chat returns to the chat
- Text input doesn't trigger iOS zoom (16px font size)

You can also test in Chrome DevTools — toggle device toolbar (Cmd+Shift+M) and pick an iPhone.

## What NOT to do

- Do NOT modify Chat.jsx or DebugPanel.jsx — they work as-is in both layouts
- Do NOT add a CSS framework — media queries are sufficient
- Do NOT change the desktop layout behavior
- Do NOT add swipe gestures — tap is simpler and more reliable

## What comes next

This is a standalone fix. Continue with Phase 3 Step 1 (Skill Registry).
