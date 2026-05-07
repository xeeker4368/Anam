"""
Tír Retrieval Pipeline

Hybrid retrieval: vector search (ChromaDB) + lexical search (FTS5 BM25),
fused via Reciprocal Rank Fusion (RRF), weighted by source trust.

One function serves both automatic retrieval (context construction calls
it with the user's message) and explicit memory_search (the entity calls
it with her own query). Same ranking, same filtering. Different callers.

The entity never sees this module. She sees memories appear in her context
(automatic) or in her tool results (explicit). Retrieval is infrastructure.
"""

import logging
import re

from tir.config import (
    DISTANCE_THRESHOLD,
    TRUST_WEIGHTS,
    RRF_K,
    RETRIEVAL_RESULTS,
)
from tir.memory.chroma import query_similar
from tir.memory.db import search_bm25

logger = logging.getLogger(__name__)


_ARTIFACT_SOURCE_TYPE = "artifact_document"
_ARTIFACT_BASE_BOOST = 1.25
_ARTIFACT_STRONG_BOOST = 2.25
_FILENAME_TOKEN_RE = re.compile(r"\b[\w.\-]+\.[A-Za-z0-9]{1,12}\b")
_COMMON_TITLES = {
    "file",
    "document",
    "note",
    "notes",
    "source",
    "artifact",
    "upload",
    "uploaded",
    "draft",
    "log",
}


# ---------------------------------------------------------------------------
# FTS5 query sanitization
# ---------------------------------------------------------------------------

def _sanitize_fts5_query(query: str) -> str:
    """Convert a natural language query into a safe FTS5 OR query.

    Splits the query into tokens, wraps each in double quotes
    (making them literal term matches), and joins with OR.

    Handles FTS5 special characters that could break MATCH syntax.

    Args:
        query: Raw query text from user message or tool argument.

    Returns:
        FTS5-safe query string, or empty string if no usable tokens.

    Example:
        'What did we decide about save_and_chunk?'
        → '"What" OR "did" OR "we" OR "decide" OR "about" OR "save_and_chunk"'
    """
    # Split on whitespace
    tokens = query.split()

    if not tokens:
        return ""

    # Clean each token: remove FTS5 operators and wrap in quotes
    safe_tokens = []
    for token in tokens:
        # Strip characters that are FTS5 operators
        cleaned = re.sub(r'["\(\)\*\-\^]', '', token)
        cleaned = cleaned.strip()
        if cleaned:
            safe_tokens.append(f'"{cleaned}"')

    if not safe_tokens:
        return ""

    return " OR ".join(safe_tokens)


def _normalize_match_text(value: str | None) -> str:
    """Normalize text for artifact metadata/header matching."""
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _filename_tokens(query: str) -> set[str]:
    """Extract filename-like tokens from a query."""
    return {
        token.lower().strip(".,!?;:()[]{}\"'")
        for token in _FILENAME_TOKEN_RE.findall(query or "")
    }


def _meaningful_title(title: str) -> bool:
    """Return whether a title is specific enough for a strong boost."""
    normalized = _normalize_match_text(title)
    if not normalized or normalized in _COMMON_TITLES:
        return False
    words = [word for word in re.split(r"\W+", normalized) if word]
    return len(words) >= 2 or len(normalized) >= 12


def _artifact_header_value(text: str, label: str) -> str | None:
    """Extract a simple value from artifact chunk headers."""
    prefix = f"{label}:"
    for line in (text or "").splitlines()[:12]:
        if line.lower().startswith(prefix.lower()):
            return line[len(prefix):].strip()
    return None


def _artifact_match(chunk: dict, query: str) -> tuple[bool, str | None]:
    """Detect exact/strong artifact matches for opt-in artifact ranking."""
    metadata = chunk.get("metadata") or {}
    text = chunk.get("text") or ""
    normalized_query = _normalize_match_text(query)
    filename_tokens = _filename_tokens(query)

    artifact_id = (
        metadata.get("artifact_id")
        or _artifact_header_value(text, "Artifact ID")
    )
    if artifact_id:
        normalized_id = _normalize_match_text(artifact_id)
        if normalized_id and normalized_id in normalized_query:
            return True, "artifact_id"

    filename = (
        metadata.get("filename")
        or _artifact_header_value(text, "File")
    )
    if filename:
        normalized_filename = _normalize_match_text(filename)
        if normalized_filename and normalized_filename in normalized_query:
            return True, "filename"
        if normalized_filename in filename_tokens:
            return True, "filename"

    title = (
        metadata.get("title")
        or _artifact_header_value(text, "Artifact source")
    )
    if title and _meaningful_title(title):
        normalized_title = _normalize_match_text(title)
        if normalized_title and normalized_title in normalized_query:
            return True, "title"

    return False, None


def _apply_artifact_boosts(chunks: list[dict], query: str) -> None:
    """Apply opt-in artifact ranking boosts in place."""
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        source_type = metadata.get("source_type") or chunk.get("source_type")
        boost = 1.0
        exact_match = False
        match_field = None

        if source_type == _ARTIFACT_SOURCE_TYPE:
            boost = _ARTIFACT_BASE_BOOST
            exact_match, match_field = _artifact_match(chunk, query)
            if exact_match:
                boost = _ARTIFACT_STRONG_BOOST

        chunk["artifact_boost"] = boost
        chunk["artifact_exact_match"] = exact_match
        chunk["artifact_match_field"] = match_field
        chunk["adjusted_score"] *= boost


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

