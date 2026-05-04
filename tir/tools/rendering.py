"""Shared rendering helpers for tool results."""

import json
from typing import Any


def render_tool_result(result: Any) -> str:
    """Render tool output as model/debug-friendly text.

    Structured JSON-compatible values are rendered as JSON. Plain strings stay
    unchanged so text-only tools do not get extra quotes.
    """
    if isinstance(result, str):
        return result

    try:
        return json.dumps(result, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(result)
