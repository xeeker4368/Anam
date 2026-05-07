import { useState } from 'react'

const REVIEW_STATUSES = ['open', 'reviewed', 'dismissed', 'resolved']
const REVIEW_CATEGORIES = [
  'research',
  'follow_up',
  'contradiction',
  'correction',
  'artifact',
  'tool_failure',
  'memory',
  'decision',
  'safety',
  'other',
]
const REVIEW_PRIORITIES = ['low', 'normal', 'high']

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
  if (value === 'unavailable' || value === 'not_configured') return 'warn'
  if (value === 'staged_only') return 'neutral'
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

function humanize(value) {
  if (value === null || value === undefined || value === '') return 'n/a'
  return String(value).replaceAll('_', ' ')
}

function capabilityGroup(capability) {
  if (capability?.requires_approval === true || capability?.mode === 'staged_only') {
    return 'restricted'
  }
  if (capability?.implemented === false) {
    return 'planned'
  }
  if (
    capability?.status === 'unavailable' ||
    capability?.status === 'not_configured' ||
    capability?.available === false ||
    capability?.configured === false ||
    capability?.enabled === false
  ) {
    return 'config'
  }
  if (
    capability?.implemented === true &&
    capability?.enabled === true &&
    capability?.available === true &&
    capability?.status === 'available'
  ) {
    return 'active'
  }
  return 'config'
}

function groupCapabilities(capabilityData) {
  const groups = {
    active: [],
    config: [],
    planned: [],
    restricted: [],
  }
  Object.values(capabilityData || {}).forEach(capability => {
    groups[capabilityGroup(capability)].push(capability)
  })
  return groups
}

function CapabilityBadge({ value, label }) {
  return (
    <SystemBadge
      value={value}
      label={label || humanize(value)}
    />
  )
}

function CapabilityCard({ capability }) {
  const label = capability?.label || capability?.key || 'Unknown capability'
  return (
    <article className="system-capability-card">
      <div className="system-capability-header">
        <h4>{label}</h4>
        <CapabilityBadge value={capability?.status} />
      </div>
      <div className="system-capability-badges">
        <CapabilityBadge value={capability?.mode} />
        <CapabilityBadge
          value={capability?.enabled}
          label={capability?.enabled ? 'enabled' : 'disabled'}
        />
        <CapabilityBadge
          value={capability?.available}
          label={capability?.available ? 'available' : 'unavailable'}
        />
        {capability?.configured !== undefined && (
          <CapabilityBadge
            value={capability.configured}
            label={capability.configured ? 'configured' : 'not configured'}
          />
        )}
        {capability?.requires_approval && (
          <CapabilityBadge value="not_configured" label="approval required" />
        )}
        {capability?.real_time && <CapabilityBadge value="available" label="real time" />}
        {capability?.source_of_truth && (
          <CapabilityBadge value="available" label="source of truth" />
        )}
      </div>
      {capability?.reason && (
        <p className="system-capability-note">
          <strong>Reason:</strong> {humanize(capability.reason)}
        </p>
      )}
      {capability?.notes && (
        <p className="system-capability-note">{capability.notes}</p>
      )}
    </article>
  )
}

