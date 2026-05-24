"""Media artifact metadata helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_MEDIA_KINDS = {
    "uploaded_image",
    "screenshot",
    "generated_image",
}

ALLOWED_INTERPRETATION_SOURCES = {
    "human",
    "model",
    "tool",
    "none",
}

ALLOWED_INTENDED_USES = {
    "general",
    "reference",
}

MEDIA_PROVENANCE_FIELDS = {
    "media_kind",
    "source_user_id",
    "source_conversation_id",
    "source_message_id",
    "source_artifact_id",
    "revision_of",
    "prompt",
    "negative_prompt",
    "generation_backend",
    "generation_model",
    "workflow_name",
    "workflow_id",
    "generation_params",
    "seed",
    "width",
    "height",
    "observed_description",
    "human_confirmed",
    "uncertainty_label",
    "interpretation_source",
    "intended_use",
}


class MediaMetadataError(ValueError):
    """Raised when media metadata is invalid."""


def is_image_mime_type(mime_type: str | None) -> bool:
    """Return whether a MIME type is an image type."""
    return bool(mime_type and mime_type.lower().startswith("image/"))


def is_image_filename(filename: str) -> bool:
    """Return whether a file name has a common image extension."""
    extension = Path(filename).suffix.lower()
    return extension in {
        ".avif",
        ".bmp",
        ".gif",
        ".heic",
        ".heif",
        ".jpeg",
        ".jpg",
        ".png",
        ".svg",
        ".tif",
        ".tiff",
        ".webp",
    }


def is_image_artifact(filename: str, mime_type: str | None) -> bool:
    """Return whether a file should be treated as image media."""
    return is_image_mime_type(mime_type) or is_image_filename(filename)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_bool(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    raise MediaMetadataError("human_confirmed must be a boolean")


def _clean_generation_params(value: Any) -> dict | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise MediaMetadataError("generation_params must be a JSON object") from exc
        if isinstance(parsed, dict):
            return parsed
    raise MediaMetadataError("generation_params must be a JSON object")


def default_media_kind(
    *,
    source: str,
    artifact_type: str,
    created_by: str,
) -> str:
    """Return the default media kind for an image artifact."""
    if (
        artifact_type == "generated_file"
        or source in {"generation", "generated"}
        or created_by in {"tool", "anam"}
    ):
        return "generated_image"
    return "uploaded_image"


def normalize_media_metadata(
    *,
    filename: str,
    mime_type: str | None,
    artifact_type: str,
    source: str,
    created_by: str,
    user_id: str | None,
    source_conversation_id: str | None,
    source_message_id: str | None,
    revision_of: str | None,
    metadata: dict | None,
) -> tuple[str, dict]:
    """Normalize optional media metadata and return artifact type plus metadata."""
    incoming = dict(metadata or {})
    image_file = is_image_artifact(filename, mime_type)
    supplied_kind = _clean_text(incoming.get("media_kind"))
    has_media_fields = any(
        key in incoming and incoming.get(key) is not None and incoming.get(key) != ""
        for key in MEDIA_PROVENANCE_FIELDS
    )

    if supplied_kind and supplied_kind not in ALLOWED_MEDIA_KINDS:
        raise MediaMetadataError(f"Invalid media_kind: {supplied_kind}")

    if not image_file and not has_media_fields:
        return artifact_type, incoming

    if image_file and artifact_type == "uploaded_file":
        artifact_type = "image"

    media_kind = supplied_kind or default_media_kind(
        source=source,
        artifact_type=artifact_type,
        created_by=created_by,
    )

    interpretation_source = _clean_text(incoming.get("interpretation_source"))
    if interpretation_source and interpretation_source not in ALLOWED_INTERPRETATION_SOURCES:
        raise MediaMetadataError(f"Invalid interpretation_source: {interpretation_source}")

    intended_use = _clean_text(incoming.get("intended_use"))
    if intended_use and intended_use not in ALLOWED_INTENDED_USES:
        raise MediaMetadataError(f"Invalid intended_use: {intended_use}")

    normalized = {
        **incoming,
        "media_kind": media_kind,
        "media_foundation_version": "image_media_foundation_v1",
    }
    if user_id:
        normalized["source_user_id"] = user_id
    if source_conversation_id:
        normalized["source_conversation_id"] = source_conversation_id
    if source_message_id:
        normalized["source_message_id"] = source_message_id
    if revision_of:
        normalized["revision_of"] = revision_of

    for key in (
        "source_artifact_id",
        "prompt",
        "negative_prompt",
        "generation_backend",
        "generation_model",
        "workflow_name",
        "workflow_id",
        "observed_description",
        "uncertainty_label",
    ):
        cleaned = _clean_text(normalized.get(key))
        if cleaned is not None:
            normalized[key] = cleaned
        elif key in normalized:
            normalized.pop(key)

    normalized["human_confirmed"] = _clean_bool(normalized.get("human_confirmed"))
    if normalized["human_confirmed"] is None:
        normalized["human_confirmed"] = False

    params = _clean_generation_params(normalized.get("generation_params"))
    if params is not None:
        normalized["generation_params"] = params
    elif "generation_params" in normalized:
        normalized.pop("generation_params")

    if interpretation_source:
        normalized["interpretation_source"] = interpretation_source
    elif "interpretation_source" in normalized:
        normalized.pop("interpretation_source")

    if intended_use:
        normalized["intended_use"] = intended_use
    else:
        normalized["intended_use"] = "general"

    return artifact_type, normalized


def media_indexing_metadata(metadata: dict | None) -> dict:
    """Return media metadata fields safe to attach to retrieval chunks."""
    if not metadata:
        return {}
    chunk_metadata = {}
    for key, value in metadata.items():
        if key not in MEDIA_PROVENANCE_FIELDS and key != "media_foundation_version":
            continue
        if isinstance(value, (dict, list)):
            chunk_metadata[key] = json.dumps(value, sort_keys=True)
        else:
            chunk_metadata[key] = value
    return chunk_metadata
