"""Internal artifact registry service.

Artifacts are metadata records for outputs created in the workspace or by
future channels. Artifact contents remain in files or external systems.
This service does not index artifacts as memory and does not expose tools,
API routes, or UI behavior.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tir.config import WORKSPACE_DIR
from tir.open_loops.service import (
    create_open_loop as create_open_loop_record,
    validate_open_loop_fields,
)
from tir.workspace.service import resolve_workspace_path, write_workspace_file


ALLOWED_ARTIFACT_TYPES = {
    "writing",
    "code",
    "research_note",
    "journal",
    "image",
    "image_prompt",
    "moltbook_draft",
    "voice_transcript",
    "vision_observation",
    "self_mod_proposal",
    "self_mod_patch",
    "generic",
}

ALLOWED_ARTIFACT_STATUSES = {
    "draft",
    "active",
    "archived",
    "superseded",
    "failed",
}


class ArtifactValidationError(ValueError):
    """Raised when artifact metadata is invalid."""


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_artifact_type(artifact_type: str) -> None:
    if artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise ArtifactValidationError(f"Invalid artifact_type: {artifact_type}")


def _validate_status(status: str) -> None:
    if status not in ALLOWED_ARTIFACT_STATUSES:
        raise ArtifactValidationError(f"Invalid artifact status: {status}")


def _validate_title(title: str) -> str:
    if not title or not title.strip():
        raise ArtifactValidationError("title is required")
    return title.strip()


def _metadata_to_json(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError as exc:
        raise ArtifactValidationError("metadata must be JSON serializable") from exc


def _normalize_workspace_path(
    path: str | Path | None,
    workspace_root: Path,
) -> str | None:
    if path is None:
        return None

    resolved = resolve_workspace_path(path, workspace_root)
    return resolved.relative_to(Path(workspace_root).resolve()).as_posix()


def artifact_to_dict(row) -> dict | None:
    """Convert an artifact DB row to a stable service result shape."""
    if row is None:
        return None

    data = dict(row)
    metadata_json = data.get("metadata_json")
    data["metadata"] = json.loads(metadata_json) if metadata_json else None
    return {
        "artifact_id": data["artifact_id"],
        "artifact_type": data["artifact_type"],
        "title": data["title"],
        "description": data.get("description"),
        "path": data.get("path"),
        "status": data["status"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "source": data.get("source"),
        "source_conversation_id": data.get("source_conversation_id"),
        "source_message_id": data.get("source_message_id"),
        "source_tool_name": data.get("source_tool_name"),
        "revision_of": data.get("revision_of"),
        "metadata_json": metadata_json,
        "metadata": data["metadata"],
    }


def create_artifact(
    *,
    artifact_type: str,
    title: str,
    description: str | None = None,
    path: str | Path | None = None,
    status: str = "draft",
    source: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    revision_of: str | None = None,
    metadata: dict | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Create an artifact metadata record in working.db."""
    _validate_artifact_type(artifact_type)
    _validate_status(status)
    normalized_title = _validate_title(title)

    artifact_id = str(uuid.uuid4())
    now = _now()
    normalized_path = _normalize_workspace_path(path, workspace_root)
    metadata_json = _metadata_to_json(metadata)

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """INSERT INTO main.artifacts
               (artifact_id, artifact_type, title, description, path, status,
                created_at, updated_at, source, source_conversation_id,
                source_message_id, source_tool_name, revision_of, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                artifact_id,
                artifact_type,
                normalized_title,
                description,
                normalized_path,
                status,
                now,
                now,
                source,
                source_conversation_id,
                source_message_id,
                source_tool_name,
                revision_of,
                metadata_json,
            ),
        )
        conn.commit()

    return get_artifact(artifact_id)


def create_artifact_file(
    *,
    relative_path: str | Path,
    content: str,
    artifact_type: str,
    title: str,
    description: str | None = None,
    status: str = "draft",
    source: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    revision_of: str | None = None,
    metadata: dict | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Write a workspace file and register its artifact metadata.

    Validation happens before writing so invalid artifact metadata or unsafe
    paths do not create files or database records.
    """
    _validate_artifact_type(artifact_type)
    _validate_status(status)
    _validate_title(title)
    _metadata_to_json(metadata)
    normalized_path = _normalize_workspace_path(relative_path, workspace_root)

    file_result = write_workspace_file(normalized_path, content, root=workspace_root)
    artifact = create_artifact(
        artifact_type=artifact_type,
        title=title,
        description=description,
        path=file_result["path"],
        status=status,
        source=source,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        source_tool_name=source_tool_name,
        revision_of=revision_of,
        metadata=metadata,
        workspace_root=workspace_root,
    )

    return {
        "artifact": artifact,
        "file": file_result,
    }


