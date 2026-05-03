"""Narrow URL-content intent detection for deterministic web_fetch prefetch."""

from __future__ import annotations

import re


_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}>\"'"

_STRONG_CONTENT_PHRASES = (
    "summarize this url",
    "summarize the url",
    "summarize this link",
    "summarize the link",
    "summarize this article",
    "summarize the article",
    "summarize this page",
    "summarize the page",
    "from this url",
    "from the url",
    "from this link",
    "from the link",
    "from this article",
    "from the article",
    "from this page",
    "from the page",
    "in this article",
    "in the article",
    "in this page",
    "in the page",
    "what does this url say",
    "what does the url say",
    "what does this link say",
    "what does the link say",
    "what does this page say",
    "what does the page say",
    "what does this article say",
    "what does the article say",
    "what does it mention",
    "does this page mention",
    "does the page mention",
    "does this article mention",
    "does the article mention",
    "is this summary accurate",
    "is the summary accurate",
    "is this claim accurate",
    "is the claim accurate",
    "verify this claim",
    "verify the claim",
)

_DETAIL_TERMS = (
    "who",
    "which",
    "what",
    "where",
    "when",
    "why",
    "how",
    "name",
    "named",
    "mention",
    "mentions",
    "mentioned",
    "detail",
    "details",
    "states",
    "involved",
    "accurate",
    "claim",
    "says",
    "say",
    "contents",
    "content",
)

_GENERIC_URL_MENTIONS = (
    "here is a url",
    "here's a url",
    "here is the url",
    "here's the url",
    "save this url",
    "save the url",
    "use this url as an example",
    "use the url as an example",
    "the api endpoint is",
    "api endpoint is",
    "may use later",
    "for later",
)


def extract_http_urls(text: str) -> list[str]:
    """Extract HTTP(S) URLs, stripping common sentence punctuation."""
    if not text:
        return []

    urls = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
        if url:
            urls.append(url)
    return urls


def has_url_content_intent(text: str) -> bool:
    """Return whether text asks about the contents of a provided URL/page."""
    if not text:
        return False

    lowered = " ".join(text.lower().split())

    if any(phrase in lowered for phrase in _STRONG_CONTENT_PHRASES):
        return True

    if "summarize" in lowered or "summary" in lowered:
        return True

    if re.search(r"\bwhat\s+does\b.*\bsay\b", lowered):
        return True

    if re.search(r"\bwhat\s+does\b.*\bmention\b", lowered):
        return True

    if any(phrase in lowered for phrase in _GENERIC_URL_MENTIONS):
        return False

    if "?" in lowered and any(term in lowered for term in _DETAIL_TERMS):
        return True

    if "can you tell me" in lowered and any(term in lowered for term in _DETAIL_TERMS):
        return True

    return False


def get_url_prefetch_candidate(text: str) -> str | None:
    """Return the first URL to prefetch when the message has URL-content intent."""
    urls = extract_http_urls(text)
    if not urls:
        return None

    if not has_url_content_intent(text):
        return None

    return urls[0]
