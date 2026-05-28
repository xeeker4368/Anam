"""Context passed from runtime callers into local Python tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolContext:
    """Safe request context available to tools that accept ``_context``."""

    user_id: str | None = None
    conversation_id: str | None = None
    source_message_id: str | None = None
    request_id: str | None = None
