"""Central read-only capability status for Project Anam."""

import os
from copy import deepcopy

from tir import config


ALLOWED_MODES = {
    "disabled",
    "read_only",
    "manual",
    "assisted",
    "autonomous",
    "write_enabled",
    "staged_only",
}

ALLOWED_STATUSES = {
    "available",
    "unavailable",
    "disabled",
    "not_implemented",
    "not_configured",
    "staged_only",
}


_CAPABILITY_DEFINITIONS = [
    {
        "key": "memory_search",
        "label": "Memory Search",
        "implemented": True,
        "mode": "read_only",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Searches indexed Project Anam memory.",
    },
    {
        "key": "web_search",
        "label": "Web Search",
        "implemented": True,
        "mode": "read_only",
        "requires_approval": False,
        "source_of_truth": True,
        "real_time": True,
        "notes": "Uses configured SearXNG provider.",
    },
    {
        "key": "web_fetch",
        "label": "Web Fetch",
        "implemented": True,
        "mode": "read_only",
        "requires_approval": False,
        "source_of_truth": True,
        "real_time": True,
        "notes": "Fetches one public HTTP/HTTPS page through the web_fetch safety policy.",
    },
    {
        "key": "moltbook_read_only",
        "label": "Moltbook Read-Only",
        "implemented": True,
        "mode": "read_only",
        "requires_approval": False,
        "source_of_truth": True,
        "real_time": True,
        "notes": "Read-only Moltbook tools; write actions remain disabled.",
    },
    {
        "key": "backups",
        "label": "Backups",
        "implemented": True,
        "mode": "manual",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Explicit admin backup and restore commands.",
    },
    {
        "key": "memory_maintenance",
        "label": "Memory Maintenance",
        "implemented": True,
        "mode": "manual",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Explicit admin memory audit, repair, and checkpoint commands.",
    },
    {
        "key": "file_uploads",
        "label": "File Uploads",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "image_generation",
        "label": "Image Generation",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "autonomous_research",
        "label": "Autonomous Research",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "reflection_journal",
        "label": "Reflection Journal",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "review_queue",
        "label": "Review Queue",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "code_sandbox",
        "label": "Code Sandbox",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "speech",
        "label": "Speech",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "vision",
        "label": "Vision",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": False,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Not implemented.",
    },
    {
        "key": "write_actions",
        "label": "Write Actions",
        "implemented": False,
        "mode": "disabled",
        "requires_approval": True,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Write/action capability is not implemented.",
    },
    {
        "key": "self_modification",
        "label": "Self-Modification",
        "implemented": False,
        "mode": "staged_only",
        "requires_approval": True,
        "source_of_truth": False,
        "real_time": False,
        "notes": "Future self-modification must remain staged, traceable, and approved.",
    },
]


def get_tool_names(registry=None) -> set[str]:
    """Return tool names from the active registry, tolerating missing registries."""
    if registry is None:
        return set()

    try:
        tools = registry.list_tools()
    except Exception:
        return set()

    names = set()
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def list_capability_definitions() -> list[dict]:
    """Return static capability definitions without runtime availability."""
    return deepcopy(_CAPABILITY_DEFINITIONS)


def _status_for_current_capability(available: bool, configured: bool = True) -> str:
    if not available:
        return "unavailable"
    if not configured:
        return "not_configured"
    return "available"


def _base_runtime_state(definition: dict) -> dict:
    capability = deepcopy(definition)
    implemented = bool(capability["implemented"])
    capability["available"] = implemented
    capability["configured"] = implemented
    capability["enabled"] = implemented
    if not implemented:
        capability["available"] = False
        capability["configured"] = False
        capability["enabled"] = False
        capability["status"] = (
            "staged_only" if capability["mode"] == "staged_only" else "not_implemented"
        )
        capability["reason"] = "not_implemented"
    else:
        capability["status"] = "available"
        capability["reason"] = None
    return capability


def _resolve_capability(definition: dict, tool_names: set[str]) -> dict:
    capability = _base_runtime_state(definition)
    key = capability["key"]

    if key == "memory_search":
        available = "memory_search" in tool_names
        capability.update(
            available=available,
            configured=True,
            enabled=available,
            status=_status_for_current_capability(available),
            reason=None if available else "tool_not_loaded",
        )
    elif key == "web_search":
        available = "web_search" in tool_names
        configured = bool(config.SEARXNG_URL)
        capability.update(
            available=available,
            configured=configured,
            enabled=available and configured,
            status=_status_for_current_capability(available, configured),
            reason=None if available and configured else (
                "tool_not_loaded" if not available else "not_configured"
            ),
        )
    elif key == "web_fetch":
        available = "web_fetch" in tool_names
        capability.update(
            available=available,
            configured=True,
            enabled=available,
            status=_status_for_current_capability(available),
            reason=None if available else "tool_not_loaded",
        )
    elif key == "moltbook_read_only":
        available = any(name.startswith("moltbook_") for name in tool_names)
        configured = bool(os.getenv("MOLTBOOK_TOKEN"))
        capability.update(
            available=available,
            configured=configured,
            enabled=available and configured,
            status=_status_for_current_capability(available, configured),
            reason=None if available and configured else (
                "tool_not_loaded" if not available else "not_configured"
            ),
        )
    elif key in {"backups", "memory_maintenance"}:
        capability.update(
            available=True,
            configured=True,
            enabled=True,
            status="available",
            reason=None,
        )

    if capability["mode"] not in ALLOWED_MODES:
        raise ValueError(f"Invalid capability mode: {capability['mode']}")
    if capability["status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid capability status: {capability['status']}")

    return capability


def build_capabilities_status(registry=None) -> dict:
    """Return read-only capability availability and configuration status."""
    tool_names = get_tool_names(registry)
    capabilities = {
        definition["key"]: _resolve_capability(definition, tool_names)
        for definition in _CAPABILITY_DEFINITIONS
    }
    return {
        "ok": True,
        "capabilities": capabilities,
    }
