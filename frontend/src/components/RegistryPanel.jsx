import { useEffect, useRef, useState } from 'react'
import { apiFetch, readErrorMessage } from '../api'

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

function sourceRoleFromAuthority(authority) {
  const mapping = {
    source_material: 'uploaded_source',
    draft: 'draft',
    log: 'log',
    correction: 'correction',
    current_project_state: 'current_project_state',
    operational_guidance: 'runtime_guidance',
    unknown: 'unknown',
  }
  return mapping[authority || 'unknown'] || 'unknown'
}

function humanizeSourceValue(value) {
  const labels = {
    user_upload: 'User upload',
    generated: 'Generated',
    autonomous_research: 'Autonomous research',
    runtime: 'Runtime',
    conversation: 'Conversation',
    tool: 'Tool',
    system: 'System',
    uploaded_source: 'Uploaded source',
    generated_artifact: 'Generated artifact',
    research_reference: 'Research reference',
    runtime_guidance: 'Runtime guidance',
    current_project_state: 'Current project state',
    correction: 'Correction',
    draft: 'Draft',
    log: 'Log',
    unknown: 'Unknown',
    uploaded_image: 'Uploaded image',
    screenshot: 'Screenshot',
    generated_image: 'Generated image',
  }
  return labels[value] || String(value || 'Unknown').replaceAll('_', ' ')
}

