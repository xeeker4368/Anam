"""Retrieval policy for direct real-time/source-specific questions."""

import re

from tir.engine.url_prefetch import get_url_prefetch_candidate


NORMAL = "normal"
SKIP_MEMORY = "skip_memory"


_PROJECT_INTERNAL_TERMS = (
    "project anam",
    "tir/",
    "this repo",
    "our implementation",
    "what we built",
    "this codebase",
    "the codebase",
    "memory architecture",
)

_MOLTBOOK_ACTION_TERMS = (
    "check",
    "find",
    "list",
    "read",
    "show",
    "summarize",
    "search",
    "look up",
    "lookup",
    "see",
    "inspect",
)

_MOLTBOOK_OBJECT_TERMS = (
    "post",
    "posts",
    "feed",
    "profile",
    "comments",
    "comment",
    "submolt",
    "submolts",
)

_WEB_CURRENT_PATTERNS = (
    r"\bsearch\s+(?:the\s+)?web\b",
    r"\blook\s+up\b",
    r"\blookup\b",
    r"\bfind\s+(?:the\s+)?(?:latest|current|recent|news)\b",
    r"\b(?:latest|current|recent|today|now)\b",
    r"\bnews\b",
    r"\bon\s+the\s+web\b",
)


def classify_retrieval_policy(user_text: str) -> dict:
    """Classify whether normal memory retrieval should run for a turn."""
    text = user_text or ""
    lowered = " ".join(text.lower().split())

    if get_url_prefetch_candidate(text):
        return {"mode": SKIP_MEMORY, "reason": "direct_url_content"}

    if _is_direct_moltbook_state_query(lowered):
        return {"mode": SKIP_MEMORY, "reason": "direct_moltbook_state"}

    if _is_direct_web_current_query(lowered):
        return {"mode": SKIP_MEMORY, "reason": "direct_web_current"}

    if any(term in lowered for term in _PROJECT_INTERNAL_TERMS):
        return {"mode": NORMAL, "reason": "project_or_internal_context"}

    return {"mode": NORMAL, "reason": "normal"}


def _is_direct_moltbook_state_query(lowered: str) -> bool:
    """Detect direct Moltbook source-state questions."""
    if "moltbook" in lowered:
        has_action = any(term in lowered for term in _MOLTBOOK_ACTION_TERMS)
        has_object = any(term in lowered for term in _MOLTBOOK_OBJECT_TERMS)
        if has_action and has_object:
            return True
        if re.search(r"\bwhat\s+has\b.+\bposted\b", lowered):
            return True
        if re.search(r"\bposts?\s+by\b", lowered):
            return True
        return False

    # Allow natural follow-up phrasing if the user asks "what has X posted"
    # without naming Moltbook explicitly.
    if re.search(r"\bwhat\s+has\b.+\bposted\b", lowered):
        return True

    return False


def _is_direct_web_current_query(lowered: str) -> bool:
    """Detect direct requests for current outside-web information."""
    if any(term in lowered for term in _PROJECT_INTERNAL_TERMS):
        explicit_web = (
            "web" in lowered
            or "latest" in lowered
            or "current" in lowered
            or "today" in lowered
            or "now" in lowered
        )
        if not explicit_web:
            return False

    return any(re.search(pattern, lowered) for pattern in _WEB_CURRENT_PATTERNS)
