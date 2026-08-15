"""Tests for the tool-call fabrication gate.

Detector text is grounded in the real 2026-08-13 incidents (rainbow, solar
eclipse) pulled from the prod store, plus the real 2026-08-12 "Threshold"
concept-description negative case.
"""

from tir.engine.fabrication_gate import (
    MEDIA_ARTIFACT,
    detect_fabricated_tool_result,
    honest_fabrication_message,
)

# Verbatim shape of the confirmed fabrications (fake artifact provenance block).
_ECLIPSE_FABRICATION = (
    "[Artifact source: anam_generated_00013_.png, role: Generated artifact, "
    "origin: Generated, file: anam_generated_00013_.png]\n"
    "Artifact ID: 9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e\n"
    "File: anam_generated_00013_.png\n"
    "Stored path: generated/2026/08/12/9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e/"
    "anam_generated_00013_.png\n"
    "Source: generation\n"
    "MIME type: image/png\n"
    "Size: 325412 bytes\n"
    "SHA256: a1b2c3d4... (truncated)\n"
    "Media kind: generated_image\n"
    "Generation prompt (provenance metadata): A breathtaking total solar eclipse."
)

# Real negative: describing an image CONCEPT in prose, no fabricated identity block.
_THRESHOLD_CONCEPT = (
    'I want to visualize the concept of "The Threshold." It represents the exact '
    "moment we've been discussing. I am imagining a heavy, ancient stone doorway "
    "standing alone in a void, geometric patterns on one side and a swirling nebula "
    "on the other."
)


def test_detects_real_fabrication_with_zero_tool_calls():
    assert detect_fabricated_tool_result(_ECLIPSE_FABRICATION, 0) == MEDIA_ARTIFACT


def test_slim_era_artifact_shape_is_detected():
    # Post-_event_text-slim imitations may morph toward the compact shape.
    text = "Done! Artifact: A rainbow (id: 0a2a95f5-667d-4ec1-b9e3-6de9ad09ab8a)"
    assert detect_fabricated_tool_result(text, 0) == MEDIA_ARTIFACT


def test_concept_description_is_not_flagged():
    # Talking ABOUT an image (no fabricated provenance) must not trigger.
    assert detect_fabricated_tool_result(_THRESHOLD_CONCEPT, 0) is None


def test_real_generation_with_tool_call_is_not_flagged():
    # A genuine generation ran a tool; even artifact-shaped text must not trigger.
    assert detect_fabricated_tool_result(_ECLIPSE_FABRICATION, 1) is None
    assert detect_fabricated_tool_result("artifact_id=abc-123 done", 2) is None


def test_ordinary_prose_is_not_flagged():
    assert detect_fabricated_tool_result("Sure — here's a summary of our chat.", 0) is None
    assert detect_fabricated_tool_result("The eclipse will be visible next year.", 0) is None


def test_empty_text_is_not_flagged():
    assert detect_fabricated_tool_result("", 0) is None
    assert detect_fabricated_tool_result("   ", 0) is None


def test_individual_markers_each_trigger():
    for text in [
        "Here it is: [Artifact source: x.png]",
        "Artifact ID: 0a2a95f5abcd",
        "Stored path: generated/x",
        "saved at generated/2026/08/12/foo/bar.png",
        "SHA256: c79bbe55233cf9da",
        "artifact_id=0a2a95f5abcd",
    ]:
        assert detect_fabricated_tool_result(text, 0) == MEDIA_ARTIFACT, text


def test_honest_message_matches_approved_wording():
    assert honest_fabrication_message(MEDIA_ARTIFACT) == (
        "I wasn't able to generate that image — nothing was actually created. "
        "Want me to try again?"
    )
    # Unknown category falls back to a generic honest message (still no fabrication).
    assert "actually done" in honest_fabrication_message("some_future_category")
