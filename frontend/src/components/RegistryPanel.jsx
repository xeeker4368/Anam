function formatDate(value) {
  if (!value) return 'n/a'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function RegistryBadge({ children, tone = 'neutral' }) {
  return <span className={`registry-badge registry-badge-${tone}`}>{children}</span>
}

function RegistryMeta({ label, value }) {
  if (!value) return null
  return (
    <div className="registry-meta-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ArtifactCard({ artifact }) {
  return (
    <article className="registry-card">
      <div className="registry-card-header">
        <h3>{artifact.title || 'Untitled artifact'}</h3>
        <RegistryBadge tone={artifact.status || 'neutral'}>
          {artifact.status || 'unknown'}
        </RegistryBadge>
      </div>
      <div className="registry-badge-row">
        <RegistryBadge>{artifact.artifact_type || 'generic'}</RegistryBadge>
      </div>
      <RegistryMeta label="Path" value={artifact.path} />
      <RegistryMeta label="Created" value={formatDate(artifact.created_at)} />
      <RegistryMeta label="Updated" value={formatDate(artifact.updated_at)} />
    </article>
  )
}

function OpenLoopCard({ openLoop }) {
  return (
    <article className="registry-card">
      <div className="registry-card-header">
        <h3>{openLoop.title || 'Untitled open loop'}</h3>
        <RegistryBadge tone={openLoop.status || 'neutral'}>
          {openLoop.status || 'unknown'}
        </RegistryBadge>
      </div>
      <div className="registry-badge-row">
        <RegistryBadge>{openLoop.loop_type || 'generic'}</RegistryBadge>
        <RegistryBadge tone={openLoop.priority || 'neutral'}>
          {openLoop.priority || 'normal'}
        </RegistryBadge>
      </div>
      <RegistryMeta label="Artifact" value={openLoop.related_artifact_id} />
      <RegistryMeta label="Next" value={openLoop.next_action} />
      <RegistryMeta label="Created" value={formatDate(openLoop.created_at)} />
      <RegistryMeta label="Updated" value={formatDate(openLoop.updated_at)} />
    </article>
  )
}

function RegistrySection({ title, count, emptyText, children }) {
  return (
    <section className="registry-section">
      <div className="registry-section-header">
        <h2>{title}</h2>
        <span>{count}</span>
      </div>
      {count === 0 ? (
        <p className="empty-text">{emptyText}</p>
      ) : (
        <div className="registry-list">{children}</div>
      )}
    </section>
  )
}

function RegistryPanel({ artifacts, openLoops, loading, error, onRefresh }) {
  return (
    <div className="registry-content">
      <div className="registry-title-row">
        <h2>Registry</h2>
        <button type="button" className="btn btn-small" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {loading && <p className="debug-note">Loading registry records...</p>}
      {error && <p className="registry-error">{error}</p>}

      <RegistrySection
        title="Artifacts"
        count={artifacts.length}
        emptyText="No artifacts recorded yet."
      >
        {artifacts.map(artifact => (
          <ArtifactCard key={artifact.artifact_id} artifact={artifact} />
        ))}
      </RegistrySection>

      <RegistrySection
        title="Open Loops"
        count={openLoops.length}
        emptyText="No open loops recorded yet."
      >
        {openLoops.map(openLoop => (
          <OpenLoopCard key={openLoop.open_loop_id} openLoop={openLoop} />
        ))}
      </RegistrySection>
    </div>
  )
}

export default RegistryPanel
