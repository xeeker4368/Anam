"""
Tír Retrieval Pipeline

Hybrid retrieval: vector search (ChromaDB) + lexical search (FTS5 BM25),
fused via Reciprocal Rank Fusion (RRF).

One function serves both automatic retrieval (context construction calls
it with the user's message) and explicit memory_search (the entity calls
it with her own query). Same ranking, same filtering. Different callers.

The entity never sees this module. She sees memories appear in her context
(automatic) or in her tool results (explicit). Retrieval is infrastructure.
"""

import logging
import re

from tir.config import (
    BM25_FLOOR_MIN_CORPUS_CHUNKS,
    BM25_SCORE_PER_TERM_THRESHOLD,
    DISTANCE_THRESHOLD,
    RRF_K,
    RETRIEVAL_RESULTS,
)
from tir.memory.chroma import query_similar
from tir.memory.db import get_connection, search_bm25

logger = logging.getLogger(__name__)


class RetrievalResult(list):
    """The retrieved chunks, plus whether the search itself failed outright.

    A plain `list` in every way callers already use — iteration, `len()`,
    truthiness, indexing, `in`, JSON serialization — so the four callers that
    only ever check emptiness need no change. Only the automatic path in
    `tir/api/routes.py` reads the extra attribute.

    `search_failed` exists because an empty result is otherwise ambiguous:
    `retrieve()` swallows backend exceptions per leg, so "both search backends
    are down" and "nothing matched" were indistinguishable, and the entity was
    told a search had run and found nothing when in fact no search completed.

    CAUTION: `search_failed` does NOT survive list operations that build a new
    list — slicing, `sorted()`, `list()`, and `+` all return a plain `list` and
    silently drop it. Read it directly off `retrieve()`'s return value before
    passing that value anywhere else.
    """

    def __init__(self, chunks=(), search_failed: bool = False):
        super().__init__(chunks)
        self.search_failed = search_failed


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

# Function words dropped before building the OR query. The terms are joined with
# OR, so any single surviving token can match a chunk on its own: leaving these
# in meant `"a of the"` matched 30 chunks and every ordinary question dragged the
# whole corpus into the BM25 leg. Content words are untouched, so a phrase that
# merely contains one of these still matches on the rest of it ("the roof repair"
# -> "roof" OR "repair"). Deliberately conservative — no stemming, no
# domain words, nothing that could carry recall on its own.
_STOPWORDS = frozenset(
    """
    a about all am an and any are as at be been being but by
    can could did do does doing done for from
    had has have he her him his how i if in into is it its
    just me my need not of on or our out
    said say she should so some tell than that the their them then
    there these they this those to up us
    was we were what whats when where which who why will with would
    you your
    """.split()
)


def _sanitize_fts5_query(query: str) -> str:
    """Convert a natural language query into a safe FTS5 OR query.

    Splits the query into tokens, drops function words, wraps each survivor in
    double quotes (making them literal term matches), and joins with OR.

    Handles FTS5 special characters that could break MATCH syntax.

    Args:
        query: Raw query text from user message or tool argument.

    Returns:
        FTS5-safe query string, or empty string if no usable tokens remain.
        An all-stopword query returns "" and the caller skips the BM25 leg
        entirely, leaving the vector leg to answer alone.

    Example:
        'What did we decide about save_and_chunk?'
        → '"decide" OR "save_and_chunk"'
    """
    # Split on whitespace
    tokens = query.split()

    if not tokens:
        return ""

    # Clean each token: remove FTS5 operators, drop stopwords, wrap in quotes
    safe_tokens = []
    for token in tokens:
        # Strip characters that are FTS5 operators
        cleaned = re.sub(r'["\(\)\*\-\^]', '', token)
        cleaned = cleaned.strip()
        if not cleaned:
            continue
        if cleaned.strip(".,!?;:'").lower().replace("'", "") in _STOPWORDS:
            continue
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
# Floor instrumentation
# ---------------------------------------------------------------------------
#
# Both floors are empirical values calibrated to one corpus at one size, so the
# thing worth watching is not whether they fire but by how much. Logging the
# margin on every query means threshold drift shows up in the debug trace as it
# happens, instead of needing a manual probe re-run to discover it. DEBUG level:
# never user-visible, never part of the prompt.


