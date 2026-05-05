function formatDate(value) {
  if (!value) return 'n/a'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatValue(value) {
  if (value === true) return 'yes'
  if (value === false) return 'no'
  if (value === null || value === undefined || value === '') return 'n/a'
  if (Array.isArray(value)) return value.length === 0 ? 'none' : value.join(', ')
  return String(value)
}

function statusTone(value) {
  if (value === true || value === 'ok' || value === 'available') return 'ok'
  if (value === false || value === 'disabled' || value === 'not_implemented') return 'muted'
  return 'neutral'
}

function SystemBadge({ value, label }) {
  const text = label || formatValue(value)
  return <span className={`system-badge system-badge-${statusTone(value)}`}>{text}</span>
}

function SystemMetric({ label, value, badge = false }) {
  return (
    <div className="system-metric">
      <span>{label}</span>
      {badge ? <SystemBadge value={value} /> : <strong>{formatValue(value)}</strong>}
    </div>
  )
}

function SystemSection({ title, children }) {
  return (
    <section className="system-section">
      <h3>{title}</h3>
      <div className="system-card">{children}</div>
    </section>
  )
}

function CapabilityRow({ label, capability }) {
  const enabled = capability?.available ?? capability?.enabled ?? false
  const details = []
  if (capability?.configured !== undefined) {
    details.push(`configured: ${formatValue(capability.configured)}`)
  }
  if (capability?.source) details.push(`source: ${capability.source}`)
  if (capability?.status) details.push(capability.status)

  return (
    <div className="system-capability-row">
      <div>
        <strong>{label}</strong>
        {details.length > 0 && <span>{details.join(' · ')}</span>}
      </div>
      <SystemBadge value={enabled} label={enabled ? 'available' : 'disabled'} />
    </div>
  )
}

function WarningList({ warnings }) {
  if (!Array.isArray(warnings) || warnings.length === 0) {
    return <p className="system-empty">No warnings reported.</p>
  }

  return (
    <ul className="system-warning-list">
      {warnings.map((warning, index) => (
        <li key={`${index}-${warning}`}>{warning}</li>
      ))}
    </ul>
  )
}

function SystemPanel({ health, memory, capabilities, loading, error, onRefresh }) {
  const audit = memory?.audit || {}
  const capabilityData = capabilities?.capabilities || {}

  return (
    <div className="system-content">
      <div className="system-title-row">
        <h2>System</h2>
        <button type="button" className="btn btn-small" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {loading && <p className="debug-note">Loading system status...</p>}
      {error && <p className="system-error">{error}</p>}
      {!health && !memory && !capabilities && !loading && !error && (
        <p className="debug-note">Open or refresh this panel to load system status.</p>
      )}

      {health && (
        <SystemSection title="Health">
          <SystemMetric label="API" value={health.api_ok} badge />
          <SystemMetric label="Project" value={health.project} />
          <SystemMetric label="Timestamp" value={formatDate(health.timestamp)} />
          <SystemMetric label="Working DB" value={health.working_db?.ok} badge />
          <SystemMetric label="Archive DB" value={health.archive_db?.ok} badge />
          <SystemMetric label="Chroma" value={health.chroma?.ok} badge />
          <SystemMetric label="Chroma chunks" value={health.chroma?.count} />
          {health.chroma?.error && <SystemMetric label="Chroma error" value={health.chroma.error} />}
          <SystemMetric label="Backup dir" value={health.backups?.backup_dir_exists} badge />
          <SystemMetric label="Latest backup" value={health.backups?.latest_backup?.name} />
          <SystemMetric
            label="Backup created"
            value={formatDate(health.backups?.latest_backup?.created_at)}
          />
          <SystemMetric label="SearXNG" value={health.external?.searxng?.configured} badge />
          <SystemMetric label="SearXNG URL" value={health.external?.searxng?.url} />
          <SystemMetric
            label="Moltbook token"
            value={health.external?.moltbook_token_configured}
            badge
          />
          <SystemMetric label="Skills" value={health.skills?.active_skill_count} />
          <SystemMetric label="Tools" value={health.skills?.active_tool_count} />
        </SystemSection>
      )}

      {memory && (
        <SystemSection title="Memory">
          {memory.ok === false ? (
            <SystemMetric label="Audit error" value={memory.error} />
          ) : (
            <>
              <SystemMetric label="Working messages" value={audit.working_message_count} />
              <SystemMetric label="Archive messages" value={audit.archive_message_count} />
              <SystemMetric label="Message parity" value={audit.message_id_parity_ok} badge />
              <SystemMetric label="Conversations" value={audit.total_conversations} />
              <SystemMetric label="Active" value={audit.active_conversation_count} />
              <SystemMetric label="Ended" value={audit.ended_conversation_count} />
              <SystemMetric label="Ended unchunked" value={audit.ended_unchunked_count} />
              <SystemMetric label="FTS chunks" value={audit.fts_chunk_count} />
              <SystemMetric label="Chroma chunks" value={audit.chroma_chunk_count} />
              <SystemMetric label="FTS/Chroma match" value={audit.fts_chroma_count_match} badge />
              <SystemMetric
                label="Missing FTS chunks"
                value={audit.chunked_conversations_missing_fts_chunks}
              />
              <div className="system-warning-block">
                <span>Warnings</span>
                <WarningList warnings={audit.warnings} />
              </div>
            </>
          )}
        </SystemSection>
      )}

      {capabilities && (
        <SystemSection title="Capabilities">
          <div className="system-capability-list">
            <CapabilityRow label="Memory Search" capability={capabilityData.memory_search} />
            <CapabilityRow label="Web Search" capability={capabilityData.web_search} />
            <CapabilityRow label="Web Fetch" capability={capabilityData.web_fetch} />
            <CapabilityRow label="Moltbook Read-Only" capability={capabilityData.moltbook_read_only} />
            <CapabilityRow label="Backups" capability={capabilityData.backups} />
            <CapabilityRow label="File Uploads" capability={capabilityData.file_uploads} />
            <CapabilityRow label="Image Generation" capability={capabilityData.image_generation} />
            <CapabilityRow
              label="Autonomous Research"
              capability={capabilityData.autonomous_research}
            />
            <CapabilityRow label="Speech" capability={capabilityData.speech} />
            <CapabilityRow label="Vision" capability={capabilityData.vision} />
            <CapabilityRow label="Write Actions" capability={capabilityData.write_actions} />
            <CapabilityRow label="Self-Modification" capability={capabilityData.self_modification} />
          </div>
        </SystemSection>
      )}
    </div>
  )
}

export default SystemPanel
