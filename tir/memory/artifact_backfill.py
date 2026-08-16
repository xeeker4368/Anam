"""Re-render existing artifact event chunks through the current slimmed `_event_text`.

`PLAN-2026-08-12-imagegen-confabulation-fix.md` slimmed `_event_text` so newly
indexed artifact chunks no longer carry forgeable identity fields (SHA256,
stored path, byte size, filename, seed). That fix was forward-only: chunks
written before it still hold the full pre-slim block and are still retrieved
into context. This module closes that gap by re-deriving each old-shape chunk's
text from its current `artifacts` row and re-upserting it under the SAME
chunk_id.

Contract — text and vector change, nothing else:

- The chunk's Chroma metadata dict is read from the store and written straight
  back, unmodified.
- The FTS provenance columns (`conversation_id`, `user_id`, `source_type`,
  `source_trust`, `created_at`) are read from the existing FTS row and written
  straight back. `created_at` is NEVER re-derived from the clock — doing so
  would rewrite provenance (NORTH_STAR invariant 4).
- No chunk is added or removed, so Chroma document count and FTS row count are
  identical before and after.
- The embedding is recomputed from the NEW text. `_store_artifact_chunk` calls
  `upsert_chunk` without an `embedding` argument, so `tir.memory.chroma`
  embeds the text it is given. The old chunk's vector is never carried over —
  a stale vector for rewritten text would be worse than doing nothing.

Freshness: text is re-derived from the CURRENT `artifacts` row, so a
`description` or `metadata_json` edited since indexing is reflected in the new
text. This is intended (the row is the source of truth), and is a no-op for
every row in the store at the time of writing.

Dry run is the default. See `PLAN-2026-08-15-artifact-backfill.md`.
"""

from tir.artifacts.media import media_indexing_metadata
from tir.artifacts.service import get_artifact
from tir.memory.artifact_indexing import _event_text, _store_artifact_chunk


# Chunk identity — only `artifact_{artifact_id}_event` chunks use `_event_text`.
EVENT_CHUNK_ID_PREFIX = "artifact_"
EVENT_CHUNK_ID_SUFFIX = "_event"
EVENT_CHUNK_KIND = "event"
ARTIFACT_SOURCE_TYPE = "artifact_document"

# Shape markers. The pre-slim `_event_text` unconditionally emitted
# `f"Artifact source: {title}"` as its first line; the current slim shape
# emits `f"Artifact: {title} (id: {artifact_id})"`.
OLD_EVENT_TEXT_PREFIX = "Artifact source:"
SLIM_EVENT_TEXT_PREFIX = "Artifact: "


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _chroma():
    import tir.memory.chroma as chroma_mod

    return chroma_mod


def _is_event_chunk(chunk_id: str, metadata: dict) -> bool:
    """Return whether a stored chunk is an artifact event chunk.

    Chunk identity is checked BEFORE any text marker. A marker-only scan is
    unsafe: conversation chunks and artifact *content* chunks can legitimately
    contain `SHA256:` / `Stored path:` (the model pasted a provenance block into
    chat, or an uploaded file's own text contains it), and those are raw
    experience that must not be rewritten.
    """
    return (
        chunk_id.startswith(EVENT_CHUNK_ID_PREFIX)
        and chunk_id.endswith(EVENT_CHUNK_ID_SUFFIX)
        and metadata.get("chunk_kind") == EVENT_CHUNK_KIND
        and metadata.get("source_type") == ARTIFACT_SOURCE_TYPE
    )


def _is_old_shape(text: str) -> bool:
    """Return whether an event chunk's text is the pre-slim block."""
    return (text or "").startswith(OLD_EVENT_TEXT_PREFIX)


def _artifact_id_from_chunk_id(chunk_id: str) -> str:
    return chunk_id[len(EVENT_CHUNK_ID_PREFIX):-len(EVENT_CHUNK_ID_SUFFIX)]


def _fts_row_count() -> int:
    with _db().get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM main.chunks_fts").fetchone()[0])