def _log_floor_margin(
    *,
    query: str,
    vector_raw: list[dict],
    vector_kept: int,
    distance_threshold: float,
) -> None:
    """Record how far the best vector candidate cleared or missed the floor."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    if not vector_raw:
        logger.debug(
            "retrieval_floor vector: no candidates (threshold=%.4f) query=%r",
            distance_threshold,
            query[:80],
        )
        return

    best = min(c["distance"] for c in vector_raw)
    # Positive margin = cleared the floor with room; negative = missed it.
    margin = distance_threshold - best
    logger.debug(
        "retrieval_floor vector: best=%.4f threshold=%.4f margin=%+.4f "
        "kept=%d/%d query=%r",
        best,
        distance_threshold,
        margin,
        vector_kept,
        len(vector_raw),
        query[:80],
    )


def _bm25_floor_applies() -> bool:
    """Return whether the index is large enough for bm25 rank to mean anything."""
    try:
        with get_connection() as conn:
            rows = int(
                conn.execute("SELECT COUNT(*) FROM main.chunks_fts").fetchone()[0]
            )
    except Exception as e:  # never let instrumentation break retrieval
        logger.debug("retrieval_floor bm25: corpus size unavailable (%s)", e)
        return False
    return rows >= BM25_FLOOR_MIN_CORPUS_CHUNKS


def _log_bm25_floor_margin(
    *,
    bm25_candidates: list[dict],
    bm25_kept: int,
    term_count: int,
    bm25_score_per_term_threshold: float,
) -> None:
    """Record how far the best lexical candidate cleared or missed the floor."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    scores = [
        c["bm25_score"] for c in bm25_candidates if c.get("bm25_score") is not None
    ]
    if not scores or not term_count:
        logger.debug(
            "retrieval_floor bm25: no scored candidates (threshold=%.2f/term)",
            bm25_score_per_term_threshold,
        )
        return

    best = min(scores)  # more negative = better
    best_per_term = best / term_count
    # Positive margin = cleared the floor with room; negative = missed it.
    margin = bm25_score_per_term_threshold - best_per_term
    logger.debug(
        "retrieval_floor bm25: best=%.3f terms=%d per_term=%.3f threshold=%.2f "
        "margin=%+.3f kept=%d/%d",
        best,
        term_count,
        best_per_term,
        bm25_score_per_term_threshold,
        margin,
        bm25_kept,
        len(bm25_candidates),
    )


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
    bm25_score_per_term_threshold: float = BM25_SCORE_PER_TERM_THRESHOLD,
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
            are dropped before fusion (default 0.40). BM25-only matches are
            NOT subject to this floor — see the note in the body.
        bm25_score_per_term_threshold: FTS5 bm25 rank PER MATCHED TERM above
            which (i.e. less negative than) lexical candidates are dropped
            before fusion (default -2.5). Not applied when the index holds
            fewer than BM25_FLOOR_MIN_CORPUS_CHUNKS chunks.
        trust_weights: Deprecated compatibility argument. source_trust is
            metadata-only and no longer applies a ranking multiplier.
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
        # No legs attempted, so this is not a search failure — it is a caller
        # handing us nothing to search for.
        return RetrievalResult([], search_failed=False)

    # Leg bookkeeping for `search_failed`. Tracked as attempted/succeeded
    # rather than failed/failed: the BM25 leg is SKIPPED entirely for an
    # all-stopword query, and a skipped leg must not count as a success. If the
    # vector leg is then the only leg attempted and it raises, nothing was
    # searched at all — which is a total failure even though only one leg
    # "failed". ("what is it", "what about it" and similar follow-ups reach
    # here with an empty FTS query, so this is production-reachable.)
    vector_attempted = True  # the vector leg is always attempted
    vector_succeeded = False
    bm25_succeeded = False

    # --- Vector search (ChromaDB) ---
    try:
        vector_raw = query_similar(
            query_text=query,
            n_results=top_k_per_signal,
        )
        vector_succeeded = True
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to BM25 only: {e}")
        vector_raw = []

    # Filter by distance threshold. This is the relevance floor, and it is
    # applied PRE-fusion and to the vector leg ONLY: a chunk dropped here can
    # still reach the result through BM25, arriving with vector_distance/
    # vector_rank of None. That exemption is deliberate — an exact lexical or
    # phrase match is real evidence independent of semantic distance, and it
    # measurably carries queries the vector leg misses (an exact-phrase recall
    # test retained 6 chunks, 5 of them lexical-only).
    vector_filtered = [
        c for c in vector_raw
        if c["distance"] <= distance_threshold
    ]
    _log_floor_margin(
        query=query,
        vector_raw=vector_raw,
        vector_kept=len(vector_filtered),
        distance_threshold=distance_threshold,
    )

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
    bm25_attempted = bool(fts5_query)
    if bm25_attempted:
        try:
            bm25_raw = search_bm25(
                query=fts5_query,
                n_results=top_k_per_signal,
                exclude_conversation_id=active_conversation_id,
            )
            bm25_succeeded = True
        except Exception as e:
            logger.warning(f"BM25 search failed, falling back to vector only: {e}")
            bm25_raw = []
    else:
        # Query was entirely function words; the vector leg answers alone.
        # NOT attempted — so it can neither succeed nor fail, and must not be
        # counted as either when deciding `search_failed` below.
        bm25_raw = []

    # Lexical relevance floor. FTS5 bm25 rank is negative, more negative =
    # better, so a candidate is weak when its score is ABOVE the threshold.
    # Needed because the OR-joined query still matches broadly on ordinary
    # content words even after stopword removal.
    # Fail OPEN on a missing score: absence of a rank is not evidence of a weak
    # match, and dropping a lexical hit for want of a metadata field would
    # quietly defeat the BM25-only exemption above. Only a score we actually
    # have, and which is genuinely weak, removes a candidate.
    bm25_candidates = bm25_raw
    term_count = fts5_query.count(" OR ") + 1 if fts5_query else 0
    if term_count and _bm25_floor_applies():
        bm25_raw = [
            c for c in bm25_candidates
            if c.get("bm25_score") is None
            or (c["bm25_score"] / term_count) <= bm25_score_per_term_threshold
        ]
    _log_bm25_floor_margin(
        bm25_candidates=bm25_candidates,
        bm25_kept=len(bm25_raw),
        term_count=term_count,
        bm25_score_per_term_threshold=bm25_score_per_term_threshold,
    )

    # A search "failed" when every leg that was actually attempted raised, and
    # none succeeded. Not `vector_failed and bm25_failed` — that reports healthy
    # when the only attempted leg is the one that died.
    any_attempted = vector_attempted or bm25_attempted
    any_succeeded = vector_succeeded or bm25_succeeded
    search_failed = any_attempted and not any_succeeded

    # --- Handle edge cases ---
    if not vector_filtered and not bm25_raw:
        return RetrievalResult([], search_failed=search_failed)

    # --- RRF fusion ---
    fused = _fuse_rrf(vector_filtered, bm25_raw, k=rrf_k)

    # --- Baseline final score ---
    # source_trust stays in metadata/debug output but does not invisibly
    # down-rank source-derived continuity artifacts.
    for chunk in fused:
        chunk["adjusted_score"] = chunk["rrf_score"]

    if artifact_intent:
        _apply_artifact_boosts(fused, query)

    # --- Re-sort by adjusted score and trim ---
    fused.sort(key=lambda x: x["adjusted_score"], reverse=True)
    # Wrapped explicitly rather than relying on the default: `fused[:max_results]`
    # is a slice, which returns a plain list and would drop `search_failed`
    # entirely. Every return path in this function constructs the type on purpose.
    return RetrievalResult(fused[:max_results], search_failed=search_failed)
