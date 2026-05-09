"""Artifact origin/source-role vocabulary and display helpers."""

ALLOWED_ORIGINS = {
    "user_upload",
    "generated",
    "autonomous_research",
    "runtime",
    "conversation",
    "tool",
    "reflection_journal",
    "system",
    "unknown",
}

ALLOWED_SOURCE_ROLES = {
    "uploaded_source",
    "generated_artifact",
    "research_reference",
    "runtime_guidance",
    "current_project_state",
    "correction",
    "draft",
    "journal",
    "log",
    "unknown",
}

_SOURCE_ROLE_LABELS = {
    "uploaded_source": "Uploaded source",
    "generated_artifact": "Generated artifact",
    "research_reference": "Research reference",
    "runtime_guidance": "Runtime guidance",
    "current_project_state": "Current project state",
    "correction": "Correction",
    "draft": "Draft",
    "journal": "Journal",
    "log": "Log",
    "unknown": "Unknown source role",
}

_ORIGIN_LABELS = {
    "user_upload": "User upload",
    "generated": "Generated",
    "autonomous_research": "Autonomous research",
    "runtime": "Runtime",
    "conversation": "Conversation",
    "tool": "Tool",
    "reflection_journal": "Reflection journal",
    "system": "System",
    "unknown": "Unknown origin",
}

_AUTHORITY_SOURCE_ROLE_FALLBACK = {
    "source_material": "uploaded_source",
    "draft": "draft",
    "log": "log",
    "correction": "correction",
    "current_project_state": "current_project_state",
    "operational_guidance": "runtime_guidance",
    "unknown": "unknown",
}


def validate_origin(origin: str) -> str:
    """Validate and return an artifact origin value."""
    if origin not in ALLOWED_ORIGINS:
        raise ValueError(f"Invalid artifact origin: {origin}")
    return origin


def validate_source_role(source_role: str) -> str:
    """Validate and return an artifact source_role value."""
    if source_role not in ALLOWED_SOURCE_ROLES:
        raise ValueError(f"Invalid artifact source_role: {source_role}")
    return source_role


def source_role_from_authority(authority: str | None) -> str:
    """Map deprecated authority values to source_role for old dev rows/callers."""
    return _AUTHORITY_SOURCE_ROLE_FALLBACK.get(authority or "unknown", "unknown")


def default_origin(
    *,
    artifact_type: str = "uploaded_file",
    source: str = "upload",
    created_by: str = "user",
) -> str:
    """Return the default origin for a new artifact."""
    if artifact_type == "generated_file":
        return "generated"
    if source == "upload" or artifact_type == "uploaded_file":
        return "user_upload"
    if source == "autonomous_research":
        return "autonomous_research"
    if created_by == "tool":
        return "tool"
    return "unknown"


def default_source_role(
    *,
    artifact_type: str = "uploaded_file",
    status: str = "active",
    origin: str = "unknown",
    authority: str | None = None,
) -> str:
    """Return the default source role for a new artifact."""
    if authority:
        return source_role_from_authority(authority)
    if artifact_type == "generated_file" and status == "draft":
        return "draft"
    if artifact_type == "generated_file" or origin == "generated":
        return "generated_artifact"
    if origin == "autonomous_research":
        return "research_reference"
    if origin == "user_upload" or artifact_type == "uploaded_file":
        return "uploaded_source"
    return "unknown"


def source_trust_for_source_role(source_role: str | None) -> str:
    """Map source_role to the existing retrieval source_trust vocabulary."""
    if source_role in {
        "generated_artifact",
        "runtime_guidance",
        "current_project_state",
        "correction",
        "draft",
        "log",
        "journal",
    }:
        return "firsthand"
    return "thirdhand"


def display_source_role(source_role: str | None, authority: str | None = None) -> str:
    """Return a human-readable source role, with old authority fallback."""
    effective = source_role or source_role_from_authority(authority)
    return _SOURCE_ROLE_LABELS.get(effective, _SOURCE_ROLE_LABELS["unknown"])


def display_origin(origin: str | None) -> str:
    """Return a human-readable origin."""
    return _ORIGIN_LABELS.get(origin or "unknown", _ORIGIN_LABELS["unknown"])
