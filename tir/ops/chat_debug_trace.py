"""Structured chat request debug trace logging."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tir import config

# Compatibility alias only — a snapshot taken at import time. Same trap as
# tir/memory/chroma.py: `from tir.config import DATA_DIR` binds a separate
# name here, so patching `tir.config.DATA_DIR` never reached it. Resolution
# goes through `chat_debug_trace_path()`, which reads config at call time.
CHAT_DEBUG_TRACE_PATH = config.DATA_DIR / "chat_debug.jsonl"


def chat_debug_trace_path() -> Path:
    """Return the CURRENT configured chat debug trace path."""
    return config.DATA_DIR / "chat_debug.jsonl"

_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?secret|api[_-]?key|authorization|token)\b\s*[:=]\s*['\"]?[^'\"\s,}]+"
)


def redact_debug_value(value: Any) -> Any:
    """Recursively redact secret-shaped strings before JSONL logging."""
    if isinstance(value, str):
        redacted = _BEARER_RE.sub("Bearer [REDACTED]", value)
        return _SECRET_RE.sub(r"\1=[REDACTED]", redacted)
    if isinstance(value, dict):
        return {str(key): redact_debug_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [redact_debug_value(item) for item in value]
    return value


def safe_chat_model_options(options: dict[str, Any]) -> dict[str, Any]:
    """Return only chat model options useful for diagnostics."""
    safe_keys = {"temperature", "think", "num_ctx"}
    return {key: options[key] for key in safe_keys if key in options}


def write_chat_debug_trace(record: dict[str, Any], *, path: Path | None = None) -> None:
    """Append one compact JSONL chat debug trace record."""
    output_path = path or chat_debug_trace_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_record = redact_debug_value(record)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_record, sort_keys=True, separators=(",", ":")) + "\n")
