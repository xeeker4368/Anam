"""Backend protocol for image generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ImageGenerationBackendRequest:
    """Normalized request passed to a concrete image backend."""

    prompt: str
    negative_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    seed: int | None = None
    workflow_path: str | None = None
    generation_params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ImageGenerationBackendResult:
    """Image bytes plus backend-supplied provenance."""

    content: bytes
    filename: str
    mime_type: str = "image/png"
    metadata: dict = field(default_factory=dict)


class ImageGenerationBackendError(RuntimeError):
    """Structured backend failure."""

    def __init__(
        self,
        message: str,
        *,
        error_type: str = "tool_error",
        status_code: int | None = None,
        safe_url: str | None = None,
        safe_path: str | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.safe_url = safe_url
        self.safe_path = safe_path


class ImageGenerationBackend(Protocol):
    """Protocol implemented by image generation backends."""

    backend_name: str

    def validate_config(self) -> None:
        """Validate backend configuration without generating."""

    def generate(
        self,
        request: ImageGenerationBackendRequest,
    ) -> ImageGenerationBackendResult:
        """Generate one image or raise ImageGenerationBackendError."""
