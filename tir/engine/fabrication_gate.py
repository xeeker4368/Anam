"""Tool-call fabrication gate.

Catches fabricated *success*: the model producing tool-result-shaped prose (a fake
artifact block, etc.) without ever calling the tool — confirmed live (rainbow,
solar eclipse; tool_call_count == 0). This is the success-side mirror of the
tool-FAILURE honesty fix (frame_failed_tool_message): both catch a mismatch between
what really happened and what the model claims happened. Here there is no tool
result to inspect, so detection is post-hoc on the finished turn text vs. the
ground-truth tool_call_count.

Design (per PLAN-2026-08-13-tool-call-fabrication-gate.md):
- Per-tool-category detectors (media/artifact first — the proven case), each a set
  of HIGH-PRECISION markers checked ONLY when tool_call_count == 0. Adding a
  category is a data addition to FABRICATION_DETECTORS, not new control flow.
- Markers are grounded in real incident text and essentially never appear in honest
  prose (SHA256 lines, stored generated/ paths, an "Artifact ID:" UUID), so combined
  with zero tool calls this is near-zero false positive.
- On detection the caller fails honestly and does NOT persist the fabrication.
"""

from __future__ import annotations

import re

MEDIA_ARTIFACT = "media_artifact"

# High-precision markers for a fabricated media/artifact result. Any one match (in
# assistant text, when tool_call_count == 0) is treated as fabrication. These key on
# fabricated PROVENANCE/IDENTITY — not on merely discussing or describing an image,
# so a concept description ("I am imagining a stone doorway...") is NOT flagged.
_MEDIA_ARTIFACT_MARKERS: tuple[re.Pattern, ...] = (
    re.compile(r"\[Artifact source:", re.IGNORECASE),
    re.compile(r"^\s*Artifact ID:\s*[0-9a-f]{6,}", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Stored path:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\bgenerated/\d{4}/\d{2}/\d{2}/", re.IGNORECASE),
    re.compile(r"^\s*SHA256:\s*[0-9a-f]{6,}", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\bartifact_id\s*[=:]\s*[0-9a-f]{6,}", re.IGNORECASE),
    # Slim-era shape (post-_event_text slim), imitations may morph toward this.
    re.compile(r"\bArtifact:\s+.+\(id:\s*[^)]+\)", re.IGNORECASE),
)

# category -> markers. Extend here (evidence-first) for future tool categories.
FABRICATION_DETECTORS: dict[str, tuple[re.Pattern, ...]] = {
    MEDIA_ARTIFACT: _MEDIA_ARTIFACT_MARKERS,
}

_HONEST_MESSAGES = {
    MEDIA_ARTIFACT: (
        "I wasn't able to generate that image — nothing was actually created. "
        "Want me to try again?"
    ),
}


def detect_fabricated_tool_result(text: str, tool_call_count: int) -> str | None:
    """Return the matched fabrication category, or None.

    A category matches only when NO tool ran this turn (``tool_call_count == 0``)
    and the finished assistant ``text`` carries that category's high-precision
    markers. Returns None immediately when a tool ran or the text is empty.
    """
    if tool_call_count != 0:
        return None
    if not text or not text.strip():
        return None
    for category, markers in FABRICATION_DETECTORS.items():
        if any(marker.search(text) for marker in markers):
            return category
    return None


def honest_fabrication_message(category: str) -> str:
    """The user-facing honest correction for a detected fabrication category."""
    return _HONEST_MESSAGES.get(
        category,
        "I wasn't able to complete that action — nothing was actually done. "
        "Want me to try again?",
    )
