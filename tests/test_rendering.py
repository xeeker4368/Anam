"""Tests for model-visible tool-result shaping (Commit 2 of the confabulation fix)."""

from tir.tools.rendering import (
    summarize_generated_image_result,
    summarize_tool_result_for_model,
)


def _success_result():
    return {
        "ok": True,
        "artifact_created": True,
        "artifact_id": "abc-123",
        "artifact_title": "A red bird",
        "media_kind": "generated_image",
        "artifact_path": "generated/2026/08/12/abc-123/anam_generated.png",
        "preview_url": "/api/artifacts/abc-123/file",
        "prompt": "a red bird on a branch",
        "seed": 42,
        "width": 512,
        "height": 512,
    }


def test_summary_is_minimal_and_omits_forgeable_fields():
    summary = summarize_generated_image_result(_success_result())
    assert summary == "image generated; artifact_id=abc-123; shown to user in the chat UI"
    # None of the imitable/forgeable detail leaks into the model-visible text.
    for leaked in ("preview_url", "/api/artifacts", "seed", "42", "512", "generated/2026",
                   "a red bird on a branch", "artifact_path"):
        assert leaked not in summary


def test_summary_none_for_failed_or_incomplete_results():
    assert summarize_generated_image_result({"ok": False, "artifact_created": False}) is None
    assert summarize_generated_image_result({"ok": True, "artifact_created": False, "artifact_id": "x"}) is None
    assert summarize_generated_image_result({"ok": True, "artifact_created": True}) is None  # no id
    assert summarize_generated_image_result(None) is None


def test_dispatch_only_reduces_media_tools():
    # image_generate gets the minimal summary...
    assert summarize_tool_result_for_model("image_generate", _success_result()) == (
        "image generated; artifact_id=abc-123; shown to user in the chat UI"
    )
    # ...every other tool returns None so the caller keeps the full rendered text.
    assert summarize_tool_result_for_model("memory_search", {"ok": True, "results": []}) is None
    assert summarize_tool_result_for_model("web_fetch", {"ok": True, "text": "x"}) is None
