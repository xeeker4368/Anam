import { useState, useEffect, useCallback, useRef } from 'react'
import Chat from './components/Chat'
import NameGate from './components/NameGate'
import DebugPanel from './components/DebugPanel'
import RegistryPanel from './components/RegistryPanel'
import SystemPanel from './components/SystemPanel'
import { apiFetch, readErrorMessage } from './api'
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

const CLIENT_STATE_KEYS = {
  activeUser: 'anam.activeUser',
  activeUserId: 'anam.activeUserId',
  activeConversationId: 'anam.activeConversationId',
  activeTab: 'anam.activeTab',
}

const RESUME_REFRESH_DELAY_MS = 150
const RESUME_REFRESH_THROTTLE_MS = 15000

const VALID_MOBILE_TABS = new Set(['chat', 'conversations', 'registry', 'system', 'debug'])

function readClientState(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeClientState(key, value) {
  try {
    if (value) {
      window.localStorage.setItem(key, value)
    } else {
      window.localStorage.removeItem(key)
    }
  } catch {
    // Local storage may be unavailable in private browsing or restricted contexts.
  }
}

function normalizeStoredTab(tab) {
  return VALID_MOBILE_TABS.has(tab) ? tab : 'chat'
}

// Identity is a resolved known user: {id, name, role}. We persist the full
// object so the role-based view is correct before /api/users reloads. The
// legacy bare-string `anam.activeUserId` key is intentionally NOT restored as
// identity — after deploy each user re-enters their name once via the gate.
function readActiveUser() {
  try {
    const raw = window.localStorage.getItem(CLIENT_STATE_KEYS.activeUser)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && parsed.id && parsed.name && parsed.role) {
      return { id: parsed.id, name: parsed.name, role: parsed.role }
    }
    return null
  } catch {
    return null
  }
}

function writeActiveUser(user) {
  try {
    if (user) {
      window.localStorage.setItem(CLIENT_STATE_KEYS.activeUser, JSON.stringify(user))
      window.localStorage.setItem(CLIENT_STATE_KEYS.activeUserId, user.id)
    } else {
      window.localStorage.removeItem(CLIENT_STATE_KEYS.activeUser)
      window.localStorage.removeItem(CLIENT_STATE_KEYS.activeUserId)
    }
  } catch {
    // Local storage may be unavailable in private browsing or restricted contexts.
  }
}

function conversationBelongsToUser(conversation, userId) {
  if (!conversation || !userId) return true
  return !conversation.user_id || conversation.user_id === userId
}

