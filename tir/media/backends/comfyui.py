"""ComfyUI image generation backend."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests

from tir.config import PROJECT_ROOT
from tir.media.backends.base import (
    ImageGenerationBackendError,
    ImageGenerationBackendRequest,
    ImageGenerationBackendResult,
)


LOCAL_COMFYUI_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _safe_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ImageGenerationBackendError(
            "ComfyUI base_url must use http or https",
            error_type="config_error",
            safe_url=base_url,
        )
    if parsed.hostname not in LOCAL_COMFYUI_HOSTS:
        raise ImageGenerationBackendError(
            "ComfyUI base_url must be localhost in v1",
            error_type="config_error",
            safe_url=f"{parsed.scheme}://{parsed.netloc}",
        )
    return base_url.rstrip("/")


def _workflow_path(path_text: str | None) -> Path:
    if not path_text:
        raise ImageGenerationBackendError(
            "ComfyUI workflow_path is required",
            error_type="config_error",
        )
    path = Path(path_text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ImageGenerationBackendError(
            "ComfyUI workflow_path must be inside the project directory",
            error_type="config_error",
            safe_path=str(path),
        ) from exc
    if not resolved.exists():
        raise ImageGenerationBackendError(
            "ComfyUI workflow_path does not exist",
            error_type="config_error",
            safe_path=str(path),
        )
    return resolved


def _replace_placeholders(value, replacements: dict[str, object]):
    if isinstance(value, dict):
        return {
            key: _replace_placeholders(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_placeholders(item, replacements) for item in value]
    if isinstance(value, str):
        if value in replacements:
            return replacements[value]
        for key, replacement in replacements.items():
            value = value.replace(key, str(replacement))
        return value
    return value


def _load_workflow(path: Path, request: ImageGenerationBackendRequest) -> dict:
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImageGenerationBackendError(
            "ComfyUI workflow JSON is invalid",
            error_type="config_error",
            safe_path=str(path),
        ) from exc

    if not isinstance(workflow, dict):
        raise ImageGenerationBackendError(
            "ComfyUI workflow JSON must be an object",
            error_type="config_error",
            safe_path=str(path),
        )

    replacements = {
        "{{prompt}}": request.prompt,
        "{{negative_prompt}}": request.negative_prompt or "",
    }
    if request.width is not None:
        replacements["{{width}}"] = request.width
    if request.height is not None:
        replacements["{{height}}"] = request.height
    if request.seed is not None:
        replacements["{{seed}}"] = request.seed
    return _replace_placeholders(workflow, replacements)


def _request_error(exc: requests.RequestException, safe_url: str) -> ImageGenerationBackendError:
    if isinstance(exc, requests.Timeout):
        return ImageGenerationBackendError(
            "ComfyUI request timed out",
            error_type="timeout",
            safe_url=safe_url,
        )
    return ImageGenerationBackendError(
        "ComfyUI backend unavailable",
        error_type="backend_unavailable",
        safe_url=safe_url,
    )


def _first_output_image(history: dict) -> dict | None:
    for node in (history.get("outputs") or {}).values():
        images = node.get("images") if isinstance(node, dict) else None
        if images:
            image = images[0]
            if isinstance(image, dict):
                return image
    return None


class ComfyUIBackend:
    """Generate images through a local ComfyUI server."""

    backend_name = "comfyui"

    def __init__(
        self,
        *,
        base_url: str,
        workflow_path: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ):
        self.base_url = _safe_base_url(base_url)
        self.workflow_path = workflow_path
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def validate_config(self) -> None:
        """Validate static ComfyUI configuration."""
        _workflow_path(self.workflow_path)

    def generate(
        self,
        request: ImageGenerationBackendRequest,
    ) -> ImageGenerationBackendResult:
        self.validate_config()
        workflow_path = _workflow_path(request.workflow_path or self.workflow_path)
        workflow = _load_workflow(workflow_path, request)
        prompt_url = f"{self.base_url}/prompt"
        try:
            response = requests.post(
                prompt_url,
                json={"prompt": workflow},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise _request_error(exc, prompt_url) from exc

        if response.status_code >= 400:
            raise ImageGenerationBackendError(
                "ComfyUI prompt request failed",
                error_type="tool_error",
                status_code=response.status_code,
                safe_url=prompt_url,
            )

        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            raise ImageGenerationBackendError(
                "ComfyUI did not return a prompt_id",
                error_type="no_output",
                safe_url=prompt_url,
            )

        deadline = time.monotonic() + self.timeout_seconds
        history_url = f"{self.base_url}/history/{prompt_id}"
        history_item = None
        while time.monotonic() < deadline:
            try:
                history_response = requests.get(
                    history_url,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise _request_error(exc, history_url) from exc
            if history_response.status_code >= 400:
                raise ImageGenerationBackendError(
                    "ComfyUI history request failed",
                    error_type="tool_error",
                    status_code=history_response.status_code,
                    safe_url=history_url,
                )
            history = history_response.json()
            history_item = history.get(prompt_id)
            if history_item:
                break
            time.sleep(self.poll_interval_seconds)

        if not history_item:
            raise ImageGenerationBackendError(
                "ComfyUI generation timed out",
                error_type="timeout",
                safe_url=history_url,
            )

        image = _first_output_image(history_item)
        if not image:
            raise ImageGenerationBackendError(
                "ComfyUI completed without an output image",
                error_type="no_output",
                safe_url=history_url,
            )

        filename = str(image.get("filename") or "")
        image_type = str(image.get("type") or "output")
        subfolder = str(image.get("subfolder") or "")
        if not filename:
            raise ImageGenerationBackendError(
                "ComfyUI output image did not include a filename",
                error_type="no_output",
                safe_url=history_url,
            )

        view_url = f"{self.base_url}/view"
        query = urlencode(
            {
                "filename": filename,
                "subfolder": subfolder,
                "type": image_type,
            }
        )
        safe_view_url = f"{view_url}?filename={filename}&type={image_type}"
        try:
            image_response = requests.get(
                f"{view_url}?{query}",
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise _request_error(exc, safe_view_url) from exc
        if image_response.status_code >= 400:
            raise ImageGenerationBackendError(
                "ComfyUI image fetch failed",
                error_type="tool_error",
                status_code=image_response.status_code,
                safe_url=safe_view_url,
            )
        if not image_response.content:
            raise ImageGenerationBackendError(
                "ComfyUI image fetch returned no bytes",
                error_type="no_output",
                safe_url=safe_view_url,
            )

        return ImageGenerationBackendResult(
            content=image_response.content,
            filename=Path(filename).name,
            mime_type=image_response.headers.get("content-type", "image/png"),
            metadata={
                "workflow_id": prompt_id,
                "workflow_path": workflow_path.name,
                "comfyui_output_type": image_type,
            },
        )
