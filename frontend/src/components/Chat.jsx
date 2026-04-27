import { useState, useEffect, useRef } from 'react'

function Chat({ conversationId, userId, onConversationCreated, onDebugData, onRefresh }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const isStreamingRef = useRef(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

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