def _fuse_rrf(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = RRF_K,
) -> list[dict]:
    """Fuse two ranked lists using Reciprocal Rank Fusion.

    For each chunk appearing in either list:
        rrf_score = sum over lists L of (1 / (k + rank_in_L))

    where rank is 1-indexed. A chunk in both lists gets both terms.

    Args:
        vector_results: Ranked list from ChromaDB (most similar first).
            Each dict has at minimum: chunk_id, text, metadata, distance.
        bm25_results: Ranked list from FTS5 (most relevant first).
            Each dict has at minimum: chunk_id, text.
        k: RRF fusion constant (default 60).

    Returns:
        Fused list of dicts with:
            chunk_id, text, metadata, rrf_score,
            vector_distance (or None), vector_rank (or None),
            bm25_rank (or None)
        Sorted by rrf_score descending.
    """
    # Build a lookup of all chunks by ID
    chunks = {}

    # Process vector results (1-indexed rank)
    for rank, item in enumerate(vector_results, start=1):
        cid = item["chunk_id"]
        chunks[cid] = {
            "chunk_id": cid,
            "text": item["text"],
            "metadata": item.get("metadata", {}),
            "vector_distance": item.get("distance"),
            "vector_rank": rank,
            "bm25_rank": None,
            "rrf_score": 1.0 / (k + rank),
        }

    # Process BM25 results (1-indexed rank)
    for rank, item in enumerate(bm25_results, start=1):
        cid = item["chunk_id"]
        if cid in chunks:
            # Chunk appears in both lists — add BM25 contribution
            chunks[cid]["bm25_rank"] = rank
            chunks[cid]["rrf_score"] += 1.0 / (k + rank)
        else:
            # Chunk only in BM25
            chunks[cid] = {
                "chunk_id": cid,
                "text": item["text"],
                "metadata": {
                    "source_type": item.get("source_type", "unknown"),
                    "source_trust": item.get("source_trust", "firsthand"),
                    "conversation_id": item.get("conversation_id"),
                    "user_id": item.get("user_id"),
                    "created_at": item.get("created_at"),
                },
                "vector_distance": None,
                "vector_rank": None,
                "bm25_rank": rank,
                "rrf_score": 1.0 / (k + rank),
            }

    # Sort by RRF score descending
    fused = sorted(chunks.values(), key=lambda x: x["rrf_score"], reverse=True)
    return fused


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    active_conversation_id: str | None = None,
    max_results: int = RETRIEVAL_RESULTS,
    distance_threshold: float = DISTANCE_THRESHOLD,
    trust_weights: dict | None = None,
    rrf_k: int = RRF_K,
    top_k_per_signal: int = 30,
    artifact_intent: bool = False,
) -> list[dict]:
    """
    Hybrid retrieve from ChromaDB + FTS5, fused via RRF.

    This is the single function that both context construction and
    the memory_search tool call. Same ranking, same filtering.

    Args:
        query: Natural language query string.
        active_conversation_id: If provided, chunks from this conversation
            are excluded to avoid duplicating what's already in context.
        max_results: Maximum final ranked results to return (default 20).
        distance_threshold: Cosine distance above which vector candidates
            are dropped before fusion (default 0.8).
        trust_weights: Mapping of source_trust → score multiplier.
            Defaults to config values.
        rrf_k: RRF fusion constant (default 60).
        top_k_per_signal: Candidates per signal before fusion (default 30).
        artifact_intent: If True, modestly prefer artifact_document chunks
            and strongly prefer exact filename/title/artifact ID matches.
            Defaults to False to preserve memory_search and normal retrieval.

    Returns:
        Ranked list (most relevant first) of dicts:
            {
                "chunk_id": str,
                "text": str,
                "metadata": dict,
                "vector_distance": float | None,
                "vector_rank": int | None,
                "bm25_rank": int | None,
                "rrf_score": float,
                "adjusted_score": float,
            }
        Empty list if nothing matches (valid outcome).
    """
    if not query or not query.strip():
        return []

    if trust_weights is None:
        trust_weights = TRUST_WEIGHTS

    # --- Vector search (ChromaDB) ---
    try:
        vector_raw = query_similar(
            query_text=query,
            n_results=top_k_per_signal,
        )
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to BM25 only: {e}")
        vector_raw = []

    # Filter by distance threshold
    vector_filtered = [
        c for c in vector_raw
        if c["distance"] <= distance_threshold
    ]

    # Exclude active conversation (post-filter in Python because
    # ChromaDB's $ne doesn't handle missing conversation_id on
    # document chunks correctly)
    if active_conversation_id:
        vector_filtered = [
            c for c in vector_filtered
            if c["metadata"].get("conversation_id") != active_conversation_id
        ]

    # --- BM25 search (FTS5) ---
    fts5_query = _sanitize_fts5_query(query)
    if fts5_query:
        try:
            bm25_raw = search_bm25(
                query=fts5_query,
                n_results=top_k_per_signal,
                exclude_conversation_id=active_conversation_id,
            )
        except Exception as e:
            logger.warning(f"BM25 search failed, falling back to vector only: {e}")
            bm25_raw = []
    else:
        bm25_raw = []

    # --- Handle edge cases ---
    if not vector_filtered and not bm25_raw:
        return []

    # --- RRF fusion ---
    fused = _fuse_rrf(vector_filtered, bm25_raw, k=rrf_k)

    # --- Trust weighting ---
    for chunk in fused:
        source_trust = chunk["metadata"].get("source_trust", "firsthand")
        weight = trust_weights.get(source_trust, 1.0)
        if weight == 1.0 and source_trust not in trust_weights:
            logger.warning(f"Unknown source_trust '{source_trust}', using weight 1.0")
        chunk["adjusted_score"] = chunk["rrf_score"] * weight

    if artifact_intent:
        _apply_artifact_boosts(fused, query)

    # --- Re-sort by adjusted score and trim ---
    fused.sort(key=lambda x: x["adjusted_score"], reverse=True)
    return fused[:max_results]
