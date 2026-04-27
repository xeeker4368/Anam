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