function CapabilityGroup({ title, capabilities }) {
  if (!capabilities || capabilities.length === 0) return null

  return (
    <div className="system-capability-group">
      <div className="registry-section-header">
        <h2>{title}</h2>
        <span>{capabilities.length}</span>
      </div>
      <div className="system-capability-list">
        {capabilities.map(capability => (
          <CapabilityCard
            key={capability.key || capability.label}
            capability={capability}
          />
        ))}
      </div>
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

function ReviewFilterSelect({ label, value, options, onChange }) {
  return (
    <label className="system-review-field">
      <span>{label}</span>
      <select value={value || ''} onChange={e => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map(option => (
          <option key={option} value={option}>{humanize(option)}</option>
        ))}
      </select>
    </label>
  )
}

function ReviewItemSource({ item }) {
  const sourceRows = [
    ['Source type', item.source_type],
    ['Conversation', item.source_conversation_id],
    ['Message', item.source_message_id],
    ['Artifact', item.source_artifact_id],
    ['Tool', item.source_tool_name],
  ].filter(([, value]) => value)

  if (sourceRows.length === 0) return null

  return (
    <div className="system-review-source">
      {sourceRows.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  )
}

function ReviewItemCard({ item, updatingId, onStatusUpdate }) {
  const isUpdating = updatingId === item.item_id

  return (
    <article className="system-review-item">
      <div className="system-review-item-header">
        <h4>{item.title}</h4>
        <SystemBadge value={item.status} label={humanize(item.status)} />
      </div>
      {item.description && (
        <p className="system-review-description">{item.description}</p>
      )}
      <div className="system-review-badges">
        <SystemBadge value={item.priority} label={humanize(item.priority)} />
        <SystemBadge value={item.category} label={humanize(item.category)} />
        <SystemBadge value="neutral" label={formatDate(item.created_at)} />
      </div>
      <ReviewItemSource item={item} />
      <div className="system-review-actions" aria-label={`Update status for ${item.title}`}>
        {REVIEW_STATUSES.map(status => (
          <button
            key={status}
            type="button"
            className="btn btn-small"
            disabled={isUpdating || item.status === status}
            onClick={() => onStatusUpdate(item.item_id, status)}
          >
            {humanize(status)}
          </button>
        ))}
      </div>
    </article>
  )
}

function ReviewCreateForm({ submitting, onCreate }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('other')
  const [priority, setPriority] = useState('normal')

  async function handleSubmit(e) {
    e.preventDefault()
    const trimmedTitle = title.trim()
    if (!trimmedTitle || submitting) return

    await onCreate({
      title: trimmedTitle,
      description: description.trim(),
      category,
      priority,
    })
    setTitle('')
    setDescription('')
    setCategory('other')
    setPriority('normal')
  }

  return (
    <form className="system-review-form" onSubmit={handleSubmit}>
      <div className="system-review-form-grid">
        <label className="system-review-field">
          <span>Title</span>
          <input
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Manual review item"
            required
          />
        </label>
        <label className="system-review-field">
          <span>Category</span>
          <select value={category} onChange={e => setCategory(e.target.value)}>
            {REVIEW_CATEGORIES.map(option => (
              <option key={option} value={option}>{humanize(option)}</option>
            ))}
          </select>
        </label>
        <label className="system-review-field">
          <span>Priority</span>
          <select value={priority} onChange={e => setPriority(e.target.value)}>
            {REVIEW_PRIORITIES.map(option => (
              <option key={option} value={option}>{humanize(option)}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="system-review-field">
        <span>Description</span>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Optional context for the operator"
          rows="3"
        />
      </label>
      <div className="system-review-form-footer">
        <span>Created by: operator</span>
        <button type="submit" className="btn btn-small" disabled={submitting || !title.trim()}>
          {submitting ? 'Adding...' : 'Add item'}
        </button>
      </div>
    </form>
  )
}

function ReviewQueueSection({
  items,
  filters,
  loading,
  error,
  submitting,
  updatingId,
  onRefresh,
  onFiltersChange,
  onCreate,
  onStatusUpdate,
}) {
  const reviewItems = Array.isArray(items) ? items : []
  const activeFilters = filters || {}

  function updateFilter(key, value) {
    onFiltersChange({
      ...activeFilters,
      [key]: value,
    })
  }

  return (
    <SystemSection title="Review Queue">
      <div className="system-review-panel">
        <div className="system-review-toolbar">
          <div className="system-review-filters">
            <ReviewFilterSelect
              label="Status"
              value={activeFilters.status}
              options={REVIEW_STATUSES}
              onChange={value => updateFilter('status', value)}
            />
            <ReviewFilterSelect
              label="Category"
              value={activeFilters.category}
              options={REVIEW_CATEGORIES}
              onChange={value => updateFilter('category', value)}
            />
            <ReviewFilterSelect
              label="Priority"
              value={activeFilters.priority}
              options={REVIEW_PRIORITIES}
              onChange={value => updateFilter('priority', value)}
            />
          </div>
          <button type="button" className="btn btn-small" onClick={onRefresh} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {error && <p className="system-error">{error}</p>}

        <ReviewCreateForm submitting={submitting} onCreate={onCreate} />

        <div className="system-review-list">
          {loading && <p className="debug-note">Loading review queue...</p>}
          {!loading && reviewItems.length === 0 && (
            <p className="system-empty">No review items match these filters.</p>
          )}
          {reviewItems.map(item => (
            <ReviewItemCard
              key={item.item_id}
              item={item}
              updatingId={updatingId}
              onStatusUpdate={onStatusUpdate}
            />
          ))}
        </div>
      </div>
    </SystemSection>
  )
}

function SystemPanel({
  health,
  memory,
  capabilities,
  loading,
  error,
  onRefresh,
  reviewItems,
  reviewFilters,
  reviewLoading,
  reviewError,
  reviewSubmitting,
  reviewUpdatingId,
  onReviewRefresh,
  onReviewFiltersChange,
  onReviewCreate,
  onReviewStatusUpdate,
}) {
  const audit = memory?.audit || {}
  const capabilityData = capabilities?.capabilities || {}
  const capabilityGroups = groupCapabilities(capabilityData)

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

      <ReviewQueueSection
        items={reviewItems}
        filters={reviewFilters}
        loading={reviewLoading}
        error={reviewError}
        submitting={reviewSubmitting}
        updatingId={reviewUpdatingId}
        onRefresh={onReviewRefresh}
        onFiltersChange={onReviewFiltersChange}
        onCreate={onReviewCreate}
        onStatusUpdate={onReviewStatusUpdate}
      />

      {capabilities && (
        <SystemSection title="Capabilities">
          <CapabilityGroup
            title="Active / Available"
            capabilities={capabilityGroups.active}
          />
          <CapabilityGroup
            title="Config Needed / Unavailable"
            capabilities={capabilityGroups.config}
          />
          <CapabilityGroup
            title="Planned / Not Implemented"
            capabilities={capabilityGroups.planned}
          />
          <CapabilityGroup
            title="Restricted / Requires Approval"
            capabilities={capabilityGroups.restricted}
          />
        </SystemSection>
      )}
    </div>
  )
}

export default SystemPanel