function artifactSourceRole(metadata) {
  return metadata.source_role || sourceRoleFromAuthority(metadata.authority)
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
          <ArtifactDetailRow
            label="Source role"
            value={humanizeSourceValue(artifactSourceRole(metadata))}
          />
          <ArtifactDetailRow
            label="Origin"
            value={humanizeSourceValue(metadata.origin)}
          />
          <ArtifactDetailRow label="Source" value={artifact.source} />
          <ArtifactDetailRow label="Created by" value={metadata.created_by} />
          <ArtifactDetailRow label="Source type" value={metadata.source_type} />
          <ArtifactDetailRow label="Conversation" value={artifact.source_conversation_id} />
          <ArtifactDetailRow label="Message" value={artifact.source_message_id} />
          <ArtifactDetailRow label="Tool" value={artifact.source_tool_name} />
          <ArtifactDetailRow label="Revision of" value={artifact.revision_of} />
          <ArtifactDetailRow label="Revised by" value={
            artifact.revised_by_count === undefined
              ? null
              : `${artifact.revised_by_count} artifact(s)`
          } />
        </ArtifactDetailGroup>

        <ArtifactDetailGroup title="Media">
          <ArtifactDetailRow
            label="Media kind"
            value={metadata.media_kind ? humanizeSourceValue(metadata.media_kind) : null}
          />
          <ArtifactDetailRow label="Source user" value={metadata.source_user_id} />
          <ArtifactDetailRow label="Source artifact" value={metadata.source_artifact_id} />
          <ArtifactDetailRow label="Prompt" value={metadata.prompt} />
          <ArtifactDetailRow label="Negative prompt" value={metadata.negative_prompt} />
          <ArtifactDetailRow label="Generation backend" value={metadata.generation_backend} />
          <ArtifactDetailRow label="Generation model" value={metadata.generation_model} />
          <ArtifactDetailRow label="Observed description" value={metadata.observed_description} />
          <ArtifactDetailRow label="Uncertainty" value={metadata.uncertainty_label} />
          <ArtifactDetailRow label="Interpretation source" value={metadata.interpretation_source} />
          <ArtifactDetailRow
            label="Human confirmed"
            value={
              metadata.human_confirmed === undefined
                ? null
                : String(Boolean(metadata.human_confirmed))
            }
          />
          <ArtifactDetailRow label="Intended use" value={metadata.intended_use} />
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
        {(metadata.source_role || metadata.authority) && (
          <RegistryBadge>{humanizeSourceValue(artifactSourceRole(metadata))}</RegistryBadge>
        )}
        {metadata.indexing_status && (
          <RegistryBadge tone={metadata.indexing_status}>
            {metadata.indexing_status}
          </RegistryBadge>
        )}
        {metadata.media_kind && (
          <RegistryBadge>{humanizeSourceValue(metadata.media_kind)}</RegistryBadge>
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
  const metadata = artifactMetadata(artifact)
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
        <RegistryMeta
          label="Media"
          value={metadata.media_kind ? humanizeSourceValue(metadata.media_kind) : null}
        />
        <RegistryMeta label="Events" value={indexing.event_chunks_written} />
        <RegistryMeta label="Chunks" value={indexing.content_chunks_written} />
      </div>
    </div>
  )
}

function GeneratedImageSummary({ result }) {
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState(null)
  const artifact = result?.artifact || null
  const file = result?.file || {}
  const metadata = artifactMetadata(artifact)

  useEffect(() => {
    let cancelled = false
    let objectUrl = null
    const controller = new AbortController()

    async function loadPreview() {
      if (!artifact?.artifact_id) return
      setPreviewError(null)
      setPreviewUrl(null)
      try {
        const resp = await apiFetch(
          `/api/artifacts/${encodeURIComponent(artifact.artifact_id)}/file`,
          { signal: controller.signal }
        )
        if (!resp.ok) {
          throw new Error(await readErrorMessage(resp, 'Image preview failed'))
        }
        const blob = await resp.blob()
        objectUrl = URL.createObjectURL(blob)
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        setPreviewUrl(objectUrl)
      } catch (e) {
        if (e?.name === 'AbortError') return
        if (!cancelled) setPreviewError(e.message || 'Image preview failed')
      }
    }

    loadPreview()

    return () => {
      cancelled = true
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [artifact?.artifact_id])

  if (!result) return null

  return (
    <div className="artifact-upload-result generated-media-result">
      <div className="artifact-upload-result-title">
        <strong>{artifact?.title || 'Generated media artifact'}</strong>
        <RegistryBadge tone="active">generated media</RegistryBadge>
      </div>
      {previewUrl ? (
        <img
          className="generated-media-preview"
          src={previewUrl}
          alt="Generated media artifact preview"
        />
      ) : (
        <p className="artifact-upload-note">
          {previewError || 'Loading generated media preview...'}
        </p>
      )}
      <div className="artifact-upload-meta">
        <RegistryMeta label="Artifact" value={artifact?.artifact_id} />
        <RegistryMeta label="File" value={file.path || artifact?.path} />
        <RegistryMeta
          label="Media"
          value={metadata.media_kind ? humanizeSourceValue(metadata.media_kind) : null}
        />
        <RegistryMeta label="Prompt" value={metadata.prompt} />
        <RegistryMeta label="Backend" value={metadata.generation_backend} />
        <RegistryMeta label="Seed" value={metadata.seed} />
        <RegistryMeta
          label="Size"
          value={
            metadata.width && metadata.height
              ? `${metadata.width}x${metadata.height}`
              : null
          }
        />
      </div>
    </div>
  )
}

function ImageGenerationPanel({
  generating,
  generationError,
  generationResult,
  capability,
  onGenerateImage,
  onRefresh,
}) {
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [backend, setBackend] = useState('comfyui')
  const [width, setWidth] = useState('512')
  const [height, setHeight] = useState('512')
  const [seed, setSeed] = useState('')
  const [intendedUse, setIntendedUse] = useState('general')
  const [localError, setLocalError] = useState(null)
  const enabled = capability ? Boolean(capability.enabled) : null
  const statusLabel = capability
    ? `${capability.status || 'unknown'}${capability.reason ? `: ${capability.reason}` : ''}`
    : 'status not loaded'

  async function handleSubmit(e) {
    e.preventDefault()
    setLocalError(null)
    const cleanedPrompt = prompt.trim()
    if (!cleanedPrompt) {
      setLocalError('Enter a prompt for the generated media artifact.')
      return
    }

    const parsedWidth = Number(width)
    const parsedHeight = Number(height)
    const parsedSeed = seed.trim() ? Number(seed) : null
    if (!Number.isInteger(parsedWidth) || parsedWidth < 1) {
      setLocalError('Width must be a positive integer.')
      return
    }
    if (!Number.isInteger(parsedHeight) || parsedHeight < 1) {
      setLocalError('Height must be a positive integer.')
      return
    }
    if (parsedSeed !== null && !Number.isInteger(parsedSeed)) {
      setLocalError('Seed must be an integer when supplied.')
      return
    }

    try {
      await onGenerateImage({
        prompt: cleanedPrompt,
        negativePrompt: negativePrompt.trim(),
        backend,
        width: parsedWidth,
        height: parsedHeight,
        seed: parsedSeed,
        intendedUse,
      })
    } catch {
      // App-level generation state renders the backend error.
    }
  }

  return (
    <section className="artifact-upload image-generation-panel">
      <div className="artifact-upload-header">
        <h2>Generate Image</h2>
        <span>Generated media artifact</span>
      </div>
      <div className="image-generation-status">
        <RegistryBadge tone={enabled ? 'active' : 'draft'}>{statusLabel}</RegistryBadge>
        <span>Operator-triggered only. Raw image bytes are not content-indexed.</span>
      </div>
      <form onSubmit={handleSubmit}>
        <label className="artifact-upload-field">
          <span>Prompt</span>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            disabled={generating}
            rows={4}
            placeholder="Describe the image to generate"
          />
        </label>
        <label className="artifact-upload-field">
          <span>Negative prompt</span>
          <textarea
            value={negativePrompt}
            onChange={e => setNegativePrompt(e.target.value)}
            disabled={generating}
            rows={2}
            placeholder="Optional"
          />
        </label>
        <div className="artifact-upload-row image-generation-grid">
          <label className="artifact-upload-field">
            <span>Width</span>
            <input
              type="number"
              min="1"
              value={width}
              onChange={e => setWidth(e.target.value)}
              disabled={generating}
            />
          </label>
          <label className="artifact-upload-field">
            <span>Height</span>
            <input
              type="number"
              min="1"
              value={height}
              onChange={e => setHeight(e.target.value)}
              disabled={generating}
            />
          </label>
          <label className="artifact-upload-field">
            <span>Seed</span>
            <input
              type="number"
              value={seed}
              onChange={e => setSeed(e.target.value)}
              disabled={generating}
              placeholder="Optional"
            />
          </label>
        </div>
        <div className="artifact-upload-row image-generation-grid">
          <label className="artifact-upload-field">
            <span>Backend</span>
            <select
              value={backend}
              onChange={e => setBackend(e.target.value)}
              disabled={generating}
            >
              <option value="comfyui">ComfyUI</option>
            </select>
          </label>
          <label className="artifact-upload-field">
            <span>Intended use</span>
            <select
              value={intendedUse}
              onChange={e => setIntendedUse(e.target.value)}
              disabled={generating}
            >
              <option value="general">General</option>
              <option value="reference">Reference</option>
            </select>
          </label>
        </div>
        <div className="image-generation-actions">
          <button
            type="submit"
            className="btn btn-small"
            disabled={generating || !prompt.trim()}
          >
            {generating ? 'Generating...' : 'Generate'}
          </button>
          <button type="button" className="btn btn-small" onClick={onRefresh}>
            Refresh Media
          </button>
        </div>
      </form>
      {(localError || generationError) && (
        <p className="artifact-upload-error">{localError || generationError}</p>
      )}
      <GeneratedImageSummary result={generationResult} />
    </section>
  )
}

function ArtifactUpload({ uploading, uploadError, uploadResult, onUpload }) {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [revisionOf, setRevisionOf] = useState('')
  const [mediaKind, setMediaKind] = useState('')
  const [localError, setLocalError] = useState(null)
  const fileInputRef = useRef(null)
  const isImageFile = Boolean(file?.type?.startsWith('image/'))

  async function handleSubmit(e) {
    e.preventDefault()
    setLocalError(null)
    if (!file) {
      setLocalError('Choose a file to upload.')
      return
    }

    try {
      await onUpload({ file, title, description, revisionOf, mediaKind })
      setFile(null)
      setTitle('')
      setDescription('')
      setRevisionOf('')
      setMediaKind('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch {
      // App-level upload state renders the backend error.
    }
  }

  return (
    <section className="artifact-upload">
      <div className="artifact-upload-header">
        <h2>Upload Artifact</h2>
        <span>Source role: Uploaded source</span>
      </div>
      <form onSubmit={handleSubmit}>
        <label className="artifact-upload-field">
          <span>File</span>
          <input
            ref={fileInputRef}
            type="file"
            onChange={e => {
              const nextFile = e.target.files?.[0] || null
              setFile(nextFile)
              if (nextFile?.type?.startsWith('image/')) {
                setMediaKind(mediaKind || 'uploaded_image')
              } else {
                setMediaKind('')
              }
            }}
            disabled={uploading}
          />
        </label>
        {isImageFile && (
          <label className="artifact-upload-field">
            <span>Media kind</span>
            <select
              value={mediaKind || 'uploaded_image'}
              onChange={e => setMediaKind(e.target.value)}
              disabled={uploading}
            >
              <option value="uploaded_image">Uploaded image</option>
              <option value="screenshot">Screenshot</option>
            </select>
            <em>Media artifacts are saved with provenance metadata; raw image bytes are not content-indexed.</em>
          </label>
        )}
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
        <label className="artifact-upload-field">
          <span>Revision of artifact ID</span>
          <input
            type="text"
            value={revisionOf}
            onChange={e => setRevisionOf(e.target.value)}
            disabled={uploading}
            placeholder="Optional existing artifact id"
          />
          <em>Optional. Use when this upload is an updated version of an existing artifact.</em>
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
  imageGenerating,
  imageGenerationError,
  imageGenerationResult,
  imageGenerationCapability,
  onGenerateImage,
  onRefresh,
}) {
  return (
    <div className="registry-content">
      <div className="registry-title-row">
        <h2>Media & Artifacts</h2>
        <button type="button" className="btn btn-small" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {loading && <p className="debug-note">Loading media and artifact records...</p>}
      {error && <p className="registry-error">{error}</p>}

      <ImageGenerationPanel
        generating={imageGenerating}
        generationError={imageGenerationError}
        generationResult={imageGenerationResult}
        capability={imageGenerationCapability}
        onGenerateImage={onGenerateImage}
        onRefresh={onRefresh}
      />

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
