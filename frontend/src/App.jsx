import { useState, useEffect, useCallback } from 'react'
import Chat from './components/Chat'
import DebugPanel from './components/DebugPanel'
import './styles.css'

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < breakpoint)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < breakpoint)
    window.addEventListener('resize', handler)
    return () => clearInterval(handler)
  }, [breakpoint])
  return isMobile
}

// iOS Safari viewport height fix
function useViewportHeight() {
  useEffect(() => {
    function setVh() {
      const vh = window.innerHeight * 0.01
      document.documentElement.style.setProperty('--vh', `${vh}px`)
    }
    setVh()
    window.addEventListener('resize', setVh)
    window.addEventListener('orientationchange', setVh)
    return () => {
      window.removeEventListener('resize', setVh)
      window.removeEventListener('orientationchange', setVh)
    }
  }, [])
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
  useViewportHeight()

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

  // --- Sidebar content ---
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

  // --- Main chat/viewer content ---
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
      <div className="app-mobile">
        <div className="m-header">
          <span className="m-title">Tír</span>
          {activeConversationId && (
            <button onClick={handleCloseConversation} className="btn btn-small">
              Close
            </button>
          )}
          <button onClick={handleNewConversation} className="btn btn-small">
            New
          </button>
        </div>
        <div className="m-body">
          {activeTab === 'chat' && mainContent}
          {activeTab === 'conversations' && (
            <div className="m-scroll">{sidebarContent}</div>
          )}
          {activeTab === 'debug' && (
            <div className="m-scroll"><DebugPanel data={debugData} /></div>
          )}
        </div>
        <div className="m-tabs">
          <button
            className={`m-tab ${activeTab === 'conversations' ? 'active' : ''}`}
            onClick={() => setActiveTab('conversations')}
          >Convos</button>
          <button
            className={`m-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >Chat</button>
          <button
            className={`m-tab ${activeTab === 'debug' ? 'active' : ''}`}
            onClick={() => setActiveTab('debug')}
          >Debug</button>
        </div>
      </div>
    )
  }

  // --- Desktop layout ---
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