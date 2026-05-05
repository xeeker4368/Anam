"""Admin-level memory integrity audit and repair helpers."""

from tir.memory import chunking
from tir.memory.chroma import get_collection_count
from tir.memory.db import (
    get_active_conversations,
    get_connection,
    get_unchunked_ended_conversations,
)


def _count_query(conn, query: str, params: tuple = ()) -> int:
    return int(conn.execute(query, params).fetchone()[0])


def _bounded_ids(conn, query: str, limit: int, params: tuple = ()) -> list[str]:
    rows = conn.execute(query, (*params, limit)).fetchall()
    return [str(row[0]) for row in rows]


def audit_memory_integrity(limit: int = 25) -> dict:
    """Return a compact audit of message persistence and retrieval coverage."""
    bounded_limit = max(0, int(limit))
    warnings = []

    with get_connection() as conn:
        working_message_count = _count_query(conn, "SELECT COUNT(*) FROM main.messages")
        archive_message_count = _count_query(conn, "SELECT COUNT(*) FROM archive.messages")

        missing_from_archive_count = _count_query(
            conn,
            """SELECT COUNT(*) FROM (
                   SELECT id FROM main.messages
                   EXCEPT
                   SELECT id FROM archive.messages
               )""",
        )
        missing_from_archive = _bounded_ids(
            conn,
            """SELECT id FROM (
                   SELECT id FROM main.messages
                   EXCEPT
                   SELECT id FROM archive.messages
               )
               ORDER BY id
               LIMIT ?""",
            bounded_limit,
        )

        missing_from_working_count = _count_query(
            conn,
            """SELECT COUNT(*) FROM (
                   SELECT id FROM archive.messages
                   EXCEPT
                   SELECT id FROM main.messages
               )""",
        )
        missing_from_working = _bounded_ids(
            conn,
            """SELECT id FROM (
                   SELECT id FROM archive.messages
                   EXCEPT
                   SELECT id FROM main.messages
               )
               ORDER BY id
               LIMIT ?""",
            bounded_limit,
        )

        total_conversations = _count_query(conn, "SELECT COUNT(*) FROM main.conversations")
        active_conversation_count = _count_query(
            conn,
            "SELECT COUNT(*) FROM main.conversations WHERE ended_at IS NULL",
        )
        ended_conversation_count = _count_query(
            conn,
            "SELECT COUNT(*) FROM main.conversations WHERE ended_at IS NOT NULL",
        )
        ended_unchunked_count = _count_query(
            conn,
            """SELECT COUNT(*) FROM main.conversations
               WHERE ended_at IS NOT NULL AND chunked = 0""",
        )
        ended_unchunked_ids = _bounded_ids(
            conn,
            """SELECT id FROM main.conversations
               WHERE ended_at IS NOT NULL AND chunked = 0
               ORDER BY started_at ASC
               LIMIT ?""",
            bounded_limit,
        )

        fts_chunk_count = _count_query(conn, "SELECT COUNT(*) FROM main.chunks_fts")

        chunked_missing_fts_count = _count_query(
            conn,
            """SELECT COUNT(*) FROM (
                   SELECT c.id
                   FROM main.conversations c
                   LEFT JOIN main.chunks_fts f ON f.conversation_id = c.id
                   WHERE c.chunked = 1 AND c.message_count > 0
                   GROUP BY c.id
                   HAVING COUNT(f.chunk_id) = 0
               )""",
        )
        chunked_missing_fts_ids = _bounded_ids(
            conn,
            """SELECT id FROM (
                   SELECT c.id, c.started_at
                   FROM main.conversations c
                   LEFT JOIN main.chunks_fts f ON f.conversation_id = c.id
                   WHERE c.chunked = 1 AND c.message_count > 0
                   GROUP BY c.id
                   HAVING COUNT(f.chunk_id) = 0
               )
               ORDER BY started_at ASC
               LIMIT ?""",
            bounded_limit,
        )

    message_id_parity_ok = (
        working_message_count == archive_message_count
        and missing_from_archive_count == 0
        and missing_from_working_count == 0
    )

    chroma_chunk_count = None
    fts_chroma_count_match = None
    try:
        chroma_chunk_count = get_collection_count()
        fts_chroma_count_match = fts_chunk_count == chroma_chunk_count
    except Exception as exc:
        warnings.append(f"Chroma count unavailable: {type(exc).__name__}: {exc}")

    if not message_id_parity_ok:
        warnings.append("Working/archive message ID parity is not clean.")
    if active_conversation_count:
        warnings.append(
            f"{active_conversation_count} active conversation(s) may not be fully "
            "retrievable until live or final chunking completes."
        )
    if ended_unchunked_count:
        warnings.append(
            f"{ended_unchunked_count} ended conversation(s) remain unchunked."
        )
    if chunked_missing_fts_count:
        warnings.append(
            f"{chunked_missing_fts_count} chunked conversation(s) have no FTS chunks."
        )
    if fts_chroma_count_match is False:
        warnings.append("FTS and Chroma chunk counts differ (count-level check only).")

    return {
        "working_message_count": working_message_count,
        "archive_message_count": archive_message_count,
        "message_id_parity_ok": message_id_parity_ok,
        "missing_from_archive_count": missing_from_archive_count,
        "missing_from_archive": missing_from_archive,
        "missing_from_working_count": missing_from_working_count,
        "missing_from_working": missing_from_working,
        "total_conversations": total_conversations,
        "active_conversation_count": active_conversation_count,
        "ended_conversation_count": ended_conversation_count,
        "ended_unchunked_count": ended_unchunked_count,
        "ended_unchunked_ids": ended_unchunked_ids,
        "fts_chunk_count": fts_chunk_count,
        "chroma_chunk_count": chroma_chunk_count,
        "fts_chroma_count_match": fts_chroma_count_match,
        "chunked_conversations_missing_fts_chunks": chunked_missing_fts_count,
        "chunked_conversations_missing_fts_chunk_ids": chunked_missing_fts_ids,
        "warnings": warnings,
    }


