import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, readErrorMessage } from '../api'

function Chat({
  conversationId,
  userId,
  userName,
  users = [],
  onUserChange,
  onConversationCreated,
  onDebugData,
  onRefresh,
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const isStreamingRef = useRef(false)
  const debugRef = useRef(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const mountedRef = useRef(false)
  const streamAbortRef = useRef(null)
  const streamReaderRef = useRef(null)
  const streamIdRef = useRef(0)
  const messageIdCounterRef = useRef(0)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      streamAbortRef.current?.abort()
      streamReaderRef.current?.cancel().catch(() => {})
      streamReaderRef.current = null
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

      setMessages(data.map((m, index) => ({
        id: messageIdFromServer(m, index),
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      })))
    } catch (e) {
      console.warn('Failed to fetch messages:', e)
    }
  }, [messageIdFromServer])

  // Load existing messages when conversationId changes
  // Skip if we're mid-stream — streaming manages its own message state
  useEffect(() => {
    if (conversationId && !isStreamingRef.current) {
      fetchMessages(conversationId)
    } else if (!conversationId) {
      setMessages([])
    }
  }, [conversationId, fetchMessages])

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

  async function sendMessage() {
    const text = input.trim()
    if (!text) return
    if (isStreamingRef.current) {
      streamAbortRef.current?.abort()
      return
    }

    setInput('')
    setIsStreaming(true)
    isStreamingRef.current = true
    debugRef.current = null
    streamAbortRef.current?.abort()
    const streamId = streamIdRef.current + 1
    streamIdRef.current = streamId
    const abortController = new AbortController()
    streamAbortRef.current = abortController
    const requestStart = performance.now()
    let firstTokenSeen = false
    let reader = null
    let streamDone = false
    const userMessageId = nextMessageId('user')
    const assistantMessageId = nextMessageId('assistant')

    // Add user message to display immediately
    setMessages(prev => [...prev, { id: userMessageId, role: 'user', content: text }])

    // Add empty assistant message that will be filled by streaming
    setMessages(prev => [
      ...prev,
      {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        streaming: true,
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
          error: true,
        }))
        return
      }

      reader = resp.body.getReader()
      streamReaderRef.current = reader
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
              if (data.conversation_id && data.conversation_id !== conversationId) {
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
              updateMessageById(assistantMessageId, last => ({ ...last, streaming: false }))
            } else if (data.type === 'error') {
              appendRawEvent(data)
              updateMessageById(assistantMessageId, last => ({
                ...last,
                content: data.message,
                streaming: false,
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
        return
      }
      console.error('Stream failed:', e)
      updateMessageById(assistantMessageId, last => ({
        ...last,
        content: `Connection error: ${e.message}`,
        streaming: false,
        error: true,
      }))
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
        updateMessageById(assistantMessageId, last => ({ ...last, streaming: false }))
        setIsStreaming(false)
        isStreamingRef.current = false
        onRefresh()
      }
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat">
      <div className="chat-active-user" aria-live="polite">
        <span className="chat-active-user-label">Active household user</span>
        {users.length > 1 && onUserChange ? (
          <select
            className="chat-user-select"
            value={userId || ''}
            onChange={e => onUserChange(e.target.value)}
            aria-label="Active household user"
          >
            {users.map(user => (
              <option key={user.id} value={user.id}>{user.name}</option>
            ))}
          </select>
        ) : (
          <span className="chat-active-user-name">{userName || 'No user selected'}</span>
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
