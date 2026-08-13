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


def summarize_generated_image_result(value: dict) -> str | None:
    """Minimal model-visible confirmation for a successful image_generate result.

    The full result dict still flows to the frontend card (via the tool_result
    event's selection), the streamed event, and the persisted trace — only the
    text the MODEL reads is reduced. A rich JSON block (artifact_id, path, seed,
    preview_url, prompt, ...) is a copyable template the model imitates as a fake
    tool result on later turns; a minimal confirmation removes that template while
    still telling the model the generation succeeded and how to refer to it.
    """
    if not isinstance(value, dict):
        return None
    if value.get("ok") is not True or not value.get("artifact_created"):
        return None
    artifact_id = value.get("artifact_id")
    if not artifact_id:
        return None
    return f"image generated; artifact_id={artifact_id}; shown to user in the chat UI"


def summarize_tool_result_for_model(tool_name: str, value) -> str | None:
    """Return a minimal model-visible summary for tools whose full result is an
    imitable template, else None (caller falls back to the full rendered text).

    Media tools only, mirroring the per-tool dispatch of
    selection_metadata_for_tool_result / frame_failed_tool_message. Reduces ONLY
    the model-facing tool message; the structured value, stream event, card
    selection, and trace are unchanged.
    """
    if tool_name == "image_generate":
        return summarize_generated_image_result(value)
    return None


def summarize_tool_failure(tool_name: str, envelope: dict) -> str:
    """One-line, tool-agnostic failure summary for logging.

    Pulls ``error_type``/``error`` from the inner tool result (or the dispatch
    error when the tool crashed) so failures are visible in the log instead of
    silent.
    """
    value = envelope.get("value")
    if isinstance(value, dict):
        error_type = value.get("error_type")
        message = value.get("error")
    else:
        error_type = None
        message = envelope.get("error")
    parts = [f"tool '{tool_name}' failed"]
    if error_type:
        parts.append(f"error_type={error_type}")
    if message:
        parts.append(f"error={message}")
    return "; ".join(parts)
