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


def render_tool_envelope(envelope: dict) -> tuple[bool, str]:
    """Render a registry dispatch envelope for stream/model tool context.

    Returns ``(effective_ok, rendered)``. ``effective_ok`` is False when the
    tool crashed (outer ``ok`` False) OR when the tool ran but returned an
    honest inner failure (``value["ok"] is False``). The outer ``ok`` from
    ``registry.dispatch`` only means "the tool ran without raising", so callers
    must use ``effective_ok`` to decide success.
    """
    if envelope.get("ok"):
        value = envelope.get("value")
        effective_ok = not (isinstance(value, dict) and value.get("ok") is False)
        return effective_ok, render_tool_result(value)

    return False, f"Error: {envelope.get('error', 'unknown tool error')}"


def frame_failed_tool_message(tool_name: str, rendered: str, envelope: dict) -> str:
    """Wrap a failed tool's rendered output with an explicit failure signal.

    The model reads tool results as text; a buried JSON ``ok: false`` is easy to
    miss and gets narrated as success. This prepends a plain-language statement
    so failure is unambiguous and tool-agnostic.
    """
    value = envelope.get("value")
    if isinstance(value, dict):
        message = value.get("error") or value.get("error_type")
    else:
        message = envelope.get("error")
    detail = f" Error: {message}." if message else ""
    return (
        f"TOOL FAILED — `{tool_name}` did not succeed and produced no usable "
        f"result.{detail} Do not claim it succeeded or invent its output "
        f"(e.g. an artifact, link, or content).\n"
        f"Raw tool result:\n{rendered}"
    )
