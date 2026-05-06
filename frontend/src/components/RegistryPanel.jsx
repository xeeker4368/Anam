import { useRef, useState } from 'react'

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
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="registry-meta-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function artifactMetadata(artifact) {
  return artifact?.metadata && typeof artifact.metadata === 'object'
    ? artifact.metadata
    : {}
}

function shortHash(value) {
  if (!value) return null
  const text = String(value)
  return text.length > 16 ? `${text.slice(0, 12)}...${text.slice(-4)}` : text
}

function formatBytes(value) {
  if (value === null || value === undefined || value === '') return null
  const bytes = Number(value)
  if (!Number.isFinite(bytes)) return value
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ArtifactDetailRow({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="registry-detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ArtifactDetailGroup({ title, children }) {
  const visibleChildren = Array.isArray(children)
    ? children.filter(Boolean)
    : children
  if (Array.isArray(visibleChildren) && visibleChildren.length === 0) return null

  return (
    <div className="registry-detail-group">
      <h4>{title}</h4>
      {visibleChildren}
    </div>
  )
}

function ArtifactDetails({ artifact }) {
  const metadata = artifactMetadata(artifact)

  return (
    <details className="registry-details">
      <summary className="registry-details-summary">Details</summary>
      <div className="registry-detail-grid">
        <ArtifactDetailGroup title="File">
          <ArtifactDetailRow label="Filename" value={metadata.filename} />
          <ArtifactDetailRow label="Safe filename" value={metadata.safe_filename} />
          <ArtifactDetailRow label="MIME" value={metadata.mime_type} />
          <ArtifactDetailRow label="Size" value={formatBytes(metadata.size_bytes)} />
          <ArtifactDetailRow label="SHA-256" value={shortHash(metadata.sha256)} />
          <ArtifactDetailRow label="Path" value={artifact.path} />
        </ArtifactDetailGroup>

        <ArtifactDetailGroup title="Source / Provenance">
          <ArtifactDetailRow label="Authority" value={metadata.authority} />
          <ArtifactDetailRow label="Source" value={artifact.source} />
          <ArtifactDetailRow label="Created by" value={metadata.created_by} />
          <ArtifactDetailRow label="Source type" value={metadata.source_type} />
          <ArtifactDetailRow label="Conversation" value={artifact.source_conversation_id} />
          <ArtifactDetailRow label="Message" value={artifact.source_message_id} />
          <ArtifactDetailRow label="Tool" value={artifact.source_tool_name} />
          <ArtifactDetailRow label="Revision of" value={artifact.revision_of} />
        </ArtifactDetailGroup>

        <ArtifactDetailGroup title="Indexing">
          <ArtifactDetailRow label="Indexing" value={metadata.indexing_status} />
          <ArtifactDetailRow label="Type" value={artifact.artifact_type} />
          <ArtifactDetailRow label="Status" value={artifact.status} />
          <ArtifactDetailRow label="Created" value={formatDate(artifact.created_at)} />
          <ArtifactDetailRow label="Updated" value={formatDate(artifact.updated_at)} />
        </ArtifactDetailGroup>
      </div>
    </details>
  )
}

function ArtifactCard({ artifact }) {
  const metadata = artifactMetadata(artifact)
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
        {metadata.authority && <RegistryBadge>{metadata.authority}</RegistryBadge>}
        {metadata.indexing_status && (
          <RegistryBadge tone={metadata.indexing_status}>
            {metadata.indexing_status}
          </RegistryBadge>
        )}
      </div>
      <RegistryMeta label="Path" value={artifact.path} />
      <RegistryMeta label="Created" value={formatDate(artifact.created_at)} />
      <RegistryMeta label="Updated" value={formatDate(artifact.updated_at)} />
      <ArtifactDetails artifact={artifact} />
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

function UploadSummary({ result }) {
  if (!result) return null

  const artifact = result.artifact || {}
  const file = result.file || {}
  const indexing = result.indexing || {}
  const metadataOnly = indexing.status === 'metadata_only'

  return (
    <div className="artifact-upload-result">
      <div className="artifact-upload-result-title">
        <strong>{artifact.title || 'Uploaded artifact'}</strong>
        <RegistryBadge tone={metadataOnly ? 'draft' : 'active'}>
          {indexing.status || 'indexed'}
        </RegistryBadge>
      </div>
      <p>Saved as source material. Indexed for retrieval.</p>
      {metadataOnly && (
        <p className="artifact-upload-note">
          This file was saved and metadata-indexed; content extraction is not supported yet.
        </p>
      )}
      <div className="artifact-upload-meta">
        <RegistryMeta label="File" value={file.path || artifact.path} />
        <RegistryMeta label="Events" value={indexing.event_chunks_written} />
        <RegistryMeta label="Chunks" value={indexing.content_chunks_written} />
      </div>
    </div>
  )
}

function ArtifactUpload({ uploading, uploadError, uploadResult, onUpload }) {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [localError, setLocalError] = useState(null)
  const fileInputRef = useRef(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLocalError(null)
    if (!file) {
      setLocalError('Choose a file to upload.')
      return
    }

    try {
      await onUpload({ file, title, description })
      setFile(null)
      setTitle('')
      setDescription('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch {
      // App-level upload state renders the backend error.
    }
  }

  return (
    <section className="artifact-upload">
      <div className="artifact-upload-header">
        <h2>Upload Artifact</h2>
        <span>source_material</span>
      </div>
      <form onSubmit={handleSubmit}>
        <label className="artifact-upload-field">
          <span>File</span>
          <input
            ref={fileInputRef}
            type="file"
            onChange={e => setFile(e.target.files?.[0] || null)}
            disabled={uploading}
          />
        </label>
        <div className="artifact-upload-row">
          <label className="artifact-upload-field">
            <span>Title</span>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              disabled={uploading}
              placeholder="Optional"
            />
          </label>
        </div>
        <label className="artifact-upload-field">
          <span>Description</span>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            disabled={uploading}
            rows={3}
            placeholder="Optional context for retrieval"
          />
        </label>
        <button type="submit" className="btn btn-small" disabled={uploading || !file}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </form>
      {(localError || uploadError) && (
        <p className="artifact-upload-error">{localError || uploadError}</p>
      )}
      <UploadSummary result={uploadResult} />
    </section>
  )
}

function RegistryPanel({
  artifacts,
  openLoops,
  loading,
  error,
  uploading,
  uploadError,
  uploadResult,
  onUpload,
  onRefresh,
}) {
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

      <ArtifactUpload
        uploading={uploading}
        uploadError={uploadError}
        uploadResult={uploadResult}
        onUpload={onUpload}
      />

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
