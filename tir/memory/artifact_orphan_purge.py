"""Remove artifact chunks that the test-isolation leak wrote into the store.

For roughly seven weeks a path-resolution bug redirected `tests/test_image_generation.py`'s
`FakeBackend` fixture output into `data/prod/chromadb` (fixed and guarded in commit
`4ef1de1`). What it left behind is ~50 `artifact_{uuid}_event` chunks titled
`fake-output.png` with no row in `artifacts`: records with no source, no conversation, no
user, and no lived origin, sitting in the retrieval pool alongside real memory.

`PLAN-2026-08-15-artifact-backfill.md` deliberately skipped these rather than re-rendering
them — with no source row there is nothing to re-derive from. Deleting is the correct
treatment where re-rendering was not.

Deletion is irreversible and cannot be re-derived, so this module is deliberately timid:

- **Two conditions are required to delete**, not one. "No `artifacts` row" is necessary but
  NOT sufficient to prove test origin: `ingest_artifact_file` writes chunks
  (`ingestion.py:239`) BEFORE the artifacts row (`ingestion.py:262`), so a crash between
  those lines would leave a *real* upload's chunks orphaned too. The title guard separates
  the two cases.
- **Anything orphaned that fails the title guard is reported, never deleted.** That is the
  half-completed-real-ingest case, and it deserves a human look rather than a silent
  delete. Leaving those behind is the point, not a gap.
- **Success is established by re-reading, not by what Chroma returns.** See
  `tir.memory.chroma.delete_chunks_by_ids`.
- Dry run is the default.

See PLAN-2026-08-16-orphan-chunk-purge.md.
"""

from tir.artifacts.service import get_artifact


ARTIFACT_CHUNK_ID_PREFIX = "artifact_"
EVENT_CHUNK_ID_SUFFIX = "_event"
EVENT_CHUNK_KIND = "event"
ARTIFACT_SOURCE_TYPE = "artifact_document"

# The fixture filename from tests/test_image_generation.py. Every leaked chunk
# carries it; no real artifact in the store ever has.
EXPECTED_ORPHAN_TITLE = "fake-output.png"


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _chroma():
    import tir.memory.chroma as chroma_mod

    return chroma_mod


def _fts_row_count() -> int:
    with _db().get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM main.chunks_fts").fetchone()[0])


def _fts_row_exists(chunk_id: str) -> bool:
    with _db().get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM main.chunks_fts WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
    return row is not None


def _delete_fts_row(chunk_id: str) -> None:
    with _db().get_connection() as conn:
        conn.execute("DELETE FROM main.chunks_fts WHERE chunk_id = ?", (chunk_id,))
        conn.commit()


def _store_counts() -> dict:
    return {
        "chroma_documents": _chroma().get_collection_count(),
        "fts_rows": _fts_row_count(),
    }


def _classify(chunk_id: str, metadata: dict) -> tuple[str, str | None]:
    """Return (verdict, reason) for an orphaned artifact chunk.

    verdict is "deletable" or "needs_review".
    """
    if metadata.get("chunk_kind") != EVENT_CHUNK_KIND or not chunk_id.endswith(
        EVENT_CHUNK_ID_SUFFIX
    ):
        return "needs_review", "orphan_content_chunk"

    title = metadata.get("title")
    if title != EXPECTED_ORPHAN_TITLE:
        return "needs_review", f"unexpected_title:{title!r}"

    return "deletable", None


