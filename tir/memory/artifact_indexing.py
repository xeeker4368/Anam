"""Index artifact files as retrievable source memory."""

import re
from datetime import datetime, timezone

from tir.artifacts.source_roles import (
    display_origin,
    display_source_role,
    source_trust_for_source_role,
)
from tir.memory.chroma import upsert_chunk
from tir.memory.db import upsert_chunk_fts


SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".html",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
}

CONTENT_CHUNK_CHARS = 4000


def is_supported_text_file(filename: str, mime_type: str | None = None) -> bool:
    """Return whether v1 should attempt text-content indexing."""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in SUPPORTED_TEXT_EXTENSIONS:
        return True
    if mime_type and mime_type.startswith("text/"):
        return True
    return False


def _normalize_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _decode_text(content: bytes) -> str:
    return _normalize_text(content.decode("utf-8", errors="replace"))


def _chunk_text(text: str, max_chars: int = CONTENT_CHUNK_CHARS) -> list[str]:
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


def _event_text(
    *,
    title: str,
    filename: str,
    path: str,
    artifact_id: str,
    source: str,
    origin: str,
    source_role: str,
    mime_type: str | None,
    size_bytes: int,
    sha256: str,
    description: str | None,
    media_metadata: dict | None = None,
) -> str:
    media_metadata = media_metadata or {}
    lines = [
        f"Artifact source: {title}",
        f"Artifact ID: {artifact_id}",
        f"File: {filename}",
        f"Stored path: {path}",
        f"Source: {source}",
        f"Origin: {display_origin(origin)}",
        f"Source role: {display_source_role(source_role)}",
        f"MIME type: {mime_type or 'unknown'}",
        f"Size: {size_bytes} bytes",
        f"SHA256: {sha256}",
    ]
    media_kind = media_metadata.get("media_kind")
    if media_kind:
        lines.append(f"Media kind: {media_kind}")
        if description:
            lines.append(
                "Description (artifact metadata, not raw image content): "
                f"{description}"
            )
    elif description:
        lines.append(f"Description: {description}")

    observed_description = media_metadata.get("observed_description")
    if observed_description:
        uncertainty = (
            media_metadata.get("uncertainty_label")
            or "unverified_visual_interpretation"
        )
        lines.append(
            "Observed description "
            f"({uncertainty}; visual interpretation, not verified fact): "
            f"{observed_description}"
        )
    prompt = media_metadata.get("prompt")
    if prompt:
        lines.append(f"Generation prompt (provenance metadata): {prompt}")
    negative_prompt = media_metadata.get("negative_prompt")
    if negative_prompt:
        lines.append(f"Negative prompt (provenance metadata): {negative_prompt}")
    generation_backend = media_metadata.get("generation_backend")
    generation_model = media_metadata.get("generation_model")
    workflow_name = media_metadata.get("workflow_name")
    workflow_id = media_metadata.get("workflow_id")
    if generation_backend:
        lines.append(f"Generation backend: {generation_backend}")
    if generation_model:
        lines.append(f"Generation model: {generation_model}")
    if workflow_name:
        lines.append(f"Generation workflow: {workflow_name}")
    if workflow_id:
        lines.append(f"Generation workflow ID: {workflow_id}")
    if media_metadata.get("seed") not in {None, ""}:
        lines.append(f"Generation seed: {media_metadata.get('seed')}")
    if media_metadata.get("width") and media_metadata.get("height"):
        lines.append(
            "Generation dimensions: "
            f"{media_metadata.get('width')}x{media_metadata.get('height')}"
        )
    interpretation_source = media_metadata.get("interpretation_source")
    if interpretation_source:
        lines.append(f"Interpretation source: {interpretation_source}")
    if "human_confirmed" in media_metadata:
        lines.append(f"Human confirmed: {bool(media_metadata.get('human_confirmed'))}")
    return "\n".join(lines)


