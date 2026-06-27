"""Tests for generated-image artifact-card selection metadata.

The card is built only from a real, successful artifact record. Anything else
must yield None so the frontend renders no card (fail-safe-empty).
"""

from tir.engine.tool_trace_context import (
    GENERATED_IMAGE_SELECTION_KIND,
    build_generated_image_selection,
    selection_metadata_for_tool_result,
)


def _success_result():
    return {
        "ok": True,
        "generation_error": False,
        "artifact_created": True,
        "artifact_id": "artifact-123",
        "artifact_title": "A red bird",
        "media_kind": "generated_image",
        "preview_url": "/api/artifacts/artifact-123/file",
        "prompt": "a red bird on a branch",
        "seed": 42,
    }


def test_successful_result_builds_card_selection():
    selection = build_generated_image_selection(_success_result())
    assert selection == {
        "kind": GENERATED_IMAGE_SELECTION_KIND,
        "tool_name": "image_generate",
        "artifact_id": "artifact-123",
        "preview_url": "/api/artifacts/artifact-123/file",
        "title": "A red bird",
        "media_kind": "generated_image",
    }


def test_dispatcher_routes_image_generate_to_card_builder():
    selection = selection_metadata_for_tool_result("image_generate", _success_result())
    assert selection is not None
    assert selection["kind"] == GENERATED_IMAGE_SELECTION_KIND
    assert selection["artifact_id"] == "artifact-123"


def test_failed_generation_yields_no_card():
    failed = {
        "ok": False,
        "generation_error": True,
        "error_type": "backend_unavailable",
        "artifact_created": False,
    }
    assert build_generated_image_selection(failed) is None
    assert selection_metadata_for_tool_result("image_generate", failed) is None


def test_no_artifact_created_yields_no_card():
    result = {"ok": True, "artifact_created": False, "artifact_id": "x"}
    assert build_generated_image_selection(result) is None


def test_missing_artifact_id_yields_no_card():
    result = {"ok": True, "artifact_created": True, "preview_url": "/x"}
    assert build_generated_image_selection(result) is None


def test_non_dict_result_yields_no_card():
    assert build_generated_image_selection(None) is None
    assert build_generated_image_selection("nope") is None


def test_missing_preview_url_still_builds_selection_with_empty_string():
    # The card builder is tolerant; the frontend decides not to render an image
    # when preview_url is empty. Selection itself is still valid (has an id).
    result = {"ok": True, "artifact_created": True, "artifact_id": "a1"}
    selection = build_generated_image_selection(result)
    assert selection is not None
    assert selection["preview_url"] == ""


def test_unrelated_tool_yields_no_card():
    assert selection_metadata_for_tool_result("echo", _success_result()) is None