def purge_orphan_artifact_chunks(
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> dict:
    """Delete leaked artifact chunks that have no `artifacts` row.

    Args:
        dry_run: When True (the default) nothing is deleted; the selected ids
            are reported instead.
        limit: Max deletable chunks to process, or None for all.

    Returns:
        A summary dict. Every scanned artifact chunk is accounted for exactly
        once as `has_artifact_row`, or as one of
        `deleted` / `partial` / `failed` / `needs_review`
        (or, in a dry run, `would_delete`).
    """
    chroma_mod = _chroma()
    collection = chroma_mod._get_collection()
    records = collection.get(include=["documents", "metadatas"])
    ids = records.get("ids") or []
    documents = records.get("documents") or []
    metadatas = records.get("metadatas") or []

    scanned = 0
    has_artifact_row = 0
    orphans_found = 0
    candidates = []
    review_entries = []

    for chunk_id, text, metadata in zip(ids, documents, metadatas):
        metadata = metadata or {}
        if not chunk_id.startswith(ARTIFACT_CHUNK_ID_PREFIX):
            continue
        if metadata.get("source_type") != ARTIFACT_SOURCE_TYPE:
            continue
        scanned += 1

        artifact_id = metadata.get("artifact_id")
        if artifact_id and get_artifact(artifact_id) is not None:
            has_artifact_row += 1
            continue

        orphans_found += 1
        entry = {
            "chunk_id": chunk_id,
            "artifact_id": artifact_id,
            "title": metadata.get("title"),
            "created_at": metadata.get("created_at"),
            "chunk_kind": metadata.get("chunk_kind"),
            "text_preview": (text or "")[:120],
        }
        verdict, reason = _classify(chunk_id, metadata)
        if verdict == "needs_review":
            review_entries.append({**entry, "status": "needs_review", "reason": reason})
            continue
        candidates.append(entry)

    # Stable order so a --limit run is reproducible and reviewable.
    candidates.sort(key=lambda candidate: candidate["chunk_id"])
    deletable = len(candidates)
    if limit is not None:
        candidates = candidates[: max(0, int(limit))]

    counts_before = _store_counts()

    entries = list(review_entries)
    deleted = 0
    partial = 0
    failed = 0

    for entry in candidates:
        chunk_id = entry["chunk_id"]
        if dry_run:
            entries.append({**entry, "status": "would_delete"})
            continue

        # FTS first: a row here is not expected (the leak was Chroma-only), but
        # if one exists both stores must go together or the id is reported as
        # partial. Never half-deleted and called a success.
        fts_removed = None
        try:
            if _fts_row_exists(chunk_id):
                _delete_fts_row(chunk_id)
                fts_removed = not _fts_row_exists(chunk_id)
                if not fts_removed:
                    failed += 1
                    entries.append(
                        {
                            **entry,
                            "status": "failed",
                            "reason": "fts_row_survived_delete; chroma untouched",
                        }
                    )
                    continue
        except Exception as exc:
            failed += 1
            entries.append(
                {
                    **entry,
                    "status": "failed",
                    "reason": f"fts_delete_failed: {type(exc).__name__}: {exc}",
                }
            )
            continue

        try:
            removed = chroma_mod.delete_chunks_by_ids([chunk_id])
        except Exception as exc:
            status = "partial" if fts_removed else "failed"
            if status == "partial":
                partial += 1
            else:
                failed += 1
            entries.append(
                {
                    **entry,
                    "status": status,
                    "reason": (
                        f"chroma_delete_failed: {type(exc).__name__}: {exc}"
                        + ("; FTS row already removed" if fts_removed else "")
                    ),
                }
            )
            continue

        if removed.get(chunk_id):
            deleted += 1
            entries.append({**entry, "status": "deleted"})
        else:
            status = "partial" if fts_removed else "failed"
            if status == "partial":
                partial += 1
            else:
                failed += 1
            entries.append(
                {
                    **entry,
                    "status": status,
                    "reason": (
                        "chroma_record_still_present_after_delete"
                        + ("; FTS row already removed" if fts_removed else "")
                    ),
                }
            )

    return {
        "dry_run": dry_run,
        "limit": limit,
        "scanned": scanned,
        "has_artifact_row": has_artifact_row,
        "orphans_found": orphans_found,
        "deletable": deletable,
        "processed": len(candidates),
        "deleted": deleted,
        "partial": partial,
        "failed": failed,
        "needs_review": len(review_entries),
        "entries": entries,
        "counts_before": counts_before,
        "counts_after": _store_counts(),
    }
