import { useState } from 'react'

function DebugSection({ title, defaultOpen, children }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section className="debug-section">
      <button
        type="button"
        className="debug-section-toggle"
        onClick={() => setOpen(value => !value)}
      >
        <span className={`debug-caret ${open ? 'open' : ''}`}>›</span>
        <span>{title}</span>
      </button>
      {open && <div className="debug-section-body">{children}</div>}
    </section>
  )
}

function stringify(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function compact(value, maxLength = 220) {
  const text = stringify(value)
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text
}

function ToolEvent({ event, index }) {
  const argsText = stringify(event.arguments || {})
  const queryOrArgs = event.query || compact(event.arguments || {}, 120)
  const raw = {
    call: event.raw_call,
    result: event.raw_result,
  }

  return (
    <div className="debug-tool-card">
      <div className="tool-header">
        <span className="tool-name">{event.name || `tool_${index + 1}`}</span>
        <span className={`tool-status tool-status-${event.status || 'pending'}`}>
          {event.status || 'pending'}
        </span>
      </div>

      {queryOrArgs && (
        <div className="tool-line">
          <span className="tool-label">Args</span>
          <span className="tool-value">{queryOrArgs}</span>
        </div>
      )}

      {event.result_summary && (
        <div className="tool-result-summary">{event.result_summary}</div>
      )}

      <details className="debug-details">
        <summary>Full arguments</summary>
        <pre>{argsText}</pre>
      </details>
      {event.result != null && (
        <details className="debug-details">
          <summary>Full result</summary>
          <pre>{stringify(event.result)}</pre>
        </details>
      )}
      <details className="debug-details">
        <summary>Raw JSON</summary>
        <pre>{stringify(raw)}</pre>
      </details>
    </div>
  )
}

function DebugPanel({ data }) {
  if (!data) {
    return (
      <div className="debug-content">
        <h2>Debug</h2>
        <p className="empty-text">Send a message to see retrieval debug info</p>
      </div>
    )
  }

  const toolEvents = data.tool_events || []
  const rawEvents = data.raw_events || []
  const lastTool = toolEvents.length > 0 ? toolEvents[toolEvents.length - 1] : null
  const memoryDefaultOpen = toolEvents.length === 0

  return (
    <div className="debug-content">
      <h2>Debug</h2>

      <DebugSection title="Overview" defaultOpen={true}>
        <div className="overview-grid">
          <div className="overview-row">
            <span>Retrieved chunks</span>
            <strong>{data.chunks_retrieved ?? 0}</strong>
          </div>
          {data.system_prompt_length != null && (
            <div className="overview-row">
              <span>Prompt chars</span>
              <strong>{data.system_prompt_length.toLocaleString()}</strong>
            </div>
          )}
          {data.history_message_count != null && (
            <div className="overview-row">
              <span>History messages</span>
              <strong>{data.history_message_count}</strong>
            </div>
          )}
          <div className="overview-row">
            <span>Tool events</span>
            <strong>{toolEvents.length}</strong>
          </div>
          {lastTool && (
            <div className="overview-row">
              <span>Last tool</span>
              <strong>{lastTool.name}</strong>
            </div>
          )}
          {data.conversation_id && (
            <div className="overview-row">
              <span>Conversation</span>
              <strong className="debug-id">{data.conversation_id.substring(0, 8)}...</strong>
            </div>
          )}
        </div>
      </DebugSection>

      <DebugSection
        key={`tool-calls-${toolEvents.length > 0 ? 'present' : 'empty'}`}
        title="Tool Calls"
        defaultOpen={toolEvents.length > 0}
      >
        {toolEvents.length === 0 ? (
          <p className="debug-note">No tool calls recorded for this turn.</p>
        ) : (
          toolEvents.map((event, index) => (
            <ToolEvent key={index} event={event} index={index} />
          ))
        )}
      </DebugSection>

      <DebugSection
        key={`memory-retrieval-${memoryDefaultOpen ? 'open' : 'collapsed'}`}
        title="Memory Retrieval"
        defaultOpen={memoryDefaultOpen}
      >
        {data.retrieval_skipped ? (
          <p className="debug-note">Skipped (greeting detected)</p>
        ) : (
          <>
            <p>{data.chunks_retrieved ?? 0} chunks retrieved</p>
            {data.system_prompt_length != null && (
              <p>System prompt: {data.system_prompt_length.toLocaleString()} chars</p>
            )}
            {data.history_message_count != null && (
              <p>History: {data.history_message_count} messages</p>
            )}
          </>
        )}

        {!data.retrieval_skipped && data.retrieved_chunks?.length > 0 && (
          <div className="debug-chunk-list">
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
      </DebugSection>

      <DebugSection title="Raw Debug Data" defaultOpen={false}>
        {rawEvents.length > 0 && (
          <details className="debug-details" open>
            <summary>Raw events</summary>
            <pre>{stringify(rawEvents)}</pre>
          </details>
        )}
        <details className="debug-details">
          <summary>Full debug object</summary>
          <pre>{stringify(data)}</pre>
        </details>
      </DebugSection>
    </div>
  )
}

export default DebugPanel