def _content_text_header(
    *,
    title: str,
    filename: str,
    origin: str,
    source_role: str,
    artifact_id: str,
    chunk_index: int,
) -> str:
    return (
        f"Artifact source: {title}\n"
        f"File: {filename}\n"
        f"Origin: {display_origin(origin)}\n"
        f"Source role: {display_source_role(source_role)}\n"
        f"Artifact ID: {artifact_id}\n"
        f"Content chunk: {chunk_index}\n\n"
    )


def _store_artifact_chunk(
    *,
    chunk_id: str,
    text: str,
    source_conversation_id: str | None,
    user_id: str | None,
    source_type: str,
    source_trust: str,
    metadata: dict,
    created_at: str,
) -> None:
    upsert_chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=metadata,
    )
    upsert_chunk_fts(
        chunk_id=chunk_id,
        text=text,
        conversation_id=source_conversation_id,
        user_id=user_id,
        source_type=source_type,
        source_trust=source_trust,
        created_at=created_at,
    )


def index_artifact_file(
    *,
    artifact_id: str,
    title: str,
    filename: str,
    path: str,
    content: bytes,
    mime_type: str | None,
    size_bytes: int,
    sha256: str,
    source: str,
    origin: str,
    source_role: str,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    user_id: str | None = None,
    description: str | None = None,
    media_metadata: dict | None = None,
) -> dict:
    """Write a retrievable artifact event chunk and optional content chunks."""
    created_at = datetime.now(timezone.utc).isoformat()
    source_type = "artifact_document"
    source_trust = source_trust_for_source_role(source_role)
    base_metadata = {
        "source_type": source_type,
        "source_trust": source_trust,
        "artifact_id": artifact_id,
        "title": title,
        "filename": filename,
        "path": path,
        "origin": origin,
        "source_role": source_role,
        "source_conversation_id": source_conversation_id or "",
        "source_message_id": source_message_id or "",
        "user_id": user_id or "",
        "created_at": created_at,
    }
    if media_metadata:
        base_metadata.update(media_metadata)

    summary = {
        "status": "metadata_only",
        "content_chunks_written": 0,
        "event_chunks_written": 0,
        "reason": None,
    }

    try:
        event_metadata = {
            **base_metadata,
            "chunk_index": -1,
            "chunk_kind": "event",
        }
        _store_artifact_chunk(
            chunk_id=f"artifact_{artifact_id}_event",
            text=_event_text(
                title=title,
                filename=filename,
                path=path,
                artifact_id=artifact_id,
                source=source,
                origin=origin,
                source_role=source_role,
                mime_type=mime_type,
                size_bytes=size_bytes,
                sha256=sha256,
                description=description,
                media_metadata=media_metadata,
            ),
            source_conversation_id=source_conversation_id,
            user_id=user_id,
            source_type=source_type,
            source_trust=source_trust,
            metadata=event_metadata,
            created_at=created_at,
        )
        summary["event_chunks_written"] = 1

        if not is_supported_text_file(filename, mime_type):
            summary["reason"] = "unsupported_type"
            return summary

        text = _decode_text(content)
        content_chunks = _chunk_text(text)
        if not content_chunks:
            summary["reason"] = "empty_text"
            return summary

        for index, chunk in enumerate(content_chunks):
            chunk_text = _content_text_header(
                title=title,
                filename=filename,
                origin=origin,
                source_role=source_role,
                artifact_id=artifact_id,
                chunk_index=index,
            ) + chunk
            metadata = {
                **base_metadata,
                "chunk_index": index,
                "chunk_kind": "content",
            }
            _store_artifact_chunk(
                chunk_id=f"artifact_{artifact_id}_chunk_{index}",
                text=chunk_text,
                source_conversation_id=source_conversation_id,
                user_id=user_id,
                source_type=source_type,
                source_trust=source_trust,
                metadata=metadata,
                created_at=created_at,
            )
            summary["content_chunks_written"] += 1

        summary["status"] = "indexed"
        return summary
    except Exception as exc:
        summary["status"] = "failed"
        summary["reason"] = f"{type(exc).__name__}: {exc}"
        return summary
