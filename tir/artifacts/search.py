"""Safe artifact/media lookup helpers for local tools and APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tir.artifacts.governance_blocklist import (
    GOVERNANCE_FILE_REJECTION_MESSAGE,
    SOURCE_TRACE_REJECTION_MESSAGE,
    is_governance_file_name,
    is_source_trace_path,
)
from tir.artifacts.media import ALLOWED_MEDIA_KINDS
from tir.artifacts.service import ArtifactValidationError, get_artifact, list_artifacts
from tir.config import WORKSPACE_DIR
from tir.workspace.service import WorkspacePathError, resolve_workspace_path


SAFE_IMAGE_PREVIEW_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/avif",
}


class ArtifactLookupError(ValueError):
    """Raised when an artifact cannot be returned safely."""


def _metadata(artifact: dict) -> dict:
    metadata = artifact.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _is_visible_to_user(artifact: dict, user_id: str | None) -> bool:
    if not user_id:
        return True

    metadata = _metadata(artifact)
    for key in ("user_id", "source_user_id"):
        artifact_user_id = metadata.get(key)
        if artifact_user_id and artifact_user_id != user_id:
            return False
    return True


def _safe_preview_url(artifact: dict, *, workspace_root: Path = WORKSPACE_DIR) -> str | None:
    path = artifact.get("path")
    if not path:
        return None
    if is_source_trace_path(path) or is_governance_file_name(Path(path).name):
        return None

    metadata = _metadata(artifact)
    if (
        not metadata.get("media_kind")
        or metadata.get("mime_type") not in SAFE_IMAGE_PREVIEW_MIME_TYPES
    ):
        return None

    try:
        resolve_workspace_path(path, workspace_root)
    except WorkspacePathError:
        return None

    return f"/api/artifacts/{artifact['artifact_id']}/file"


def _summary_text(value: Any, *, max_chars: int = 240) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def summarize_media_artifact(
    artifact: dict,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Return safe metadata for an artifact without reading file contents."""
    metadata = _metadata(artifact)
    summary = {
        "artifact_id": artifact.get("artifact_id"),
        "title": artifact.get("title"),
        "media_kind": metadata.get("media_kind"),
        "artifact_type": artifact.get("artifact_type"),
        "source": artifact.get("source"),
        "created_at": artifact.get("created_at"),
        "updated_at": artifact.get("updated_at"),
        "path": artifact.get("path"),
        "preview_url": _safe_preview_url(artifact, workspace_root=workspace_root),
        "description": _summary_text(artifact.get("description")),
        "prompt": _summary_text(metadata.get("prompt")),
        "observed_description": _summary_text(metadata.get("observed_description")),
        "generation_backend": metadata.get("generation_backend"),
        "generation_model": metadata.get("generation_model"),
        "workflow_name": metadata.get("workflow_name"),
        "workflow_id": metadata.get("workflow_id"),
        "seed": metadata.get("seed"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "revision_of": artifact.get("revision_of") or metadata.get("revision_of"),
        "source_artifact_id": metadata.get("source_artifact_id"),
        "intended_use": metadata.get("intended_use"),
    }
    return {key: value for key, value in summary.items() if value not in {None, ""}}


def get_media_artifact_reference(
    artifact_id: str,
    *,
    user_id: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Return one safe media artifact reference or a structured rejection."""
    normalized = (artifact_id or "").strip()
    if not normalized:
        return {
            "ok": False,
            "error_type": "invalid_request",
            "error": "artifact_id is required",
        }

    artifact = get_artifact(normalized)
    if artifact is None:
        return {
            "ok": False,
            "error_type": "not_found",
            "error": "Artifact not found",
            "artifact_id": normalized,
        }
    if not _is_visible_to_user(artifact, user_id):
        return {
            "ok": False,
            "error_type": "forbidden",
            "error": "Artifact is not visible to the active household user",
            "artifact_id": normalized,
        }

    path = artifact.get("path") or ""
    if path:
        if is_source_trace_path(path):
            return {
                "ok": False,
                "error_type": "blocked_source_trace",
                "error": SOURCE_TRACE_REJECTION_MESSAGE,
                "artifact_id": normalized,
            }
        if is_governance_file_name(Path(path).name):
            return {
                "ok": False,
                "error_type": "blocked_governance_file",
                "error": GOVERNANCE_FILE_REJECTION_MESSAGE,
                "artifact_id": normalized,
            }
        try:
            resolve_workspace_path(path, workspace_root)
        except WorkspacePathError:
            return {
                "ok": False,
                "error_type": "unsafe_path",
                "error": "Artifact path is outside workspace",
                "artifact_id": normalized,
            }

    return {
        "ok": True,
        "artifact": summarize_media_artifact(artifact, workspace_root=workspace_root),
    }


def _search_blob(artifact: dict) -> str:
    metadata = _metadata(artifact)
    fields = [
        artifact.get("artifact_id"),
        artifact.get("title"),
        artifact.get("description"),
        artifact.get("path"),
        artifact.get("artifact_type"),
        artifact.get("source"),
        metadata.get("media_kind"),
        metadata.get("prompt"),
        metadata.get("negative_prompt"),
        metadata.get("observed_description"),
        metadata.get("generation_backend"),
        metadata.get("generation_model"),
        metadata.get("workflow_name"),
        metadata.get("workflow_id"),
        metadata.get("intended_use"),
    ]
    return "\n".join(str(value).lower() for value in fields if value not in {None, ""})


def _score_artifact(artifact: dict, terms: list[str]) -> int:
    if not terms:
        return 0

    score = 0
    artifact_id = str(artifact.get("artifact_id") or "").lower()
    title = str(artifact.get("title") or "").lower()
    metadata = _metadata(artifact)
    prompt = str(metadata.get("prompt") or "").lower()
    observed = str(metadata.get("observed_description") or "").lower()
    blob = _search_blob(artifact)
    for term in terms:
        if term == artifact_id:
            score += 120
        if term in artifact_id:
            score += 60
        if term and term in title:
            score += 40
        if term and term in prompt:
            score += 20
        if term and term in observed:
            score += 20
        if term and term in blob:
            score += 5
    return score


def search_media_artifacts(
    *,
    query: str | None = None,
    media_kind: str | None = None,
    artifact_type: str | None = None,
    limit: int = 5,
    include_recent: bool = True,
    user_id: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Search artifact metadata by title, id, description, and media provenance."""
    if media_kind is not None and media_kind not in ALLOWED_MEDIA_KINDS:
        return {
            "ok": False,
            "error_type": "invalid_media_kind",
            "error": f"Invalid media_kind: {media_kind}",
        }

    bounded_limit = max(1, min(int(limit or 5), 10))
    normalized_query = (query or "").strip()
    terms = [term.lower() for term in normalized_query.split() if term.strip()]

    try:
        candidates = list_artifacts(
            artifact_type=artifact_type,
            limit=max(100, bounded_limit),
            offset=0,
            workspace_root=workspace_root,
        )
    except ArtifactValidationError as exc:
        return {
            "ok": False,
            "error_type": "invalid_artifact_type",
            "error": str(exc),
        }

    matched = []
    for artifact in candidates:
        if not _is_visible_to_user(artifact, user_id):
            continue
        metadata = _metadata(artifact)
        if media_kind and metadata.get("media_kind") != media_kind:
            continue
        if not normalized_query and not include_recent:
            continue

        score = _score_artifact(artifact, terms)
        if normalized_query and score <= 0:
            continue
        matched.append((score, artifact))

    matched.sort(key=lambda item: (item[0], item[1].get("created_at") or ""), reverse=True)
    results = [
        summarize_media_artifact(artifact, workspace_root=workspace_root)
        for _score, artifact in matched[:bounded_limit]
    ]
    return {
        "ok": True,
        "query": normalized_query,
        "count": len(results),
        "results": results,
    }
