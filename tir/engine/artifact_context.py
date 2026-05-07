"""Bounded recent-artifact context for artifact-related chat turns."""

from tir.artifacts.service import list_recent_artifacts_for_user
from tir.artifacts.source_roles import display_origin, display_source_role


RECENT_ARTIFACT_LIMIT = 5
RECENT_ARTIFACT_CONTEXT_CHAR_BUDGET = 2000

_INTENT_TERMS = {
    "upload",
    "uploaded",
    "file",
    "files",
    "artifact",
    "artifacts",
    "attachment",
    "attachments",
    "document",
    "documents",
}

_INTENT_PHRASES = {
    "can you see it",
    "can you see them",
    "do you see it",
    "do you see them",
    "what did i upload",
    "what did i just upload",
    "recent upload",
    "recent uploads",
}

_TRUNCATION_MARKER = "\n[recent artifact context truncated]"


def has_recent_artifact_intent(text: str) -> bool:
    """Return True when a prompt likely asks about recent files/artifacts."""
    lowered = (text or "").lower()
    if any(phrase in lowered for phrase in _INTENT_PHRASES):
        return True

    words = {
        word.strip(".,!?;:()[]{}\"'")
        for word in lowered.split()
    }
    return bool(words & _INTENT_TERMS)


def _short_id(artifact_id: str | None) -> str:
    if not artifact_id:
        return ""
    return str(artifact_id)[:8]


def _artifact_filename(artifact: dict, metadata: dict) -> str:
    return (
        metadata.get("filename")
        or metadata.get("safe_filename")
        or artifact.get("path")
        or ""
    )


def _format_artifact_line(artifact: dict) -> str:
    metadata = artifact.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    title = artifact.get("title") or _artifact_filename(artifact, metadata) or "Untitled artifact"
    filename = _artifact_filename(artifact, metadata)
    source_role = display_source_role(metadata.get("source_role"))
    origin = display_origin(metadata.get("origin"))
    indexing_status = metadata.get("indexing_status") or "unknown"
    artifact_id = _short_id(artifact.get("artifact_id"))

    parts = [
        str(title),
        f"type={artifact.get('artifact_type') or 'unknown'}",
        f"role={source_role}",
        f"origin={origin}",
        f"indexing={indexing_status}",
        f"status={artifact.get('status') or 'unknown'}",
    ]
    if filename and filename != title:
        parts.insert(1, f"file={filename}")
    if artifact.get("created_at"):
        parts.append(f"created={artifact['created_at']}")
    if artifact_id:
        parts.append(f"id={artifact_id}")
    if artifact.get("revision_of"):
        parts.append(f"revision_of={_short_id(artifact.get('revision_of'))}")

    return "- " + ", ".join(parts)


def _cap_context(text: str) -> tuple[str, bool]:
    if len(text) <= RECENT_ARTIFACT_CONTEXT_CHAR_BUDGET:
        return text, False

    max_body_chars = RECENT_ARTIFACT_CONTEXT_CHAR_BUDGET - len(_TRUNCATION_MARKER)
    if max_body_chars < 0:
        return _TRUNCATION_MARKER.strip(), True
    return text[:max_body_chars].rstrip() + _TRUNCATION_MARKER, True


def build_recent_artifacts_context(
    *,
    user_id: str,
    limit: int = RECENT_ARTIFACT_LIMIT,
) -> tuple[str | None, dict]:
    """Build a compact metadata-only recent artifact context block."""
    effective_limit = min(max(limit, 1), RECENT_ARTIFACT_LIMIT)
    artifacts = list_recent_artifacts_for_user(
        user_id=user_id,
        limit=effective_limit,
    )
    if not artifacts:
        return None, {
            "included": False,
            "artifact_count": 0,
            "limit": effective_limit,
            "chars": 0,
            "truncated": False,
        }

    lines = [
        "Recent artifacts available as uploaded source material:",
        *[_format_artifact_line(artifact) for artifact in artifacts],
    ]
    context, truncated = _cap_context("\n".join(lines))
    return context, {
        "included": True,
        "artifact_count": len(artifacts),
        "limit": effective_limit,
        "chars": len(context),
        "truncated": truncated,
    }
