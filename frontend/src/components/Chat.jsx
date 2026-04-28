import { useState, useEffect, useRef } from 'react'

function Chat({ conversationId, userId, onConversationCreated, onDebugData, onRefresh }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const isStreamingRef = useRef(false)
  const debugRef = useRef(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

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

  // Load existing messages when conversationId changes
  // Skip if we're mid-stream — streaming manages its own message state
  useEffect(() => {
    if (conversationId && !isStreamingRef.current) {
      fetchMessages(conversationId)
    } else if (!conversationId) {
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
    isStreamingRef.current = true
    debugRef.current = null
    const requestStart = performance.now()
    let firstTokenSeen = false

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
              if (data.conversation_id && !conversationId) {
                onConversationCreated(data.conversation_id)
              }
            } else if (data.type === 'debug_update') {
              mergeDebugTimings(data.timings || {}, data)
            } else if (data.type === 'tool_call') {
              recordToolCall(data)
            } else if (data.type === 'tool_result') {
              recordToolResult(data)
            } else if (data.type === 'token') {
              if (!firstTokenSeen) {
                firstTokenSeen = true
                mergeDebugTimings({
                  request_start_to_first_token_ms: elapsedMs(requestStart),
                })
              }
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
              const doneAt = performance.now()
              mergeDebugTimings({
                request_start_to_done_ms: elapsedMs(requestStart, doneAt),
                frontend_stream_total_ms: elapsedMs(requestStart, doneAt),
              }, data)
              // Mark streaming complete
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = { ...last, streaming: false }
                return updated
              })
            } else if (data.type === 'error') {
              appendRawEvent(data)
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
            } else {
              appendRawEvent(data)
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
    isStreamingRef.current = false
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
