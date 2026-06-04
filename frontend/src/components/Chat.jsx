import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, readErrorMessage } from '../api'

function draftStorageKey(userId, conversationId) {
  return `anam.chatDraft.${userId || 'unknown'}.${conversationId || 'new'}`
}

function readDraft(key) {
  try {
    return window.localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

function writeDraft(key, value) {
  try {
    if (value) {
      window.localStorage.setItem(key, value)
    } else {
      window.localStorage.removeItem(key)
    }
  } catch {
    // Local storage can be unavailable in private browsing or restricted contexts.
  }
}

function hasPersistedMatchingUser(serverMessages, localMessage) {
  return serverMessages.some(message => (
    message.role === 'user' && message.content === localMessage.content
  ))
}

function hasPersistedAssistantForPending(serverMessages, pendingMessage) {
  // Anchor by the server user-message id (from the debug event), not by content:
  // repeated content would otherwise collide with an earlier identical turn that
  // did get a reply, falsely dropping this turn's interrupted bubble.
  const anchorId = pendingMessage.serverUserMessageId
  if (!anchorId) return false

  const userIndex = serverMessages.findIndex(message => message.id === anchorId)
  if (userIndex < 0) return false

  return serverMessages
    .slice(userIndex + 1)
    .some(message => message.role === 'assistant' && (message.content || '').trim())
}

function hasLocalPendingMessages(localMessages) {
  return localMessages.some(message => (
    message.localOnly && (message.optimistic || message.pending) && message.role
  ))
}

function hasAdoptablePendingMessages(serverMessages, localMessages) {
  return localMessages.some(message => (
    message.localOnly
      && message.role === 'user'
      && message.optimistic
      && hasPersistedMatchingUser(serverMessages, message)
  ))
}

function mergeServerMessagesWithLocalPending(serverMessages, localMessages) {
  const merged = [...serverMessages]

  localMessages.forEach(localMessage => {
    if (localMessage.optimistic && localMessage.role === 'user') {
      if (!hasPersistedMatchingUser(serverMessages, localMessage)) {
        merged.push(localMessage)
      }
      return
    }

    if (localMessage.localOnly && localMessage.role === 'assistant') {
      if (!hasPersistedAssistantForPending(serverMessages, localMessage)) {
        merged.push(localMessage)
      }
    }
  })

  return merged
}

function interruptedAssistantMessage(message) {
  return {
    ...message,
    streaming: false,
    pending: true,
    interrupted: true,
    localOnly: true,
    interruptedAt: Date.now(),
  }
}

const RESUME_MESSAGE_REFRESH_DELAY_MS = 150
const RESUME_MESSAGE_REFRESH_THROTTLE_MS = 2500

function Chat({
  conversationId,
  userId,
  userName,
  onSignOut,
  onConversationCreated,
  onDebugData,
  onRefresh,
  onStreamingStateChange,
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [keyboardActive, setKeyboardActive] = useState(false)
  const isStreamingRef = useRef(false)
  const debugRef = useRef(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const inputAreaRef = useRef(null)
  const viewportScrollTimerRef = useRef(null)
  const viewportRafRef = useRef(null)
  const viewportDelayTimersRef = useRef([])
  const mountedRef = useRef(false)
  const streamAbortRef = useRef(null)
  const streamAbortReasonRef = useRef(null)
  const streamReaderRef = useRef(null)
  const streamIdRef = useRef(0)
  const messageIdCounterRef = useRef(0)
  const draftStorageKeyRef = useRef(draftStorageKey(userId, conversationId))
  const skipDraftPersistRef = useRef(false)
  const wasHiddenRef = useRef(false)
  const messagesConversationIdRef = useRef(conversationId)
  const resumeMessageRefreshTimerRef = useRef(null)
  const lastResumeMessageRefreshRef = useRef(0)
  const onStreamingStateChangeRef = useRef(onStreamingStateChange)

  useEffect(() => {
    onStreamingStateChangeRef.current = onStreamingStateChange
  }, [onStreamingStateChange])

  function setStreamingActive(isActive) {
    setIsStreaming(isActive)
    isStreamingRef.current = isActive
    onStreamingStateChangeRef.current?.(isActive)
    if (isActive && resumeMessageRefreshTimerRef.current) {
      window.clearTimeout(resumeMessageRefreshTimerRef.current)
      resumeMessageRefreshTimerRef.current = null
    }
  }

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      streamAbortReasonRef.current = 'unmount'
      onStreamingStateChangeRef.current?.(false)
      streamAbortRef.current?.abort()
      streamReaderRef.current?.cancel().catch(() => {})
      streamReaderRef.current = null
      if (resumeMessageRefreshTimerRef.current) {
        window.clearTimeout(resumeMessageRefreshTimerRef.current)
        resumeMessageRefreshTimerRef.current = null
      }
      if (viewportScrollTimerRef.current) {
        window.clearTimeout(viewportScrollTimerRef.current)
      }
      if (viewportRafRef.current) {
        window.cancelAnimationFrame(viewportRafRef.current)
      }
      viewportDelayTimersRef.current.forEach(timer => window.clearTimeout(timer))
      viewportDelayTimersRef.current = []
    }
  }, [])

  function nextMessageId(prefix) {
    messageIdCounterRef.current += 1
    return `${prefix}-${Date.now()}-${messageIdCounterRef.current}`
  }

  const messageIdFromServer = useCallback((message, index) => {
    return message.id || message.message_id || `${message.timestamp || 'message'}-${index}`
  }, [])

  function isAbortError(error) {
    return error?.name === 'AbortError'
  }

  const scrollToLatestMessage = useCallback((behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior, block: 'end' })
  }, [])

  const updateVisualViewportVars = useCallback(() => {
    const root = document.documentElement
    const visualViewport = window.visualViewport
    const composerHeight = Math.ceil(inputAreaRef.current?.getBoundingClientRect().height || 76)

    if (!visualViewport) {
      const fixedTop = Math.max(0, window.innerHeight - composerHeight)
      root.style.setProperty('--anam-visual-viewport-height', `${window.innerHeight}px`)
      root.style.setProperty('--anam-visual-viewport-offset-top', '0px')
      root.style.setProperty('--anam-visual-viewport-bottom-gap', '0px')
      root.style.setProperty('--anam-composer-height', `${composerHeight}px`)
      root.style.setProperty('--anam-composer-fixed-top', `${fixedTop}px`)
      root.style.setProperty('--anam-composer-occluded-bottom-space', `${composerHeight}px`)
      return
    }

    const bottomGap = Math.max(
      0,
      window.innerHeight - visualViewport.height - visualViewport.offsetTop
    )
    const fixedTop = Math.max(
      visualViewport.offsetTop,
      visualViewport.offsetTop + visualViewport.height - composerHeight
    )
    const occludedBottomSpace = Math.max(composerHeight, window.innerHeight - fixedTop)

    root.style.setProperty('--vv-height', `${visualViewport.height}px`)
    root.style.setProperty('--vv-offset-top', `${visualViewport.offsetTop}px`)
    root.style.setProperty('--composer-height', `${composerHeight}px`)
    root.style.setProperty('--composer-fixed-top', `${fixedTop}px`)
    root.style.setProperty('--anam-visual-viewport-height', `${visualViewport.height}px`)
    root.style.setProperty('--anam-visual-viewport-offset-top', `${visualViewport.offsetTop}px`)
    root.style.setProperty('--anam-visual-viewport-bottom-gap', `${bottomGap}px`)
    root.style.setProperty('--anam-composer-height', `${composerHeight}px`)
    root.style.setProperty('--anam-composer-fixed-top', `${fixedTop}px`)
    root.style.setProperty('--anam-composer-occluded-bottom-space', `${occludedBottomSpace}px`)
  }, [])

  const scheduleViewportSync = useCallback((behavior = 'auto') => {
    updateVisualViewportVars()

    if (viewportRafRef.current) {
      window.cancelAnimationFrame(viewportRafRef.current)
    }
    viewportDelayTimersRef.current.forEach(timer => window.clearTimeout(timer))
    viewportDelayTimersRef.current = []

    viewportRafRef.current = window.requestAnimationFrame(() => {
      updateVisualViewportVars()
      scrollToLatestMessage(behavior)
    })

    viewportDelayTimersRef.current = [60, 160, 320].map(delay => (
      window.setTimeout(() => {
        updateVisualViewportVars()
        scrollToLatestMessage(behavior)
      }, delay)
    ))
  }, [scrollToLatestMessage, updateVisualViewportVars])

  function updateMessageById(messageId, updater) {
    setMessages(prev => prev.map(message => (
      message.id === messageId ? updater(message) : message
    )))
  }

  function elapsedMs(start, end = performance.now()) {
    return Math.round((end - start) * 100) / 100
  }

  function summarize(value, maxLength = 220) {
    const text = typeof value === 'string' ? value : JSON.stringify(value)
    if (!text) return ''
    return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text
  }

  function publishDebug(nextDebug) {
    debugRef.current = nextDebug
    onDebugData({
      ...nextDebug,
      tool_events: [...(nextDebug.tool_events || [])],
      raw_events: [...(nextDebug.raw_events || [])],
    })
  }

  function ensureDebug() {
    if (!debugRef.current) {
      debugRef.current = {
        tool_events: [],
        raw_events: [],
      }
    }
    return debugRef.current
  }

  function appendRawEvent(data) {
    const current = ensureDebug()
    const next = {
      ...current,
      raw_events: [...(current.raw_events || []), data],
    }
    publishDebug(next)
  }

  function mergeDebugTimings(timings, rawEvent = null) {
    const current = ensureDebug()
    const next = {
      ...current,
      timings: {
        ...(current.timings || {}),
        ...timings,
      },
      raw_events: rawEvent
        ? [...(current.raw_events || []), rawEvent]
        : [...(current.raw_events || [])],
    }
    publishDebug(next)
  }

  function recordToolCall(data) {
    const current = ensureDebug()
    const toolEvent = {
      name: data.name || 'unknown',
      arguments: data.arguments || {},
      query: data.arguments?.query,
      status: 'pending',
      result: null,
      result_summary: '',
      raw_call: data,
    }
    const next = {
      ...current,
      tool_events: [...(current.tool_events || []), toolEvent],
      raw_events: [...(current.raw_events || []), data],
    }
    publishDebug(next)
  }

  function recordToolResult(data) {
    const current = ensureDebug()
    const toolEvents = [...(current.tool_events || [])]
    const matchIndex = [...toolEvents]
      .reverse()
      .findIndex(event => event.name === data.name && event.status === 'pending')
    const targetIndex = matchIndex >= 0 ? toolEvents.length - 1 - matchIndex : -1

    if (targetIndex >= 0) {
      toolEvents[targetIndex] = {
        ...toolEvents[targetIndex],
        status: data.ok ? 'succeeded' : 'failed',
        ok: data.ok,
        result: data.result,
        result_summary: summarize(data.result),
        raw_result: data,
      }
    } else {
      toolEvents.push({
        name: data.name || 'unknown',
        arguments: {},
        query: undefined,
        status: data.ok ? 'succeeded' : 'failed',
        ok: data.ok,
        result: data.result,
        result_summary: summarize(data.result),
        raw_result: data,
      })
    }

    const next = {
      ...current,
      tool_events: toolEvents,
      raw_events: [...(current.raw_events || []), data],
    }
    publishDebug(next)
  }

  const fetchMessages = useCallback(async (convId) => {
    try {
      const resp = await apiFetch(`/api/conversations/${convId}/messages`)
      if (!resp.ok) {
        throw new Error(await readErrorMessage(resp, 'Failed to fetch messages'))
      }

      const data = await resp.json()
      if (!Array.isArray(data)) {
        throw new Error('Messages response was not a list')
      }

      const serverMessages = data.map((m, index) => ({
        id: messageIdFromServer(m, index),
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
        persisted: true,
      }))
      setMessages(prev => {
        const sameConversation = messagesConversationIdRef.current === convId
        const canAdoptNewConversationPending = (
          messagesConversationIdRef.current === null
            && hasLocalPendingMessages(prev)
            && hasAdoptablePendingMessages(serverMessages, prev)
        )
        const shouldMergeLocal = sameConversation || canAdoptNewConversationPending
        messagesConversationIdRef.current = convId
        return shouldMergeLocal
          ? mergeServerMessagesWithLocalPending(serverMessages, prev)
          : serverMessages
      })
    } catch (e) {
      console.warn('Failed to fetch messages:', e)
    }
  }, [messageIdFromServer])

  useEffect(() => {
    const key = draftStorageKey(userId, conversationId)
    draftStorageKeyRef.current = key
    skipDraftPersistRef.current = true
    setInput(readDraft(key))
  }, [userId, conversationId])

  useEffect(() => {
    if (skipDraftPersistRef.current) {
      skipDraftPersistRef.current = false
      return
    }
    writeDraft(draftStorageKeyRef.current, input)
  }, [input])

  // Load existing messages when conversationId changes
  // Skip if we're mid-stream — streaming manages its own message state
  useEffect(() => {
    if (conversationId && !isStreamingRef.current) {
      fetchMessages(conversationId)
    } else if (!conversationId) {
      messagesConversationIdRef.current = null
      setMessages([])
    }
  }, [conversationId, fetchMessages])

  useEffect(() => {
    function runResumeMessageRefresh() {
      resumeMessageRefreshTimerRef.current = null
      if (isStreamingRef.current) return
      lastResumeMessageRefreshRef.current = Date.now()
      if (!conversationId) return
      fetchMessages(conversationId)
    }

    function scheduleResumeMessageRefresh() {
      if (!conversationId) return
      if (document.visibilityState && document.visibilityState !== 'visible') return
      if (isStreamingRef.current) return
      const now = Date.now()
      if (now - lastResumeMessageRefreshRef.current < RESUME_MESSAGE_REFRESH_THROTTLE_MS) return
      if (resumeMessageRefreshTimerRef.current) return
      resumeMessageRefreshTimerRef.current = window.setTimeout(
        runResumeMessageRefresh,
        RESUME_MESSAGE_REFRESH_DELAY_MS
      )
    }

    function handleVisibilityChange() {
      if (document.visibilityState === 'hidden') {
        wasHiddenRef.current = true
        return
      }
      if (document.visibilityState === 'visible') {
        scheduleResumeMessageRefresh()
        wasHiddenRef.current = false
      }
    }

    function handleFocus() {
      scheduleResumeMessageRefresh()
      wasHiddenRef.current = false
    }

    function handlePageShow() {
      scheduleResumeMessageRefresh()
      wasHiddenRef.current = false
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleFocus)
    window.addEventListener('pageshow', handlePageShow)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
      window.removeEventListener('pageshow', handlePageShow)
      if (resumeMessageRefreshTimerRef.current) {
        window.clearTimeout(resumeMessageRefreshTimerRef.current)
        resumeMessageRefreshTimerRef.current = null
      }
    }
  }, [conversationId, fetchMessages])

  // Auto-scroll to bottom
  useEffect(() => {
    scrollToLatestMessage('smooth')
  }, [messages, scrollToLatestMessage])

  useEffect(() => {
    if (!window.visualViewport) return undefined

    function handleVisualViewportChange() {
      if (viewportScrollTimerRef.current) {
        window.clearTimeout(viewportScrollTimerRef.current)
      }
      viewportScrollTimerRef.current = window.setTimeout(() => {
        scheduleViewportSync('auto')
      }, 90)
    }

    updateVisualViewportVars()
    window.visualViewport.addEventListener('resize', handleVisualViewportChange)
    window.visualViewport.addEventListener('scroll', handleVisualViewportChange)
    return () => {
      window.visualViewport.removeEventListener('resize', handleVisualViewportChange)
      window.visualViewport.removeEventListener('scroll', handleVisualViewportChange)
      if (viewportScrollTimerRef.current) {
        window.clearTimeout(viewportScrollTimerRef.current)
      }
    }
  }, [scheduleViewportSync, updateVisualViewportVars])

  // Focus input
  useEffect(() => {
    if (!isStreaming) {
      inputRef.current?.focus()
    }
  }, [isStreaming])

  async function sendMessage() {
    const text = input.trim()
    if (!text) return
    if (isStreamingRef.current) {
      streamAbortReasonRef.current = 'user_abort'
      streamAbortRef.current?.abort()
      return
    }

    writeDraft(draftStorageKeyRef.current, '')
    setInput('')
    setStreamingActive(true)
    debugRef.current = null
    streamAbortRef.current?.abort()
    streamAbortReasonRef.current = null
    const streamId = streamIdRef.current + 1
    streamIdRef.current = streamId
    const abortController = new AbortController()
    streamAbortRef.current = abortController
    const requestStart = performance.now()
    let firstTokenSeen = false
    let reader = null
    let streamDone = false
    let streamStarted = false
    let sawDoneEvent = false
    let sawError = false
    const userMessageId = nextMessageId('user')
    const assistantMessageId = nextMessageId('assistant')
    messagesConversationIdRef.current = conversationId

    // Add user message to display immediately
    setMessages(prev => [
      ...prev,
      {
        id: userMessageId,
        role: 'user',
        content: text,
        optimistic: true,
        localOnly: true,
        conversationScope: conversationId || 'new',
        createdAtClient: Date.now(),
      },
    ])

    // Add empty assistant message that will be filled by streaming
    setMessages(prev => [
      ...prev,
      {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        streaming: true,
        pending: true,
        localOnly: true,
        conversationScope: conversationId || 'new',
        pendingForUserMessageId: userMessageId,
        pendingForUserContent: text,
        createdAtClient: Date.now(),
      },
    ])

    try {
      const resp = await apiFetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal,
        body: JSON.stringify({
          text,
          conversation_id: conversationId,
          user_id: userId,
        }),
      })

      if (!resp.ok) {
        const message = await readErrorMessage(resp, 'Chat request failed')
        appendRawEvent({
          type: 'error',
          source: 'http',
          status: resp.status,
          message,
        })
        updateMessageById(assistantMessageId, last => ({
          ...last,
          content: message,
          streaming: false,
          pending: false,
          error: true,
        }))
        return
      }

      reader = resp.body.getReader()
      streamReaderRef.current = reader
      streamStarted = true
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        if (abortController.signal.aborted || streamIdRef.current !== streamId) break
        const { done, value } = await reader.read()
        if (done) {
          streamDone = true
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.trim()) continue

          try {
            const data = JSON.parse(line)

            if (data.type === 'debug') {
              const debugAt = performance.now()
              publishDebug({
                ...data,
                timings: {
                  ...(data.timings || {}),
                  request_start_to_debug_ms: elapsedMs(requestStart, debugAt),
                },
                tool_events: [],
                raw_events: [data],
              })
              // Stamp this turn's server user-message id onto the pending assistant
              // bubble so reconciliation can anchor by id, not by ambiguous content.
              if (data.user_message_id) {
                updateMessageById(assistantMessageId, last => ({
                  ...last,
                  serverUserMessageId: data.user_message_id,
                }))
              }
              if (data.conversation_id && data.conversation_id !== conversationId) {
                messagesConversationIdRef.current = data.conversation_id
                onConversationCreated(data.conversation_id)
              }
            } else if (data.type === 'debug_update') {
              mergeDebugTimings(data.timings || {}, data)
            } else if (data.type === 'tool_call') {
              recordToolCall(data)
            } else if (data.type === 'tool_result') {
              recordToolResult(data)
            } else if (data.type === 'token') {
              if (abortController.signal.aborted || streamIdRef.current !== streamId) break
              if (!firstTokenSeen) {
                firstTokenSeen = true
                mergeDebugTimings({
                  request_start_to_first_token_ms: elapsedMs(requestStart),
                })
              }
              updateMessageById(assistantMessageId, last => ({
                ...last,
                content: last.content + data.content,
              }))
            } else if (data.type === 'done') {
              const doneAt = performance.now()
              mergeDebugTimings({
                request_start_to_done_ms: elapsedMs(requestStart, doneAt),
                frontend_stream_total_ms: elapsedMs(requestStart, doneAt),
              }, data)
              // Mark streaming complete
              sawDoneEvent = true
              updateMessageById(assistantMessageId, last => ({
                ...last,
                streaming: false,
                pending: false,
                interrupted: false,
              }))
            } else if (data.type === 'error') {
              appendRawEvent(data)
              sawError = true
              updateMessageById(assistantMessageId, last => ({
                ...last,
                content: data.message,
                streaming: false,
                pending: false,
                error: true,
              }))
            } else {
              appendRawEvent(data)
            }
          } catch (parseErr) {
            console.warn('Failed to parse stream line:', line, parseErr)
          }
        }
      }
    } catch (e) {
      if (isAbortError(e) || abortController.signal.aborted) {
        // Explicit abort (user re-send, unmount) — settled in finally.
        return
      }
      if (!streamStarted) {
        // Request failed before any streaming began: a genuine connection error.
        console.error('Stream failed:', e)
        updateMessageById(assistantMessageId, last => ({
          ...last,
          content: `Connection error: ${e.message}`,
          streaming: false,
          pending: false,
          error: true,
        }))
        return
      }
      // Stream was interrupted after it began (e.g. iOS backgrounded the tab and
      // the connection was torn down mid-response). Fall through to finally, which
      // does a single message refetch to recover a server-persisted reply if one
      // exists, and otherwise settles the local bubble.
      console.warn('Stream interrupted mid-response:', e)
    } finally {
      if (reader) {
        try {
          if (!streamDone) {
            await reader.cancel()
          }
        } catch (e) {
          if (!isAbortError(e)) {
            console.warn('Failed to cancel stream reader:', e)
          }
        } finally {
          try {
            reader.releaseLock()
          } catch {
            // Reader may already be released after cancellation/error.
          }
          if (streamReaderRef.current === reader) {
            streamReaderRef.current = null
          }
        }
      }
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null
      }
      if (mountedRef.current && streamIdRef.current === streamId) {
        const abortReason = streamAbortReasonRef.current
        const convId = messagesConversationIdRef.current
        // The stream began but ended without a clean `done` event and without an
        // error or explicit abort — i.e. the connection was torn down mid-response.
        // The backend does not persist on mid-stream disconnect, but iOS sometimes
        // keeps the socket alive long enough for the server to finish and save, so
        // do one refetch: adopt the persisted reply if present, else settle locally.
        const needsRecoveryRefetch = (
          streamStarted
            && !sawDoneEvent
            && !sawError
            && abortReason !== 'user_abort'
            && abortReason !== 'unmount'
            && Boolean(convId)
        )
        updateMessageById(assistantMessageId, last => {
          if (abortController.signal.aborted || abortReason || needsRecoveryRefetch) {
            return interruptedAssistantMessage(last)
          }
          return { ...last, streaming: false }
        })
        setStreamingActive(false)
        streamAbortReasonRef.current = null
        onRefresh()
        if (needsRecoveryRefetch) {
          fetchMessages(convId)
        }
      }
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  function handleInputFocus() {
    setKeyboardActive(true)
    scheduleViewportSync('auto')
  }

  function handleInputBlur() {
    window.setTimeout(() => {
      setKeyboardActive(false)
      scheduleViewportSync('auto')
    }, 120)
  }

  return (
    <div className={`chat ${keyboardActive ? 'keyboard-active' : ''}`}>
      <div className="chat-active-user" aria-live="polite">
        <span className="chat-active-user-indicator">
          <span className="chat-active-user-label">You are</span>
          <span className="chat-active-user-name">{userName || 'No user selected'}</span>
        </span>
        {onSignOut && (
          <button
            type="button"
            className="btn btn-small chat-switch-user"
            onClick={onSignOut}
          >
            Switch user
          </button>
        )}
      </div>
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-chat">
            <p>Start a conversation</p>
          </div>
        )}
        {messages.map(msg => (
          <div
            key={msg.id}
            className={`message message-${msg.role} ${msg.error ? 'message-error' : ''}`}
          >
            <div className="message-role">
              {msg.role === 'user' ? 'You' : 'Assistant'}
            </div>
            <div className="message-content">
              {msg.content
                || (msg.interrupted ? 'Response interrupted; send again if needed.' : '')}
              {msg.streaming && <span className="cursor">|</span>}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area" ref={inputAreaRef}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onFocus={handleInputFocus}
          onBlur={handleInputBlur}
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