def create_artifact_file_with_open_loop(
    *,
    relative_path: str | Path,
    content: str,
    artifact_type: str,
    title: str,
    description: str | None = None,
    status: str = "draft",
    source: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    revision_of: str | None = None,
    metadata: dict | None = None,
    create_open_loop: bool = False,
    open_loop_title: str | None = None,
    open_loop_description: str | None = None,
    open_loop_next_action: str | None = None,
    open_loop_type: str = "unfinished_artifact",
    open_loop_priority: str = "normal",
    open_loop_metadata: dict | None = None,
    open_loop_source: str | None = None,
    open_loop_source_conversation_id: str | None = None,
    open_loop_source_message_id: str | None = None,
    open_loop_source_tool_name: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Create an artifact file and optionally link an open loop to it."""
    normalized_title = _validate_title(title)
    _validate_artifact_type(artifact_type)
    _validate_status(status)
    _metadata_to_json(metadata)
    _normalize_workspace_path(relative_path, workspace_root)

    requested_open_loop_title = (
        open_loop_title
        if open_loop_title is not None
        else f"Continue draft: {normalized_title}"
    )
    if create_open_loop:
        validate_open_loop_fields(
            title=requested_open_loop_title,
            loop_type=open_loop_type,
            priority=open_loop_priority,
            metadata=open_loop_metadata,
        )

    result = create_artifact_file(
        relative_path=relative_path,
        content=content,
        artifact_type=artifact_type,
        title=normalized_title,
        description=description,
        status=status,
        source=source,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        source_tool_name=source_tool_name,
        revision_of=revision_of,
        metadata=metadata,
        workspace_root=workspace_root,
    )

    open_loop = None
    if create_open_loop:
        open_loop = create_open_loop_record(
            title=requested_open_loop_title,
            description=open_loop_description,
            loop_type=open_loop_type,
            priority=open_loop_priority,
            related_artifact_id=result["artifact"]["artifact_id"],
            source=open_loop_source if open_loop_source is not None else source,
            source_conversation_id=(
                open_loop_source_conversation_id
                if open_loop_source_conversation_id is not None
                else source_conversation_id
            ),
            source_message_id=(
                open_loop_source_message_id
                if open_loop_source_message_id is not None
                else source_message_id
            ),
            source_tool_name=(
                open_loop_source_tool_name
                if open_loop_source_tool_name is not None
                else source_tool_name
            ),
            next_action=open_loop_next_action,
            metadata=open_loop_metadata,
        )

    return {
        "artifact": result["artifact"],
        "file": result["file"],
        "open_loop": open_loop,
    }


def get_artifact(artifact_id: str) -> dict | None:
    """Fetch an artifact by id."""
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    return artifact_to_dict(row)


def list_artifacts(
    *,
    artifact_type: str | None = None,
    status: str | None = None,
    path: str | Path | None = None,
    limit: int = 50,
    offset: int = 0,
    workspace_root: Path = WORKSPACE_DIR,
) -> list[dict]:
    """List artifacts with optional type, status, and path filters."""
    clauses = []
    params = []

    if artifact_type is not None:
        _validate_artifact_type(artifact_type)
        clauses.append("artifact_type = ?")
        params.append(artifact_type)

    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)

    if path is not None:
        normalized_path = _normalize_workspace_path(path, workspace_root)
        clauses.append("path = ?")
        params.append(normalized_path)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""SELECT * FROM main.artifacts
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [artifact_to_dict(row) for row in rows]


def update_artifact_status(artifact_id: str, status: str) -> dict | None:
    """Update only an artifact's status."""
    _validate_status(status)
    updated_at = _now()

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """UPDATE main.artifacts
               SET status = ?, updated_at = ?
               WHERE artifact_id = ?""",
            (status, updated_at, artifact_id),
        )
        conn.commit()

    return get_artifact(artifact_id)