def repair_memory_integrity(
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Repair recoverable retrieval gaps for ended unchunked conversations."""
    active_conversation_count = len(get_active_conversations())
    repairable = get_unchunked_ended_conversations()
    targets = repairable[:limit] if limit is not None else repairable

    if dry_run:
        return {
            "dry_run": True,
            "active_conversation_count": active_conversation_count,
            "repairable_ended_unchunked_count": len(repairable),
            "would_attempt": len(targets),
            "conversation_ids": [conv["id"] for conv in targets],
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "chunks_written": 0,
            "failures": [],
        }

    summary = chunking.recover_unchunked_ended_conversations(limit=limit)
    return {
        "dry_run": False,
        "active_conversation_count": active_conversation_count,
        "repairable_ended_unchunked_count": len(repairable),
        **summary,
    }


def checkpoint_active_conversations(
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Checkpoint active conversations into retrieval without closing them."""
    active_conversations = get_active_conversations()
    checkpointable = [
        conv
        for conv in active_conversations
        if int(conv.get("message_count") or 0) > 0
    ]
    targets = checkpointable[:limit] if limit is not None else checkpointable
    conversation_ids = [conv["id"] for conv in targets]

    summary = {
        "dry_run": dry_run,
        "active_conversation_count": len(active_conversations),
        "checkpointable_active_count": len(checkpointable),
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "chunks_written": 0,
        "conversation_ids": conversation_ids,
        "failures": [],
    }

    if dry_run:
        return summary

    for conv in targets:
        conversation_id = conv["id"]
        summary["attempted"] += 1
        try:
            chunks_written = chunking.checkpoint_conversation(
                conversation_id,
                conv["user_id"],
            )
            summary["chunks_written"] += chunks_written
            summary["succeeded"] += 1
        except Exception as exc:
            summary["failed"] += 1
            summary["failures"].append({
                "conversation_id": conversation_id,
                "error": str(exc),
            })

    return summary
