"""Internal file ingestion foundation for artifacts."""

import hashlib
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tir.artifacts.service import (
    ALLOWED_ARTIFACT_STATUSES,
    ALLOWED_ARTIFACT_TYPES,
    create_artifact,
)
from tir.config import WORKSPACE_DIR
from tir.memory.artifact_indexing import index_artifact_file
from tir.workspace.service import resolve_workspace_path


ALLOWED_AUTHORITIES = {
    "source_material",
    "draft",
    "log",
    "correction",
    "current_project_state",
    "unknown",
}

MAX_INGEST_BYTES = 10 * 1024 * 1024


class ArtifactIngestionError(ValueError):
    """Raised when an artifact file cannot be safely ingested."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_filename(filename: str) -> str:
    if not filename or not filename.strip():
        raise ArtifactIngestionError("filename is required")

    normalized = filename.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ArtifactIngestionError("filename cannot contain traversal")

    basename = parts[-1] if parts else ""
    basename = re.sub(r"\s+", " ", basename).strip()
    basename = re.sub(r"[^A-Za-z0-9._ -]", "_", basename)
    basename = basename.strip(" .")

    if not basename or not any(char.isalnum() for char in basename):
        raise ArtifactIngestionError("filename does not contain a safe file name")

    return basename


def _storage_prefix(source: str, artifact_type: str, created_by: str) -> str:
    if source == "upload" or artifact_type == "uploaded_file":
        return "uploads"
    if artifact_type == "generated_file" or created_by in {"anam", "tool"}:
        return "generated"
    return "uploads"


def _storage_path(
    *,
    artifact_id: str,
    safe_filename: str,
    source: str,
    artifact_type: str,
    created_by: str,
) -> str:
    now = _now()
    prefix = _storage_prefix(source, artifact_type, created_by)
    return (
        Path(prefix)
        / f"{now.year:04d}"
        / f"{now.month:02d}"
        / f"{now.day:02d}"
        / artifact_id
        / safe_filename
    ).as_posix()


def _write_bytes(relative_path: str, content: bytes, workspace_root: Path) -> dict:
    target = resolve_workspace_path(relative_path, workspace_root)
    parent = resolve_workspace_path(
        target.relative_to(Path(workspace_root).resolve()).parent,
        workspace_root,
        allow_root=True,
    )
    parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {
        "path": target.relative_to(Path(workspace_root).resolve()).as_posix(),
        "bytes": target.stat().st_size,
    }


def _mime_type_for_filename(filename: str) -> str:
    mime_type, _encoding = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def _validate_authority(authority: str) -> None:
    if authority not in ALLOWED_AUTHORITIES:
        raise ArtifactIngestionError(f"Invalid artifact authority: {authority}")


def ingest_artifact_file(
    *,
    filename: str,
    content: bytes,
    user_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    artifact_type: str = "uploaded_file",
    source: str = "upload",
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    created_by: str = "user",
    authority: str = "source_material",
    status: str = "active",
    revision_of: str | None = None,
    metadata: dict | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Save, register, and index an uploaded or generated artifact file."""
    if not isinstance(content, bytes):
        raise ArtifactIngestionError("content must be bytes")
    if len(content) > MAX_INGEST_BYTES:
        raise ArtifactIngestionError("file exceeds ingestion size limit")

    if artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise ArtifactIngestionError(f"Invalid artifact_type: {artifact_type}")
    if status not in ALLOWED_ARTIFACT_STATUSES:
        raise ArtifactIngestionError(f"Invalid artifact status: {status}")
    effective_authority = (
        "draft"
        if artifact_type == "generated_file" and authority == "source_material"
        else authority
    )
    _validate_authority(effective_authority)

    artifact_id = str(uuid.uuid4())
    safe_filename = _safe_filename(filename)
    original_filename = Path(filename.replace("\\", "/")).name
    relative_path = _storage_path(
        artifact_id=artifact_id,
        safe_filename=safe_filename,
        source=source,
        artifact_type=artifact_type,
        created_by=created_by,
    )
    resolved_path = resolve_workspace_path(relative_path, workspace_root)
    normalized_path = resolved_path.relative_to(Path(workspace_root).resolve()).as_posix()

    mime_type = _mime_type_for_filename(safe_filename)
    sha256 = hashlib.sha256(content).hexdigest()
    size_bytes = len(content)
    artifact_title = (title or safe_filename).strip()
    if not artifact_title:
        raise ArtifactIngestionError("title is required")

    base_metadata = {
        "filename": original_filename,
        "safe_filename": safe_filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "created_by": created_by,
        "authority": effective_authority,
        "source_type": "artifact_document",
        "user_id": user_id,
    }
    if metadata:
        base_metadata.update(metadata)

    file_result = _write_bytes(normalized_path, content, workspace_root)

    indexing = index_artifact_file(
        artifact_id=artifact_id,
        title=artifact_title,
        filename=safe_filename,
        path=file_result["path"],
        content=content,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
        source=source,
        authority=effective_authority,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        user_id=user_id,
        description=description,
    )

    artifact_metadata = {
        **base_metadata,
        "indexing_status": indexing["status"],
    }
    artifact = create_artifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        title=artifact_title,
        description=description,
        path=file_result["path"],
        status=status,
        source=source,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        source_tool_name=source_tool_name,
        revision_of=revision_of,
        metadata=artifact_metadata,
        workspace_root=workspace_root,
    )

    return {
        "artifact": artifact,
        "file": {
            **file_result,
            "sha256": sha256,
            "mime_type": mime_type,
        },
        "indexing": indexing,
    }
