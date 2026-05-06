from dataclasses import dataclass

from tir.ops.capabilities import (
    ALLOWED_MODES,
    ALLOWED_STATUSES,
    build_capabilities_status,
    get_tool_names,
    list_capability_definitions,
)


EXPECTED_CAPABILITY_KEYS = {
    "memory_search",
    "web_search",
    "web_fetch",
    "moltbook_read_only",
    "backups",
    "memory_maintenance",
    "file_uploads",
    "image_generation",
    "autonomous_research",
    "reflection_journal",
    "review_queue",
    "code_sandbox",
    "speech",
    "vision",
    "write_actions",
    "self_modification",
}

REQUIRED_FIELDS = {
    "key",
    "label",
    "implemented",
    "enabled",
    "available",
    "mode",
    "requires_approval",
    "source_of_truth",
    "real_time",
    "configured",
    "status",
    "reason",
    "notes",
}


@dataclass
class FakeRegistry:
    tools: tuple[str, ...] = ("memory_search", "web_search", "web_fetch")

    def list_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"{name} description",
                    "parameters": {},
                },
            }
            for name in self.tools
        ]


class BrokenRegistry:
    def list_tools(self):
        raise RuntimeError("registry unavailable")


def test_capability_definitions_include_all_expected_keys():
    definitions = list_capability_definitions()

    assert {definition["key"] for definition in definitions} == EXPECTED_CAPABILITY_KEYS


def test_capability_schema_fields_and_allowed_values(monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "secret-token")
    result = build_capabilities_status(
        FakeRegistry(tools=("memory_search", "web_search", "web_fetch", "moltbook_me"))
    )

    assert result["ok"] is True
    for key, capability in result["capabilities"].items():
        assert key in EXPECTED_CAPABILITY_KEYS
        assert REQUIRED_FIELDS <= set(capability)
        assert capability["key"] == key
        assert capability["mode"] in ALLOWED_MODES
        assert capability["status"] in ALLOWED_STATUSES
        assert isinstance(capability["label"], str)
        assert isinstance(capability["implemented"], bool)
        assert isinstance(capability["enabled"], bool)
        assert isinstance(capability["available"], bool)
        assert isinstance(capability["requires_approval"], bool)
        assert isinstance(capability["source_of_truth"], bool)
        assert isinstance(capability["real_time"], bool)
        assert isinstance(capability["configured"], bool)


def test_memory_search_reports_read_only_and_available_when_tool_exists():
    capability = build_capabilities_status(FakeRegistry())["capabilities"]["memory_search"]

    assert capability["implemented"] is True
    assert capability["enabled"] is True
    assert capability["available"] is True
    assert capability["mode"] == "read_only"
    assert capability["status"] == "available"


def test_web_tools_report_realtime_source_of_truth(monkeypatch):
    monkeypatch.setattr("tir.config.SEARXNG_URL", "http://127.0.0.1:8080")
    capabilities = build_capabilities_status(FakeRegistry())["capabilities"]

    for key in ("web_search", "web_fetch"):
        assert capabilities[key]["mode"] == "read_only"
        assert capabilities[key]["real_time"] is True
        assert capabilities[key]["source_of_truth"] is True
        assert capabilities[key]["implemented"] is True

    assert capabilities["web_search"]["configured"] is True
    assert capabilities["web_search"]["enabled"] is True
    assert capabilities["web_fetch"]["enabled"] is True


def test_moltbook_configured_is_boolean_only_and_does_not_expose_token(monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "do-not-leak")
    capability = build_capabilities_status(
        FakeRegistry(tools=("moltbook_me", "moltbook_posts_by_author"))
    )["capabilities"]["moltbook_read_only"]

    assert capability["configured"] is True
    assert capability["available"] is True
    assert capability["enabled"] is True
    assert capability["real_time"] is True
    assert capability["source_of_truth"] is True
    assert "do-not-leak" not in str(capability)


def test_file_uploads_reports_manual_available_capability():
    capability = build_capabilities_status(FakeRegistry())["capabilities"]["file_uploads"]

    assert capability["implemented"] is True
    assert capability["enabled"] is True
    assert capability["available"] is True
    assert capability["configured"] is True
    assert capability["mode"] == "manual"
    assert capability["status"] == "available"
    assert capability["requires_approval"] is False


def test_future_capabilities_report_disabled_not_implemented():
    capabilities = build_capabilities_status(FakeRegistry())["capabilities"]
    future_keys = {
        "image_generation",
        "autonomous_research",
        "reflection_journal",
        "review_queue",
        "code_sandbox",
        "speech",
        "vision",
    }

    for key in future_keys:
        assert capabilities[key]["implemented"] is False
        assert capabilities[key]["enabled"] is False
        assert capabilities[key]["available"] is False
        assert capabilities[key]["mode"] == "disabled"
        assert capabilities[key]["status"] == "not_implemented"


def test_write_actions_and_self_modification_require_approval():
    capabilities = build_capabilities_status(FakeRegistry())["capabilities"]

    assert capabilities["write_actions"]["requires_approval"] is True
    assert capabilities["write_actions"]["enabled"] is False
    assert capabilities["write_actions"]["status"] == "not_implemented"
    assert capabilities["self_modification"]["requires_approval"] is True
    assert capabilities["self_modification"]["enabled"] is False
    assert capabilities["self_modification"]["mode"] == "staged_only"
    assert capabilities["self_modification"]["status"] == "staged_only"


def test_missing_or_broken_registry_is_handled_gracefully():
    assert get_tool_names(None) == set()
    assert get_tool_names(BrokenRegistry()) == set()

    capabilities = build_capabilities_status(None)["capabilities"]
    assert capabilities["memory_search"]["available"] is False
    assert capabilities["memory_search"]["enabled"] is False
    assert capabilities["memory_search"]["reason"] == "tool_not_loaded"
