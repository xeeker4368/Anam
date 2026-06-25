"""Backend-agnostic image generation service."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Callable

from tir.artifacts.ingestion import ingest_artifact_file
from tir.config import (
    COMFYUI_BASE_URL,
    COMFYUI_POLL_INTERVAL_SECONDS,
    COMFYUI_TIMEOUT_SECONDS,
    COMFYUI_WORKFLOW_PATH,
    IMAGE_GENERATION_DEFAULT_BACKEND,
    IMAGE_GENERATION_DEFAULT_HEIGHT,
    IMAGE_GENERATION_DEFAULT_WIDTH,
    IMAGE_GENERATION_ENABLED,
    IMAGE_GENERATION_MAX_HEIGHT,
    IMAGE_GENERATION_MAX_PROMPT_CHARS,
    IMAGE_GENERATION_MAX_WIDTH,
    WORKSPACE_DIR,
)
from tir.media.backends.base import (
    ImageGenerationBackend,
    ImageGenerationBackendError,
    ImageGenerationBackendRequest,
    ImageGenerationBackendResult,
)
from tir.media.backends.comfyui import ComfyUIBackend


ALLOWED_IMAGE_BACKENDS = {"comfyui"}
ALLOWED_INTENDED_USES = {"general", "reference"}


class ImageGenerationError(ValueError):
    """Raised when an image generation request is invalid."""


def _failure_trace(
    *,
    backend: str,
    error_type: str,
    message: str,
    status_code: int | None = None,
    safe_url: str | None = None,
    safe_path: str | None = None,
    dry_run: bool = False,
    write: bool = False,
) -> dict:
    return {
        "ok": False,
        "generation_error": True,
        "error_type": error_type,
        "error": message,
        "backend": backend,
        "status_code": status_code,
        "url": safe_url,
        "path": safe_path,
        "dry_run": dry_run,
        "write": write,
        "artifact_created": False,
    }


def _validate_mode(*, dry_run: bool, write: bool) -> None:
    if dry_run == write:
        raise ImageGenerationError("Exactly one of dry_run or write is required")


def _clean_prompt(prompt: str | None, *, max_chars: int) -> str:
    text = (prompt or "").strip()
    if not text:
        raise ImageGenerationError("prompt is required")
    if len(text) > max_chars:
        raise ImageGenerationError(
            f"prompt exceeds {max_chars} character limit"
        )
    return text


def _validate_dimensions(width: int | None, height: int | None) -> tuple[int | None, int | None]:
    if width is not None:
        if width < 1 or width > IMAGE_GENERATION_MAX_WIDTH:
            raise ImageGenerationError(
                f"width must be between 1 and {IMAGE_GENERATION_MAX_WIDTH}"
            )
    if height is not None:
        if height < 1 or height > IMAGE_GENERATION_MAX_HEIGHT:
            raise ImageGenerationError(
                f"height must be between 1 and {IMAGE_GENERATION_MAX_HEIGHT}"
            )
    return width, height


def _validate_backend_name(backend: str | None) -> str:
    selected = (backend or IMAGE_GENERATION_DEFAULT_BACKEND or "").strip().lower()
    if selected not in ALLOWED_IMAGE_BACKENDS:
        raise ImageGenerationError(f"Unsupported image generation backend: {selected}")
    return selected


def _validate_intended_use(intended_use: str | None) -> str:
    selected = (intended_use or "general").strip()
    if selected not in ALLOWED_INTENDED_USES:
        raise ImageGenerationError(
            f"Invalid intended_use: {selected}. Allowed: general, reference"
        )
    return selected


def _validate_backend_filename(filename: str) -> str:
    safe = Path(filename or "generated-image.png").name
    if not safe or safe in {".", ".."} or "/" in filename or "\\" in filename:
        raise ImageGenerationError("backend output filename is unsafe")
    if not Path(safe).suffix:
        safe = f"{safe}.png"
    return safe


def _backend_for_name(backend: str) -> ImageGenerationBackend:
    if backend == "comfyui":
        return ComfyUIBackend(
            base_url=COMFYUI_BASE_URL,
            workflow_path=COMFYUI_WORKFLOW_PATH,
            timeout_seconds=COMFYUI_TIMEOUT_SECONDS,
            poll_interval_seconds=COMFYUI_POLL_INTERVAL_SECONDS,
        )
    raise ImageGenerationError(f"Unsupported image generation backend: {backend}")


def _generation_params(
    *,
    seed: int | None,
    width: int | None,
    height: int | None,
    extra: dict | None,
) -> dict:
    params = dict(extra or {})
    if seed is not None:
        params["seed"] = seed
    if width is not None:
        params["width"] = width
    if height is not None:
        params["height"] = height
    return params


def _safe_metadata_value(value):
    if isinstance(value, (dict, list)):
        json.dumps(value, sort_keys=True)
    return value


def _present(value) -> bool:
    return value is not None and value != ""


def generate_image(
    *,
    prompt: str,
    negative_prompt: str | None = None,
    backend: str | None = None,
    dry_run: bool = False,
    write: bool = False,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
    title: str | None = None,
    user_id: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_artifact_id: str | None = None,
    revision_of: str | None = None,
    intended_use: str | None = "general",
    generation_model: str | None = None,
    workflow_name: str | None = None,
    workflow_id: str | None = None,
    generation_params: dict | None = None,
    backend_factory: Callable[[str], ImageGenerationBackend] | None = None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Validate, optionally generate, and store one generated image artifact."""
    _validate_mode(dry_run=dry_run, write=write)
    selected_backend = _validate_backend_name(backend)
    cleaned_prompt = _clean_prompt(
        prompt,
        max_chars=IMAGE_GENERATION_MAX_PROMPT_CHARS,
    )
    width, height = _validate_dimensions(width, height)
    # Resolve to concrete integers so workflow placeholders always substitute.
    # Validation above already rejected explicit out-of-range values; defaults
    # are known-good. A missing seed picks a random one rather than failing.
    if width is None:
        width = IMAGE_GENERATION_DEFAULT_WIDTH
    if height is None:
        height = IMAGE_GENERATION_DEFAULT_HEIGHT
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    selected_intended_use = _validate_intended_use(intended_use)

    if not IMAGE_GENERATION_ENABLED:
        return _failure_trace(
            backend=selected_backend,
            error_type="config_error",
            message="Image generation is disabled in configuration",
            dry_run=dry_run,
            write=write,
        )

    params = _generation_params(
        seed=seed,
        width=width,
        height=height,
        extra=generation_params,
    )
    request = ImageGenerationBackendRequest(
        prompt=cleaned_prompt,
        negative_prompt=negative_prompt.strip() if negative_prompt else None,
        width=width,
        height=height,
        seed=seed,
        workflow_path=COMFYUI_WORKFLOW_PATH if selected_backend == "comfyui" else None,
        generation_params=params,
    )

    try:
        backend_impl = (
            backend_factory(selected_backend)
            if backend_factory
            else _backend_for_name(selected_backend)
        )
        backend_impl.validate_config()
    except ImageGenerationBackendError as exc:
        return _failure_trace(
            backend=selected_backend,
            error_type=exc.error_type,
            message=str(exc),
            status_code=exc.status_code,
            safe_url=exc.safe_url,
            safe_path=exc.safe_path,
            dry_run=dry_run,
            write=write,
        )
    except Exception as exc:
        return _failure_trace(
            backend=selected_backend,
            error_type="tool_error",
            message=f"{type(exc).__name__}: {exc}",
            dry_run=dry_run,
            write=write,
        )

    if dry_run:
        return {
            "ok": True,
            "generation_error": False,
            "backend": selected_backend,
            "dry_run": True,
            "write": False,
            "artifact_created": False,
            "validated": True,
            "prompt_chars": len(cleaned_prompt),
            "width": width,
            "height": height,
            "intended_use": selected_intended_use,
        }

    try:
        generated = backend_impl.generate(request)
    except ImageGenerationBackendError as exc:
        return _failure_trace(
            backend=selected_backend,
            error_type=exc.error_type,
            message=str(exc),
            status_code=exc.status_code,
            safe_url=exc.safe_url,
            safe_path=exc.safe_path,
            dry_run=dry_run,
            write=write,
        )
    except Exception as exc:
        return _failure_trace(
            backend=selected_backend,
            error_type="tool_error",
            message=f"{type(exc).__name__}: {exc}",
            dry_run=dry_run,
            write=write,
        )

    if not isinstance(generated, ImageGenerationBackendResult):
        return _failure_trace(
            backend=selected_backend,
            error_type="tool_error",
            message="Image backend returned an invalid result",
            dry_run=dry_run,
            write=write,
        )
    if not generated.content:
        return _failure_trace(
            backend=selected_backend,
            error_type="no_output",
            message="Image backend returned no output bytes",
            dry_run=dry_run,
            write=write,
        )

    try:
        filename = _validate_backend_filename(generated.filename)
    except ImageGenerationError as exc:
        return _failure_trace(
            backend=selected_backend,
            error_type="tool_error",
            message=str(exc),
            dry_run=dry_run,
            write=write,
        )
    backend_metadata = {
        key: _safe_metadata_value(value)
        for key, value in (generated.metadata or {}).items()
        if _present(value)
    }
    metadata = {
        **backend_metadata,
        "media_kind": "generated_image",
        "prompt": cleaned_prompt,
        "generation_backend": selected_backend,
        "generation_params": params,
        "intended_use": selected_intended_use,
    }
    if negative_prompt:
        metadata["negative_prompt"] = negative_prompt.strip()
    if generation_model:
        metadata["generation_model"] = generation_model.strip()
    if workflow_name:
        metadata["workflow_name"] = workflow_name.strip()
    if workflow_id:
        metadata["workflow_id"] = workflow_id.strip()
    if seed is not None:
        metadata["seed"] = seed
    if width is not None:
        metadata["width"] = width
    if height is not None:
        metadata["height"] = height
    if source_artifact_id:
        metadata["source_artifact_id"] = source_artifact_id

    result = ingest_artifact_file(
        filename=filename,
        content=generated.content,
        user_id=user_id,
        title=title or filename,
        artifact_type="generated_file",
        source="generation",
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        source_tool_name=f"image_generate:{selected_backend}",
        created_by="tool",
        revision_of=revision_of,
        metadata=metadata,
        workspace_root=workspace_root,
    )

    return {
        "ok": True,
        "generation_error": False,
        "backend": selected_backend,
        "dry_run": False,
        "write": True,
        "artifact_created": True,
        "artifact": result["artifact"],
        "file": result["file"],
        "indexing": result["indexing"],
    }
