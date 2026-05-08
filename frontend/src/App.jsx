import { useState, useEffect, useCallback, useRef } from 'react'
import Chat from './components/Chat'
import DebugPanel from './components/DebugPanel'
import RegistryPanel from './components/RegistryPanel'
import SystemPanel from './components/SystemPanel'
import './styles.css'

const DEFAULT_REVIEW_FILTERS = {
  status: '',
  category: '',
  priority: '',
}

const DEFAULT_BEHAVIORAL_GUIDANCE_FILTERS = {
  status: '',
  proposalType: '',
}

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < breakpoint)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < breakpoint)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
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
  const [rightPanelView, setRightPanelView] = useState('debug')
  const [artifacts, setArtifacts] = useState([])
  const [openLoops, setOpenLoops] = useState([])
  const [registryLoading, setRegistryLoading] = useState(false)
  const [registryError, setRegistryError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [systemHealth, setSystemHealth] = useState(null)
  const [systemMemory, setSystemMemory] = useState(null)
  const [systemCapabilities, setSystemCapabilities] = useState(null)
  const [systemLoading, setSystemLoading] = useState(false)
  const [systemError, setSystemError] = useState(null)
  const [systemLoaded, setSystemLoaded] = useState(false)
  const [reviewItems, setReviewItems] = useState([])
  const [reviewFilters, setReviewFilters] = useState(DEFAULT_REVIEW_FILTERS)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState(null)
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [reviewUpdatingId, setReviewUpdatingId] = useState(null)
  const [behavioralGuidanceProposals, setBehavioralGuidanceProposals] = useState([])
  const [behavioralGuidanceFilters, setBehavioralGuidanceFilters] = useState(
    DEFAULT_BEHAVIORAL_GUIDANCE_FILTERS
  )
  const [behavioralGuidanceLoading, setBehavioralGuidanceLoading] = useState(false)
  const [behavioralGuidanceError, setBehavioralGuidanceError] = useState(null)
  const [behavioralGuidanceUpdatingId, setBehavioralGuidanceUpdatingId] = useState(null)
  const healthWarnedRef = useRef(false)
  const isMobile = useIsMobile()
  useViewportHeight()

  async function readErrorMessage(resp, fallback) {
    const fallbackMessage = fallback || `HTTP ${resp.status} ${resp.statusText}`.trim()
    try {
      const contentType = resp.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const data = await resp.json()
        const message = data?.detail || data?.message || data?.error
        return typeof message === 'string' ? message : JSON.stringify(message || data)
      }

      const text = await resp.text()
      return text.trim() || fallbackMessage
    } catch {
      return fallbackMessage
    }
  }

  useEffect(() => {
    fetchConversations()
    fetchHealth()
    fetchUsers()
    fetchRegistries()
    const healthInterval = setInterval(fetchHealth, 30000)
    return () => clearInterval(healthInterval)
  }, [])

  async function fetchConversations() {
    try {
      const resp = await fetch('/api/conversations')
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to fetch conversations'))
      }

      const data = await resp.json()
      if (!Array.isArray(data)) {
        throw new Error('Conversations response was not a list')
      }

      setConversations(data)
    } catch (e) {
      console.error('Failed to fetch conversations:', e)
    }
  }

  async function fetchHealth() {
    try {
      const resp = await fetch('/api/health')
      setHealth(await resp.json())
      healthWarnedRef.current = false
    } catch (e) {
      setHealth({
        backend: 'unreachable',
        ollama: 'unreachable',
        chromadb_chunks: -1,
        conversations: -1,
        messages: -1,
      })
      if (!healthWarnedRef.current) {
        console.warn('Backend health check failed:', e)
        healthWarnedRef.current = true
      }
    }
  }

  async function fetchUsers() {
    try {
      const resp = await fetch('/api/users')
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to fetch users'))
      }

      const data = await resp.json()
      if (!Array.isArray(data)) {
        throw new Error('Users response was not a list')
      }

      setUsers(data)
      if (data.length > 0) {
        const admin = data.find(u => u.role === 'admin') || data[0]
        setActiveUserId(admin.id)
      }
    } catch (e) {
      console.error('Failed to fetch users:', e)
    }
  }

  async function fetchRegistries() {
    setRegistryLoading(true)
    setRegistryError(null)
    try {
      const [artifactResp, openLoopResp] = await Promise.all([
        fetch('/api/artifacts'),
        fetch('/api/open-loops'),
      ])

      if (!artifactResp.ok) {
        throw new Error(await readErrorMessage(artifactResp, 'Failed to fetch artifacts'))
      }
      if (!openLoopResp.ok) {
        throw new Error(await readErrorMessage(openLoopResp, 'Failed to fetch open loops'))
      }

      const artifactData = await artifactResp.json()
      const openLoopData = await openLoopResp.json()
      if (!Array.isArray(artifactData)) {
        throw new Error('Artifacts response was not a list')
      }
      if (!Array.isArray(openLoopData)) {
        throw new Error('Open loops response was not a list')
      }

      setArtifacts(artifactData)
      setOpenLoops(openLoopData)
    } catch (e) {
      console.warn('Failed to fetch registry records:', e)
      setRegistryError(e.message || 'Failed to fetch registry records')
    } finally {
      setRegistryLoading(false)
    }
  }

  async function uploadArtifact(form) {
    setUploading(true)
    setUploadError(null)
    setUploadResult(null)
    try {
      const body = new FormData()
      body.append('file', form.file)
      if (activeUserId) body.append('user_id', activeUserId)
      if (form.title?.trim()) body.append('title', form.title.trim())
      if (form.description?.trim()) body.append('description', form.description.trim())
      if (form.revisionOf?.trim()) body.append('revision_of', form.revisionOf.trim())

      const resp = await fetch('/api/artifacts/upload', {
        method: 'POST',
        body,
      })
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Artifact upload failed'))
      }

      const data = await resp.json()
      if (!data || typeof data !== 'object' || data.ok !== true) {
        throw new Error(data?.error || 'Artifact upload returned an invalid response')
      }

      setUploadResult(data)
      await fetchRegistries()
      return data
    } catch (e) {
      const message = e.message || 'Artifact upload failed'
      setUploadError(message)
      throw e
    } finally {
      setUploading(false)
    }
  }

  async function fetchSystemStatus() {
    setSystemLoading(true)
    setSystemError(null)
    const reviewPromise = fetchReviewItems()
    const behavioralGuidancePromise = fetchBehavioralGuidanceProposals()
    try {
      const [healthResp, memoryResp, capabilitiesResp] = await Promise.all([
        fetch('/api/system/health'),
        fetch('/api/system/memory'),
        fetch('/api/system/capabilities'),
      ])

      if (!healthResp.ok) {
        throw new Error(await readErrorMessage(healthResp, 'Failed to fetch system health'))
      }
      if (!memoryResp.ok) {
        throw new Error(await readErrorMessage(memoryResp, 'Failed to fetch memory status'))
      }
      if (!capabilitiesResp.ok) {
        throw new Error(
          await readErrorMessage(capabilitiesResp, 'Failed to fetch capability status')
        )
      }

      const healthData = await healthResp.json()
      const memoryData = await memoryResp.json()
      const capabilitiesData = await capabilitiesResp.json()
      if (!healthData || typeof healthData !== 'object' || Array.isArray(healthData)) {
        throw new Error('System health response was not an object')
      }
      if (!memoryData || typeof memoryData !== 'object' || Array.isArray(memoryData)) {
        throw new Error('Memory status response was not an object')
      }
      if (
        !capabilitiesData ||
        typeof capabilitiesData !== 'object' ||
        Array.isArray(capabilitiesData)
      ) {
        throw new Error('Capability status response was not an object')
      }

      setSystemHealth(healthData)
      setSystemMemory(memoryData)
      setSystemCapabilities(capabilitiesData)
      setSystemLoaded(true)
    } catch (e) {
      console.warn('Failed to fetch system status:', e)
      setSystemError(e.message || 'Failed to fetch system status')
    } finally {
      await reviewPromise
      await behavioralGuidancePromise
      setSystemLoading(false)
    }
  }

  async function fetchReviewItems(filters = reviewFilters) {
    setReviewLoading(true)
    setReviewError(null)
    try {
      const params = new URLSearchParams()
      if (filters.status) params.set('status', filters.status)
      if (filters.category) params.set('category', filters.category)
      if (filters.priority) params.set('priority', filters.priority)
      params.set('limit', '50')

      const query = params.toString()
      const resp = await fetch(`/api/review${query ? `?${query}` : ''}`)
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to fetch review queue'))
      }

      const data = await resp.json()
      if (!data || typeof data !== 'object' || !Array.isArray(data.items)) {
        throw new Error('Review queue response was not a valid item list')
      }

      setReviewItems(data.items)
      return data.items
    } catch (e) {
      console.warn('Failed to fetch review queue:', e)
      setReviewError(e.message || 'Failed to fetch review queue')
      return []
    } finally {
      setReviewLoading(false)
    }
  }

  function updateReviewFilters(nextFilters) {
    setReviewFilters(nextFilters)
    fetchReviewItems(nextFilters)
  }

  async function createReviewItem(form) {
    setReviewSubmitting(true)
    setReviewError(null)
    try {
      const payload = {
        title: form.title,
        description: form.description || null,
        category: form.category || 'other',
        priority: form.priority || 'normal',
        created_by: 'operator',
      }

      const resp = await fetch('/api/review', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to create review item'))
      }

      const data = await resp.json()
      if (!data || typeof data !== 'object' || data.ok !== true || !data.item) {
        throw new Error(data?.error || 'Review create returned an invalid response')
      }

      await fetchReviewItems(reviewFilters)
      return data.item
    } catch (e) {
      const message = e.message || 'Failed to create review item'
      setReviewError(message)
      throw e
    } finally {
      setReviewSubmitting(false)
    }
  }

  async function updateReviewItemStatus(itemId, status) {
    setReviewUpdatingId(itemId)
    setReviewError(null)
    try {
      const resp = await fetch(`/api/review/${encodeURIComponent(itemId)}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status }),
      })
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to update review item'))
      }

      const data = await resp.json()
      if (!data || typeof data !== 'object' || data.ok !== true || !data.item) {
        throw new Error(data?.error || 'Review update returned an invalid response')
      }

      await fetchReviewItems(reviewFilters)
      return data.item
    } catch (e) {
      const message = e.message || 'Failed to update review item'
      setReviewError(message)
      throw e
    } finally {
      setReviewUpdatingId(null)
    }
  }

  async function fetchBehavioralGuidanceProposals(filters = behavioralGuidanceFilters) {
    setBehavioralGuidanceLoading(true)
    setBehavioralGuidanceError(null)
    try {
      const params = new URLSearchParams()
      if (filters.status) params.set('status', filters.status)
      if (filters.proposalType) params.set('proposal_type', filters.proposalType)
      params.set('limit', '50')

      const query = params.toString()
      const resp = await fetch(
        `/api/behavioral-guidance/proposals${query ? `?${query}` : ''}`
      )
      if (!resp.ok) {
        throw new Error(
          await readErrorMessage(resp, 'Failed to fetch behavioral guidance proposals')
        )
      }

      const data = await resp.json()
      if (!data || typeof data !== 'object' || !Array.isArray(data.proposals)) {
        throw new Error('Behavioral guidance response was not a valid proposal list')
      }

      setBehavioralGuidanceProposals(data.proposals)
      return data.proposals
    } catch (e) {
      console.warn('Failed to fetch behavioral guidance proposals:', e)
      setBehavioralGuidanceError(e.message || 'Failed to fetch behavioral guidance proposals')
      return []
    } finally {
      setBehavioralGuidanceLoading(false)
    }
  }

  function updateBehavioralGuidanceFilters(nextFilters) {
    setBehavioralGuidanceFilters(nextFilters)
    fetchBehavioralGuidanceProposals(nextFilters)
  }

  async function updateBehavioralGuidanceProposalStatus(proposalId, form) {
    setBehavioralGuidanceUpdatingId(proposalId)
    setBehavioralGuidanceError(null)
    try {
      const payload = {
        status: form.status,
        reviewed_by_user_id: form.reviewedByUserId || activeUserId || null,
        reviewed_by_role: form.reviewedByRole || 'admin',
        review_decision_reason: form.reviewDecisionReason || null,
      }

      const resp = await fetch(
        `/api/behavioral-guidance/proposals/${encodeURIComponent(proposalId)}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }
      )
      if (!resp.ok) {
        throw new Error(
          await readErrorMessage(resp, 'Failed to update behavioral guidance proposal')
        )
      }

      const data = await resp.json()
      if (!data || typeof data !== 'object' || data.ok !== true || !data.proposal) {
        throw new Error(data?.error || 'Behavioral guidance update returned an invalid response')
      }

      await fetchBehavioralGuidanceProposals(behavioralGuidanceFilters)
      return data.proposal
    } catch (e) {
      const message = e.message || 'Failed to update behavioral guidance proposal'
      setBehavioralGuidanceError(message)
      throw e
    } finally {
      setBehavioralGuidanceUpdatingId(null)
    }
  }

  async function handleCloseConversation() {
    if (!activeConversationId) return
    try {
      const resp = await fetch(`/api/conversations/${activeConversationId}/close`, {
        method: 'POST',
      })
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to close conversation'))
      }

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
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to fetch messages'))
      }

      const messages = await resp.json()
      if (!Array.isArray(messages)) {
        throw new Error('Messages response was not a list')
      }

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
    fetchRegistries()
  }, [])

  function handleRegistryRefresh() {
    setUploadResult(null)
    setUploadError(null)
    fetchRegistries()
  }

  function openSystemPanel() {
    setRightPanelView('system')
    if (!systemLoaded && !systemLoading) {
      fetchSystemStatus()
    }
  }

  function openSystemTab() {
    setActiveTab('system')
    if (!systemLoaded && !systemLoading) {
      fetchSystemStatus()
    }
  }

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
            {health.backend === 'unreachable' && (
              <div className="health-item err">
                Backend: unreachable
              </div>
            )}
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
        </div>
        <div className="m-body">
          {activeTab === 'chat' && mainContent}
          {activeTab === 'conversations' && (
            <div className="m-scroll">{sidebarContent}</div>
          )}
          {activeTab === 'debug' && (
            <div className="m-scroll"><DebugPanel data={debugData} /></div>
          )}
          {activeTab === 'registry' && (
            <div className="m-scroll">
              <RegistryPanel
                artifacts={artifacts}
                openLoops={openLoops}
                loading={registryLoading}
                error={registryError}
                uploading={uploading}
                uploadError={uploadError}
                uploadResult={uploadResult}
                onUpload={uploadArtifact}
                onRefresh={handleRegistryRefresh}
              />
            </div>
          )}
          {activeTab === 'system' && (
            <div className="m-scroll">
              <SystemPanel
                health={systemHealth}
                memory={systemMemory}
                capabilities={systemCapabilities}
                loading={systemLoading}
                error={systemError}
                onRefresh={fetchSystemStatus}
                reviewItems={reviewItems}
                reviewFilters={reviewFilters}
                reviewLoading={reviewLoading}
                reviewError={reviewError}
                reviewSubmitting={reviewSubmitting}
                reviewUpdatingId={reviewUpdatingId}
                onReviewRefresh={() => fetchReviewItems(reviewFilters)}
                onReviewFiltersChange={updateReviewFilters}
                onReviewCreate={createReviewItem}
                onReviewStatusUpdate={updateReviewItemStatus}
                behavioralGuidanceProposals={behavioralGuidanceProposals}
                behavioralGuidanceFilters={behavioralGuidanceFilters}
                behavioralGuidanceLoading={behavioralGuidanceLoading}
                behavioralGuidanceError={behavioralGuidanceError}
                behavioralGuidanceUpdatingId={behavioralGuidanceUpdatingId}
                onBehavioralGuidanceRefresh={() =>
                  fetchBehavioralGuidanceProposals(behavioralGuidanceFilters)
                }
                onBehavioralGuidanceFiltersChange={updateBehavioralGuidanceFilters}
                onBehavioralGuidanceStatusUpdate={updateBehavioralGuidanceProposalStatus}
              />
            </div>
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
          <button
            className={`m-tab ${activeTab === 'registry' ? 'active' : ''}`}
            onClick={() => setActiveTab('registry')}
          >Registry</button>
          <button
            className={`m-tab ${activeTab === 'system' ? 'active' : ''}`}
            onClick={openSystemTab}
          >System</button>
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
          <div className="right-panel-switch">
            <button
              type="button"
              className={`right-panel-tab ${rightPanelView === 'debug' ? 'active' : ''}`}
              onClick={() => setRightPanelView('debug')}
            >
              Debug
            </button>
            <button
              type="button"
              className={`right-panel-tab ${rightPanelView === 'registry' ? 'active' : ''}`}
              onClick={() => setRightPanelView('registry')}
            >
              Registry
            </button>
            <button
              type="button"
              className={`right-panel-tab ${rightPanelView === 'system' ? 'active' : ''}`}
              onClick={openSystemPanel}
            >
              System
            </button>
          </div>
          {rightPanelView === 'debug' && (
            <DebugPanel data={debugData} />
          )}
          {rightPanelView === 'registry' && (
            <RegistryPanel
              artifacts={artifacts}
              openLoops={openLoops}
              loading={registryLoading}
              error={registryError}
              uploading={uploading}
              uploadError={uploadError}
              uploadResult={uploadResult}
              onUpload={uploadArtifact}
              onRefresh={handleRegistryRefresh}
            />
          )}
          {rightPanelView === 'system' && (
            <SystemPanel
              health={systemHealth}
              memory={systemMemory}
              capabilities={systemCapabilities}
              loading={systemLoading}
              error={systemError}
              onRefresh={fetchSystemStatus}
              reviewItems={reviewItems}
              reviewFilters={reviewFilters}
              reviewLoading={reviewLoading}
              reviewError={reviewError}
              reviewSubmitting={reviewSubmitting}
              reviewUpdatingId={reviewUpdatingId}
              onReviewRefresh={() => fetchReviewItems(reviewFilters)}
              onReviewFiltersChange={updateReviewFilters}
              onReviewCreate={createReviewItem}
              onReviewStatusUpdate={updateReviewItemStatus}
              behavioralGuidanceProposals={behavioralGuidanceProposals}
              behavioralGuidanceFilters={behavioralGuidanceFilters}
              behavioralGuidanceLoading={behavioralGuidanceLoading}
              behavioralGuidanceError={behavioralGuidanceError}
              behavioralGuidanceUpdatingId={behavioralGuidanceUpdatingId}
              onBehavioralGuidanceRefresh={() =>
                fetchBehavioralGuidanceProposals(behavioralGuidanceFilters)
              }
              onBehavioralGuidanceFiltersChange={updateBehavioralGuidanceFilters}
              onBehavioralGuidanceStatusUpdate={updateBehavioralGuidanceProposalStatus}
            />
          )}
        </aside>
      )}
    </div>
  )
}

export default App