def _fts_provenance(chunk_id: str) -> dict | None:
    """Return the existing FTS row's provenance columns, or None if absent."""
    with _db().get_connection() as conn:
        row = conn.execute(
            """SELECT conversation_id, user_id, source_type, source_trust, created_at
               FROM main.chunks_fts WHERE chunk_id = ?""",
            (chunk_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def _store_counts() -> dict:
    return {
        "chroma_documents": _chroma().get_collection_count(),
        "fts_rows": _fts_row_count(),
    }


def backfill_artifact_event_chunks(
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> dict:
    """Re-render pre-slim artifact event chunks in place.

    Args:
        dry_run: When True (the default) nothing is written; each candidate's
            old and new text is reported instead.
        limit: Max candidate chunks to process, or None for all.

    Returns:
        A summary dict. Chunk accounting is disjoint: every scanned event chunk
        is counted exactly once as `already_slim`, or as one of
        `rewritten` / `unchanged` / `skipped` / `failed`.
    """
    collection = _chroma()._get_collection()
    records = collection.get(include=["documents", "metadatas"])
    ids = records.get("ids") or []
    documents = records.get("documents") or []
    metadatas = records.get("metadatas") or []

    scanned = 0
    already_slim = 0
    candidates = []
    for chunk_id, text, metadata in zip(ids, documents, metadatas):
        metadata = metadata or {}
        if not _is_event_chunk(chunk_id, metadata):
            continue
        scanned += 1
        if not _is_old_shape(text):
            already_slim += 1
            continue
        candidates.append((chunk_id, text or "", metadata))

    # Stable order so a --limit run is reproducible and reviewable.
    candidates.sort(key=lambda candidate: candidate[0])
    eligible = len(candidates)
    if limit is not None:
        candidates = candidates[: max(0, int(limit))]

    counts_before = _store_counts()

    entries = []
    rewritten = 0
    unchanged = 0
    skipped = 0
    failed = 0

    for chunk_id, old_text, metadata in candidates:
        artifact_id = metadata.get("artifact_id") or _artifact_id_from_chunk_id(chunk_id)
        entry = {"chunk_id": chunk_id, "artifact_id": artifact_id}
        try:
            artifact = get_artifact(artifact_id)
            if artifact is None:
                # Orphan: no source row, so the text cannot be re-derived.
                # Reported, never blanked and never guessed at.
                skipped += 1
                entries.append({**entry, "status": "skipped", "reason": "no_artifact_row"})
                continue

            new_text = _event_text(
                title=artifact["title"],
                artifact_id=artifact["artifact_id"],
                description=artifact.get("description"),
                media_metadata=media_indexing_metadata(artifact.get("metadata")),
            )
            if new_text == old_text:
                unchanged += 1
                entries.append({**entry, "status": "unchanged"})
                continue

            provenance = _fts_provenance(chunk_id)
            if provenance is None:
                # In Chroma but not FTS: a pre-existing store mismatch. Writing
                # FTS here would ADD a row and break the count invariant, and a
                # Chroma-only write would be a silent partial. Report instead.
                skipped += 1
                entries.append({**entry, "status": "skipped", "reason": "missing_fts_row"})
                continue

            entry.update(
                {
                    "old_text": old_text,
                    "new_text": new_text,
                    "old_chars": len(old_text),
                    "new_chars": len(new_text),
                }
            )

            if dry_run:
                entries.append({**entry, "status": "would_rewrite"})
                rewritten += 1
                continue

            _store_artifact_chunk(
                chunk_id=chunk_id,
                text=new_text,
                source_conversation_id=provenance["conversation_id"],
                user_id=provenance["user_id"],
                source_type=provenance["source_type"],
                source_trust=provenance["source_trust"],
                metadata=metadata,
                created_at=provenance["created_at"],
            )
            entries.append({**entry, "status": "rewritten"})
            rewritten += 1
        except Exception as exc:
            # One bad chunk never aborts the run; it is reported, not swallowed.
            failed += 1
            entries.append(
                {**entry, "status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
            )

    return {
        "dry_run": dry_run,
        "limit": limit,
        "scanned": scanned,
        "already_slim": already_slim,
        "eligible": eligible,
        "processed": len(candidates),
        "rewritten": rewritten,
        "unchanged": unchanged,
        "skipped": skipped,
        "failed": failed,
        "entries": entries,
        "counts_before": counts_before,
        "counts_after": _store_counts(),
    }
