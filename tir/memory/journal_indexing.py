"""Index reflection journals as retrievable journal memory."""

import re
from datetime import datetime, timezone

from tir.memory.chroma import upsert_chunk
from tir.memory.db import get_connection, upsert_chunk_fts


JOURNAL_CHUNK_CHARS = 4000


def _normalize_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _chunk_text(text: str, max_chars: int = JOURNAL_CHUNK_CHARS) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []

    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def journal_chunk_prefix(journal_date: str) -> str:
    safe_date = re.sub(r"[^A-Za-z0-9]+", "_", journal_date).strip("_")
    return f"journal_{safe_date}"


def journal_chunks_exist(journal_date: str) -> bool:
    prefix = journal_chunk_prefix(journal_date)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM main.chunks_fts WHERE chunk_id LIKE ?",
            (f"{prefix}_chunk_%",),
        ).fetchone()
    return bool(row["count"])


def _chroma_metadata(metadata: dict) -> dict:
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def index_reflection_journal(
    *,
    artifact_id: str,
    journal_date: str,
    title: str,
    path: str,
    text: str,
    metadata: dict,
) -> dict:
    """Index a reflection journal file as source_type=journal chunks."""
    created_at = datetime.now(timezone.utc).isoformat()
    chunks = _chunk_text(text)
    summary = {
        "status": "empty_text",
        "chunks_written": 0,
        "reason": None,
    }
    if not chunks:
        summary["reason"] = "empty_text"
        return summary

    prefix = journal_chunk_prefix(journal_date)
    base_metadata = {
        **metadata,
        "source_type": "journal",
        "source_trust": "firsthand",
        "artifact_id": artifact_id,
        "title": title,
        "path": path,
        "journal_date": journal_date,
        "created_at": created_at,
    }

    try:
        for index, chunk in enumerate(chunks):
            chunk_id = f"{prefix}_chunk_{index}"
            chunk_text = (
                f"Reflection journal: {journal_date}\n"
                f"Artifact ID: {artifact_id}\n"
                f"Path: {path}\n"
                f"Content chunk: {index}\n\n"
                f"{chunk}"
            )
            chunk_metadata = {
                **base_metadata,
                "chunk_index": index,
                "chunk_kind": "journal_content",
            }
            upsert_chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                metadata=_chroma_metadata(chunk_metadata),
            )
            upsert_chunk_fts(
                chunk_id=chunk_id,
                text=chunk_text,
                conversation_id=None,
                user_id=None,
                source_type="journal",
                source_trust="firsthand",
                created_at=created_at,
            )
            summary["chunks_written"] += 1
        summary["status"] = "indexed"
        return summary
    except Exception as exc:
        summary["status"] = "failed"
        summary["reason"] = f"{type(exc).__name__}: {exc}"
        return summary
