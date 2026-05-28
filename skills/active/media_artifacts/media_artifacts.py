"""Chat-callable media artifact tools."""

from __future__ import annotations

from tir import config as config_mod
from tir.artifacts.search import get_media_artifact_reference, search_media_artifacts
from tir.media import image_generation as image_generation_mod
from tir.media.image_generation import ImageGenerationError
from tir.tools.registry import tool


def _context_value(_context, name: str):
    return getattr(_context, name, None) if _context is not None else None


def _shape_generated_image_result(result: dict) -> dict:
    if result.get("generation_error"):
        return result

    artifact = result.get("artifact") or {}
    shaped_artifact = get_media_artifact_reference(
        artifact.get("artifact_id") or "",
    )
    artifact_summary = shaped_artifact.get("artifact") if shaped_artifact.get("ok") else {}
    metadata = artifact.get("metadata") or {}
    return {
        "ok": True,
        "generation_error": False,
        "artifact_created": True,
        "artifact_id": artifact.get("artifact_id"),
        "artifact_title": artifact.get("title"),
        "artifact_type": artifact.get("artifact_type"),
        "media_kind": metadata.get("media_kind"),
        "artifact_path": artifact.get("path"),
        "preview_url": artifact_summary.get("preview_url"),
        "prompt": metadata.get("prompt"),
        "negative_prompt": metadata.get("negative_prompt"),
        "backend": result.get("backend") or metadata.get("generation_backend"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "seed": metadata.get("seed"),
        "revision_of": artifact.get("revision_of") or metadata.get("revision_of"),
        "source_artifact_id": metadata.get("source_artifact_id"),
        "indexing": result.get("indexing"),
    }


@tool(
    name="media_search",
    description=(
        "Search local generated/uploaded media artifact metadata by title, "
        "artifact id, description, prompt, or provenance. Returns safe metadata "
        "and preview URLs only, not file contents."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional title, artifact id, description, prompt, or provenance text to search for.",
            },
            "media_kind": {
                "type": "string",
                "enum": ["generated_image", "uploaded_image", "screenshot"],
                "description": "Optional media kind filter.",
            },
            "artifact_type": {
                "type": "string",
                "description": "Optional artifact type filter such as generated_file or image.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Maximum number of results to return.",
            },
            "include_recent": {
                "type": "boolean",
                "description": "When query is empty, return recent matching artifacts.",
            },
        },
    },
)
def media_search(
    query: str | None = None,
    media_kind: str | None = None,
    artifact_type: str | None = None,
    limit: int = 5,
    include_recent: bool = True,
    _context=None,
) -> dict:
    return search_media_artifacts(
        query=query,
        media_kind=media_kind,
        artifact_type=artifact_type,
        limit=limit,
        include_recent=include_recent,
        user_id=_context_value(_context, "user_id"),
    )


@tool(
    name="media_get",
    description=(
        "Get safe metadata for one generated or uploaded media artifact by "
        "artifact id. Returns preview URL when available; never returns raw bytes."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "artifact_id": {
                "type": "string",
                "description": "Artifact id to inspect.",
            },
        },
        "required": ["artifact_id"],
    },
)
def media_get(artifact_id: str, _context=None) -> dict:
    return get_media_artifact_reference(
        artifact_id,
        user_id=_context_value(_context, "user_id"),
    )


@tool(
    name="image_generate",
    description=(
        "Generate an ordinary image/media artifact only when the user explicitly "
        "asks for image generation and chat image generation is enabled. This is "
        "an ordinary media/reference artifact workflow, not an identity workflow. "
        "Returns safe artifact metadata and a preview URL, never raw image bytes."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Required image generation prompt.",
            },
            "negative_prompt": {
                "type": "string",
                "description": "Optional negative prompt.",
            },
            "title": {
                "type": "string",
                "description": "Optional artifact title for later lookup.",
            },
            "width": {
                "type": "integer",
                "minimum": 1,
                "description": "Optional image width, bounded by configuration.",
            },
            "height": {
                "type": "integer",
                "minimum": 1,
                "description": "Optional image height, bounded by configuration.",
            },
            "seed": {
                "type": "integer",
                "description": "Optional generation seed.",
            },
            "backend": {
                "type": "string",
                "description": "Optional backend name; defaults to configured backend.",
            },
            "intended_use": {
                "type": "string",
                "enum": ["general", "reference"],
                "description": "Allowed intended use for ordinary generated media.",
            },
            "source_artifact_id": {
                "type": "string",
                "description": "Optional source/reference artifact id.",
            },
            "revision_of": {
                "type": "string",
                "description": "Optional artifact id this output revises.",
            },
        },
        "required": ["prompt"],
    },
)
def image_generate(
    prompt: str,
    negative_prompt: str | None = None,
    title: str | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    backend: str | None = None,
    intended_use: str = "general",
    source_artifact_id: str | None = None,
    revision_of: str | None = None,
    _context=None,
) -> dict:
    if not config_mod.IMAGE_GENERATION_ALLOW_AGENT_TOOL:
        return {
            "ok": False,
            "generation_error": True,
            "error_type": "config_error",
            "error": "Image generation is not enabled for chat tools.",
            "artifact_created": False,
        }
    if not config_mod.IMAGE_GENERATION_ENABLED:
        return {
            "ok": False,
            "generation_error": True,
            "error_type": "config_error",
            "error": "Image generation is disabled in configuration.",
            "artifact_created": False,
        }

    user_id = _context_value(_context, "user_id")
    if source_artifact_id:
        source_reference = get_media_artifact_reference(
            source_artifact_id,
            user_id=user_id,
        )
        if not source_reference.get("ok"):
            return {
                **source_reference,
                "generation_error": True,
                "artifact_created": False,
            }
    if revision_of:
        revision_reference = get_media_artifact_reference(
            revision_of,
            user_id=user_id,
        )
        if not revision_reference.get("ok"):
            return {
                **revision_reference,
                "generation_error": True,
                "artifact_created": False,
            }

    try:
        result = image_generation_mod.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            backend=backend,
            write=True,
            dry_run=False,
            width=width,
            height=height,
            seed=seed,
            title=title,
            user_id=user_id,
            source_conversation_id=_context_value(_context, "conversation_id"),
            source_message_id=_context_value(_context, "source_message_id"),
            source_artifact_id=source_artifact_id,
            revision_of=revision_of,
            intended_use=intended_use,
        )
    except ImageGenerationError as exc:
        return {
            "ok": False,
            "generation_error": True,
            "error_type": "invalid_request",
            "error": str(exc),
            "artifact_created": False,
        }

    return _shape_generated_image_result(result)