async function fetchJsonList(path, fallbackMessage) {
  const resp = await apiFetch(path)
  if (!resp.ok) {
    throw new Error(await readErrorMessage(resp, fallbackMessage))
  }

  const data = await resp.json()
  if (!Array.isArray(data)) {
    throw new Error(`${fallbackMessage} response was not a list`)
  }
  return data
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
  const [activeConversationId, setActiveConversationId] = useState(
    () => readClientState(CLIENT_STATE_KEYS.activeConversationId) || null
  )
  const [viewingConversation, setViewingConversation] = useState(null)
  const [viewingMessages, setViewingMessages] = useState([])
  const [debugData, setDebugData] = useState(null)
  const [showDebug, setShowDebug] = useState(false)
  const [health, setHealth] = useState(null)
  const [users, setUsers] = useState([])
  const [activeUser, setActiveUser] = useState(() => readActiveUser())
  const activeUserId = activeUser?.id || null
  const [showDashboard, setShowDashboard] = useState(false)
  const [activeTab, setActiveTab] = useState(
    () => normalizeStoredTab(readClientState(CLIENT_STATE_KEYS.activeTab))
  )
  const [rightPanelView, setRightPanelView] = useState('debug')
  const [artifacts, setArtifacts] = useState([])
  const [openLoops, setOpenLoops] = useState([])
  const [registryLoading, setRegistryLoading] = useState(false)
  const [registryError, setRegistryError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [imageGenerating, setImageGenerating] = useState(false)
  const [imageGenerationError, setImageGenerationError] = useState(null)
  const [imageGenerationResult, setImageGenerationResult] = useState(null)
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
  const lastResumeRefreshRef = useRef(0)
  const resumeRefreshTimerRef = useRef(null)
  const chatStreamActiveRef = useRef(false)
  const activeConversationIdRef = useRef(activeConversationId)
  const activeUserIdRef = useRef(activeUserId)
  const conversationsRef = useRef(conversations)
  const isMobile = useIsMobile()
  useViewportHeight()

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId
  }, [activeConversationId])

  useEffect(() => {
    activeUserIdRef.current = activeUserId
  }, [activeUserId])

  useEffect(() => {
    conversationsRef.current = conversations
  }, [conversations])

  const applyActiveUser = useCallback((user) => {
    const userId = user?.id || null
    writeActiveUser(user)
    activeUserIdRef.current = userId
    setActiveUser(user)

    const currentConversationId = activeConversationIdRef.current
    const currentConversations = conversationsRef.current
    if (!currentConversationId || currentConversations.length === 0) return

    const activeConversation = currentConversations.find(
      conv => conv.id === currentConversationId
    )
    if (activeConversation && conversationBelongsToUser(activeConversation, userId)) return

    activeConversationIdRef.current = null
    setActiveConversationId(null)
    setViewingConversation(null)
    setViewingMessages([])
  }, [])

  // Gate resolved a known user (full {id, name, role} from /api/users/resolve).
  const handleUserResolved = useCallback((user) => {
    applyActiveUser(user)
  }, [applyActiveUser])

  // Admin switching among known users via the dropdown.
  const selectActiveUser = useCallback((userId) => {
    const user = users.find(u => u.id === userId)
    if (user) applyActiveUser(user)
  }, [users, applyActiveUser])

  // Switch / sign out: clear identity and active conversation -> back to gate.
  const handleSignOut = useCallback(() => {
    activeConversationIdRef.current = null
    setActiveConversationId(null)
    setViewingConversation(null)
    setViewingMessages([])
    applyActiveUser(null)
  }, [applyActiveUser])

  const fetchConversations = useCallback(async () => {
    try {
      const data = await fetchJsonList('/api/conversations', 'Failed to fetch conversations')

      conversationsRef.current = data
      setConversations(data)
      const storedConversationId = readClientState(CLIENT_STATE_KEYS.activeConversationId)
      const storedUserId = readClientState(CLIENT_STATE_KEYS.activeUserId)
      const candidateConversationId = activeConversationIdRef.current || storedConversationId
      const candidateUserId = storedUserId || activeUserIdRef.current
      if (candidateConversationId) {
        const candidate = data.find(conv => conv.id === candidateConversationId)
        if (!candidate) {
          activeConversationIdRef.current = null
          setActiveConversationId(null)
        } else if (conversationBelongsToUser(candidate, candidateUserId)) {
          activeConversationIdRef.current = candidateConversationId
          setActiveConversationId(candidateConversationId)
        } else {
          activeConversationIdRef.current = null
          setActiveConversationId(null)
        }
      }
    } catch (e) {
      console.error('Failed to fetch conversations:', e)
    }
  }, [])

  const fetchHealth = useCallback(async () => {
    try {
      const resp = await apiFetch('/api/health')
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
  }, [])

  const fetchUsers = useCallback(async () => {
    try {
      const data = await fetchJsonList('/api/users', 'Failed to fetch users')

      setUsers(data)
      // No auto-selection: identity is established only via the name gate
      // (or restored from a previously resolved active user). If the stored
      // active user no longer exists, return to the gate.
      const currentId = activeUserIdRef.current
      if (currentId && !data.some(u => u.id === currentId)) {
        activeConversationIdRef.current = null
        setActiveConversationId(null)
        setViewingConversation(null)
        setViewingMessages([])
        writeActiveUser(null)
        activeUserIdRef.current = null
        setActiveUser(null)
      }
    } catch (e) {
      console.error('Failed to fetch users:', e)
    }
  }, [])

  const fetchArtifacts = useCallback(async ({ showLoading = true } = {}) => {
    if (showLoading) {
      setRegistryLoading(true)
      setRegistryError(null)
    }
    try {
      const data = await fetchJsonList('/api/artifacts', 'Failed to fetch artifacts')
      setArtifacts(data)
      return data
    } catch (e) {
      console.warn('Failed to fetch artifacts:', e)
      setRegistryError(e.message || 'Failed to fetch media and artifacts')
      return []
    } finally {
      if (showLoading) setRegistryLoading(false)
    }
  }, [])

  const fetchOpenLoops = useCallback(async ({ showLoading = true } = {}) => {
    if (showLoading) {
      setRegistryLoading(true)
      setRegistryError(null)
    }
    try {
      const data = await fetchJsonList('/api/open-loops', 'Failed to fetch open loops')
      setOpenLoops(data)
      return data
    } catch (e) {
      console.warn('Failed to fetch open loops:', e)
      setRegistryError(e.message || 'Failed to fetch open loops')
      return []
    } finally {
      if (showLoading) setRegistryLoading(false)
    }
  }, [])

  const fetchRegistries = useCallback(async () => {
    setRegistryLoading(true)
    setRegistryError(null)
    try {
      await Promise.all([
        fetchArtifacts({ showLoading: false }),
        fetchOpenLoops({ showLoading: false }),
      ])
    } finally {
      setRegistryLoading(false)
    }
  }, [fetchArtifacts, fetchOpenLoops])

  useEffect(() => {
    const initialRefreshTimer = window.setTimeout(() => {
      fetchConversations()
      fetchHealth()
      fetchUsers()
      fetchRegistries()
    }, 0)
    const healthInterval = setInterval(fetchHealth, 30000)
    return () => {
      window.clearTimeout(initialRefreshTimer)
      clearInterval(healthInterval)
    }
  }, [fetchConversations, fetchHealth, fetchRegistries, fetchUsers])

  useEffect(() => {
    writeClientState(CLIENT_STATE_KEYS.activeUserId, activeUserId)
  }, [activeUserId])

  useEffect(() => {
    writeClientState(CLIENT_STATE_KEYS.activeConversationId, activeConversationId)
  }, [activeConversationId])

  useEffect(() => {
    writeClientState(CLIENT_STATE_KEYS.activeTab, activeTab)
  }, [activeTab])

  useEffect(() => {
    function runResumeRefresh() {
      resumeRefreshTimerRef.current = null
      if (chatStreamActiveRef.current) return
      lastResumeRefreshRef.current = Date.now()
      fetchConversations()
      fetchHealth()
      fetchRegistries()
    }

    function scheduleResumeRefresh() {
      if (document.visibilityState && document.visibilityState !== 'visible') return
      if (chatStreamActiveRef.current) return
      const now = Date.now()
      if (now - lastResumeRefreshRef.current < RESUME_REFRESH_THROTTLE_MS) return
      if (resumeRefreshTimerRef.current) return
      resumeRefreshTimerRef.current = window.setTimeout(runResumeRefresh, RESUME_REFRESH_DELAY_MS)
    }

    function handleVisibilityChange() {
      if (document.visibilityState === 'visible') {
        scheduleResumeRefresh()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', scheduleResumeRefresh)
    window.addEventListener('pageshow', scheduleResumeRefresh)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', scheduleResumeRefresh)
      window.removeEventListener('pageshow', scheduleResumeRefresh)
      if (resumeRefreshTimerRef.current) {
        window.clearTimeout(resumeRefreshTimerRef.current)
        resumeRefreshTimerRef.current = null
      }
    }
  }, [fetchConversations, fetchHealth, fetchRegistries])

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
      if (form.mediaKind?.trim()) body.append('media_kind', form.mediaKind.trim())

      const resp = await apiFetch('/api/artifacts/upload', {
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
      await fetchArtifacts()
      return data
    } catch (e) {
      const message = e.message || 'Artifact upload failed'
      setUploadError(message)
      throw e
    } finally {
      setUploading(false)
    }
  }

  async function generateImage(form) {
    setImageGenerating(true)
    setImageGenerationError(null)
    setImageGenerationResult(null)
    try {
      const payload = {
        prompt: form.prompt,
        negative_prompt: form.negativePrompt || null,
        backend: form.backend || 'comfyui',
        width: form.width,
        height: form.height,
        seed: form.seed,
        intended_use: form.intendedUse || 'general',
        user_id: activeUserId || null,
      }

      const resp = await apiFetch('/api/image-generation/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      const data = await resp.json().catch(() => null)
      if (!resp.ok || !data || data.generation_error) {
        const message = data?.error || data?.detail || `Image generation failed (${resp.status})`
        throw new Error(message)
      }
      if (!data || typeof data !== 'object' || data.ok !== true || !data.artifact) {
        throw new Error('Image generation returned an invalid response')
      }

      setImageGenerationResult(data)
      await fetchArtifacts()
      return data
    } catch (e) {
      const message = e.message || 'Image generation failed'
      setImageGenerationError(message)
      throw e
    } finally {
      setImageGenerating(false)
    }
  }

  async function fetchSystemStatus() {
    setSystemLoading(true)
    setSystemError(null)
    const reviewPromise = fetchReviewItems()
    const behavioralGuidancePromise = fetchBehavioralGuidanceProposals()
    try {
      const [healthResp, memoryResp, capabilitiesResp] = await Promise.all([
        apiFetch('/api/system/health'),
        apiFetch('/api/system/memory'),
        apiFetch('/api/system/capabilities'),
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
      const resp = await apiFetch(`/api/review${query ? `?${query}` : ''}`)
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

      const resp = await apiFetch('/api/review', {
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
      const resp = await apiFetch(`/api/review/${encodeURIComponent(itemId)}`, {
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
      const resp = await apiFetch(
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

      const resp = await apiFetch(
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
      const resp = await apiFetch(`/api/conversations/${activeConversationId}/close`, {
        method: 'POST',
      })
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to close conversation'))
      }

      await resp.json().catch(() => null)
      activeConversationIdRef.current = null
      setActiveConversationId(null)
      setDebugData(null)
      fetchConversations()
    } catch (e) {
      console.error('Failed to close conversation:', e)
    }
  }

  async function handleViewConversation(conv) {
    try {
      const resp = await apiFetch(`/api/conversations/${conv.id}/messages`)
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to fetch messages'))
      }

      const messages = await resp.json()
      if (!Array.isArray(messages)) {
        throw new Error('Messages response was not a list')
      }

      activeConversationIdRef.current = conv.id
      setActiveConversationId(conv.id)
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

  function handleSelectConversation(conv) {
    if (conv.ended_at) {
      handleViewConversation(conv)
      return
    }

    activeConversationIdRef.current = conv.id
    setActiveConversationId(conv.id)
    setViewingConversation(null)
    setViewingMessages([])
  }

  const handleConversationCreated = useCallback((convId) => {
    activeConversationIdRef.current = convId
    setActiveConversationId(convId)
  }, [])

  const handleDebugData = useCallback((data) => {
    setDebugData(data)
  }, [])

  const handleChatRefresh = useCallback(() => {
    fetchConversations()
  }, [fetchConversations])

  const handleChatStreamingStateChange = useCallback((isActive) => {
    chatStreamActiveRef.current = Boolean(isActive)
    if (isActive && resumeRefreshTimerRef.current) {
      window.clearTimeout(resumeRefreshTimerRef.current)
      resumeRefreshTimerRef.current = null
    }
  }, [])

  function handleRegistryRefresh() {
    setUploadResult(null)
    setUploadError(null)
    setImageGenerationError(null)
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

  const activeUserName = activeUser?.name || 'No user selected'
  const isAdmin = activeUser?.role === 'admin'

  // --- Sidebar content ---
  const sidebarContent = (
    <>
      <div className="sidebar-header">
        <h1>Project Anam</h1>
        {users.length > 1 && (
          <select
            value={activeUserId || ''}
            onChange={e => selectActiveUser(e.target.value)}
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
            onClick={() => handleSelectConversation(conv)}
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
          {showDashboard ? 'Hide Status' : 'Status'}
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
              {msg.role === 'user' ? viewingConversation.user_name : 'Assistant'}
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
      userName={activeUserName}
      onSignOut={handleSignOut}
      onConversationCreated={handleConversationCreated}
      onDebugData={handleDebugData}
      onRefresh={handleChatRefresh}
      onStreamingStateChange={handleChatStreamingStateChange}
    />
  )

  // --- Name-login gate: no chat until a known user is resolved ---
  if (!activeUser) {
    return <NameGate onResolved={handleUserResolved} />
  }

  // --- Household (non-admin): chat only, no operator surfaces ---
  if (!isAdmin) {
    return (
      <div className="app-chat-only">
        <main className="chat-only-main">{mainContent}</main>
      </div>
    )
  }

  // --- Mobile layout ---
  if (isMobile) {
    return (
      <div className="app-mobile">
        <div className="m-header">
          <div className="m-title-group">
            <span className="m-title">Project Anam</span>
            {users.length > 1 ? (
              <label className="m-user-switch">
                <span>Household user</span>
                <select
                  value={activeUserId || ''}
                  onChange={e => selectActiveUser(e.target.value)}
                  aria-label="Active household user"
                >
                  {users.map(user => (
                    <option key={user.id} value={user.id}>{user.name}</option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="m-active-user">User: {activeUserName}</span>
            )}
          </div>
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
                imageGenerating={imageGenerating}
                imageGenerationError={imageGenerationError}
                imageGenerationResult={imageGenerationResult}
                imageGenerationCapability={systemCapabilities?.capabilities?.image_generation}
                onGenerateImage={generateImage}
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
            className={`m-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >Chat</button>
          <button
            className={`m-tab ${activeTab === 'conversations' ? 'active' : ''}`}
            onClick={() => setActiveTab('conversations')}
          >History</button>
          <button
            className={`m-tab ${activeTab === 'registry' ? 'active' : ''}`}
            onClick={() => setActiveTab('registry')}
          >Media</button>
          <button
            className={`m-tab ${activeTab === 'system' ? 'active' : ''}`}
            onClick={openSystemTab}
          >Status</button>
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
              Media
            </button>
            <button
              type="button"
              className={`right-panel-tab ${rightPanelView === 'system' ? 'active' : ''}`}
              onClick={openSystemPanel}
            >
              Status
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
              imageGenerating={imageGenerating}
              imageGenerationError={imageGenerationError}
              imageGenerationResult={imageGenerationResult}
              imageGenerationCapability={systemCapabilities?.capabilities?.image_generation}
              onGenerateImage={generateImage}
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
