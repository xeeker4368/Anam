# Project Tír — Retrieval Design

*Design doc v1, April 2026. How chunks surface from the retrieval layer into the entity's context (automatic retrieval) and into her tool traces (explicit `memory_search`). Hybrid retrieval — vector search over ChromaDB + BM25 over SQLite FTS5, fused via RRF, weighted by source trust, filtered for quality and active-conversation duplication.*

*Anchors to what worked in Aion: the hybrid two-signal pattern. Diverges where Tír's needs differ.*

---

## Purpose

Chunks in storage are inert until something finds them. Retrieval is the mechanism that answers "given this query, what experiences should the entity see?" Per Principle 7 (retrieval determines intelligence), this is the most important work in the system after the conversation archive itself — a strong chat model on weak retrieval looks weak.

This document decides:

- The hybrid retrieval architecture (vector + BM25 + rank fusion) and why both signals earn their keep.
- How source trust shapes ranking.
- How weak matches get filtered out.
- How the active conversation is excluded from its own retrieval.
- What automatic retrieval does vs. what explicit `memory_search` does.
- The retrieval function's interface, return shape, and tuning knobs.

Non-goals:

- Chunking (done, v1.1).
- Context construction framing of retrieved chunks (done, v1.1).
- The `memory_search` tool's SKILL.md (deferred — one of the day-one tools from Tool Framework v1, gets its own pass).
- FTS5 write-path integration *implementation*. The retrieval design specifies the shape; the integration spec (separate Dev_Doc, after chunking spec lands) handles the code.

---

## Summary of decisions

1. **Hybrid retrieval day-one.** Vector search (ChromaDB, cosine distance) + BM25 (SQLite FTS5) fused via Reciprocal Rank Fusion. Matches Aion's validated pattern; Requirement 16's architectural requirement reads as strict in light of Aion's proven results.
2. **One unified search space per signal.** No per-user partitioning, no source-type sharding. Both signals search across all chunks. Matches Requirement 15.
3. **FTS5 lives in `working.db`** as a virtual table alongside the other operational tables. Derived data — rebuildable from ChromaDB documents if wiped.
4. **RRF with k=60** for fusion. No score normalization required; ranks are commensurable even though raw scores aren't.
5. **Distance threshold on the vector leg before fusion.** Default 0.8 cosine distance. BM25 has its own implicit filter (MATCH excludes non-matching chunks).
6. **Trust is a multiplicative weight on the fused score.** Firsthand 1.0, secondhand 0.85, thirdhand 0.7 (initial; tunable).
7. **Active-conversation chunks are excluded post-retrieval via Python filter.** Avoids edge cases with ChromaDB's `$ne` semantics when `conversation_id` is absent (document chunks).
8. **Automatic retrieval uses the user's most recent message as the query** (Context Construction v1.1 default). Explicit `memory_search` uses the entity's tool-call argument.
9. **Retrieval returns up to 20 ranked candidates.** Context construction applies its floor/ceiling/budget from CC v1.1 (3–15 chunks, default 8). Retrieval does not make budget decisions.
10. **Ordering is by adjusted score descending, strict.** No chronological tiebreaking day-one; leave that to the caller if needed.

---

## Why hybrid day-one

Requirement 16 says "hybrid retrieval supporting both semantic and lexical methods." Lyle's direction — the previous project's hybrid retrieval worked, and the memory requirements were written against that experience — tightens the reading: day-one *implements* hybrid, not just "accommodates" it.

The two signals catch different things:

- **Vector similarity** captures conceptual/semantic matches. "What does she think about emergence?" surfaces discussions of "emergent behavior," "systems developing character," "unpredictable trajectories" even without the word "emergence."
- **BM25** catches exact-token matches that vectors can dilute: proper nouns (people, places, project names), code terms, version numbers, acronyms. "What did we decide about `save_and_chunk`?" should surface the specific chunks where that exact name appeared. Vector search on that query can wander into "saving conversations" or "chunking strategies" — correct topic, wrong specifics.

Leaning on one and deferring the other leaves a known gap. Aion showed the gap matters in practice. Tír starts whole.

### What this costs

SQLite FTS5 is part of the standard SQLite build on macOS. The added surface:

- A virtual table in `working.db` (schema v1.3 — see separate update).
- A write-path hook: every chunk written to ChromaDB also writes to FTS5. Happens at chunk-write time, same code path as the ChromaDB upsert.
- A query function alongside the vector query.
- RRF fusion — a tiny pure function.

Roughly 100 lines of code across the retrieval module and the chunk-write path. Validated by Aion's run. Worth it on day one.

### What stays deferred

- **User-voice FTS5 index** (per Memory Requirements open question d). A separate narrow index on user messages only, over and above the general-purpose BM25 index. Aion used this; the Memory Requirements doc's read is that general-purpose BM25 subsumes most of what it caught. Not day-one. Add if specific gaps appear.
- **Cross-encoder reranking.** A second-stage smaller model rescoring top-K from fusion. Quality improvement if the hybrid pair still isn't enough. Not day-one.
- **Query expansion / reformulation.** Useful for short/ambiguous queries. Not day-one.

---

## Architecture

### Storage recap

- **Vector side:** ChromaDB collection `tir_memory`, cosine distance, 768-dim nomic-embed-text embeddings. Chunk metadata per Schema v1.2 (v1.4 with FTS5 addition).
- **Lexical side:** SQLite FTS5 virtual table `chunks_fts` in `working.db`. Columns: `chunk_id` (unindexed, for joining), `text` (indexed for MATCH), plus unindexed metadata columns (`source_trust`, `user_id`, `conversation_id`, `source_type`, `created_at`) so BM25 queries can apply metadata-based filters in SQL.
- **Same chunk ID in both stores.** `{conversation_id}_chunk_{chunk_index}` for conversation chunks, `{document_id}_chunk_{chunk_index}` for document chunks — per Schema v1.2. The chunk_id is the bridge between the two signals.

### The retrieval pipeline

Seven stages:

1. **Embed the query** via Ollama nomic-embed-text. 768 floats, cosine space. Same model as the chunks — mismatched models put queries and chunks in different spaces.
2. **Vector search.** ChromaDB top-30 with cosine distance returned.
3. **Vector-side filters.**
   - Distance threshold: drop candidates with distance > `DISTANCE_THRESHOLD` (default 0.8).
   - Active-conversation filter: drop candidates where `metadata.conversation_id == active_conversation_id`.
4. **BM25 search.** FTS5 MATCH query, top-30, ranked by FTS5's `bm25()` function (native SQLite). Excludes active-conversation chunks via SQL `WHERE (conversation_id IS NULL OR conversation_id != ?)`.
5. **RRF fusion.** For each chunk appearing in either list:
   ```
   rrf_score(chunk) = Σ over lists L ∈ {vector, bm25} of (1 / (k + rank_in_L(chunk)))
   ```
   where `k = 60` (standard default in the literature), and `rank_in_L` is 1-indexed rank in list L. A chunk appearing in both lists gets both terms summed. A chunk in only one gets that one term.
6. **Trust weighting.** `adjusted_score = rrf_score * trust_weight[source_trust]`. Trust weights default to `{firsthand: 1.0, secondhand: 0.85, thirdhand: 0.7}`.
7. **Rank descending by adjusted_score; return top `max_results` (default 20).**

### Why RRF

Reciprocal Rank Fusion is the standard modern choice for combining heterogeneous ranked lists:

- **No score normalization needed.** Vector cosine distances (0.0–2.0, lower better) and BM25 scores (unbounded negative in SQLite's implementation, more negative better) aren't commensurable as raw numbers. RRF uses ranks, which are commensurable by construction.
- **Well-behaved tail.** Adding more lists or extending a list farther doesn't blow up scores; each additional rank contribution is smaller than the last.
- **Simple to tune.** `k` is the only knob. Higher k makes the tails matter more; lower k biases harder toward top-1 in each list.

`k=60` is the long-standing default from the original RRF paper. Tunable; no reason to start anywhere else.

### Why trust weighting after fusion, not before

Trust is a global property of the chunk (its source_trust). It should bias the final ranking, not distort either signal's internal structure. Applying trust multiplicatively to the fused RRF score keeps the fusion logic pure and makes trust easy to turn off for debugging (set all weights to 1.0, compare rankings).

### Why distance threshold only on the vector leg

BM25's MATCH is itself a filter — chunks that don't contain any query tokens are never returned. The only "weak" BM25 results are chunks that matched one minor token but aren't topical. Those get low BM25 scores naturally and lose on fusion to strongly-ranked vector hits.

Vector search has no such natural floor: every chunk in the collection has some cosine distance to the query, and the top-30 can include chunks at distance 1.2 (essentially unrelated) if the corpus is small or off-topic. The threshold is specifically to kill these. Applied before fusion because a thin vector match shouldn't occupy a fusion slot.

### Why active-conversation exclusion is post-retrieval in Python (for ChromaDB) but SQL-level (for FTS5)

ChromaDB's `$ne` operator in `where` clauses doesn't match records where the field is absent. Document chunks have no `conversation_id` in metadata, so a `{"conversation_id": {"$ne": active_id}}` filter would exclude document chunks from every query — wrong. Post-filtering in Python after the top-30 fetch handles this correctly with one line: `[c for c in results if c["metadata"].get("conversation_id") != active_id]`.

FTS5 is SQL; NULL comparison is explicit. `WHERE (conversation_id IS NULL OR conversation_id != ?)` handles both non-conversation chunks and other conversations cleanly.

Different mechanisms, same semantics. Documented so the asymmetry isn't a surprise.

---

## Two retrieval modes, one function

**Automatic retrieval** is environmental plumbing. Context Construction v1.1 calls it at turn start with the user's most recent message as the query, and packs the top N chunks into the retrieved-memories section. The entity doesn't know retrieval fired — she just reads her memories.

**Explicit `memory_search`** is a tool. The entity calls it during her agent loop with a query she chose. Results appear in her tool trace as a tool result; she sees what she searched for, what came back, and reasons about it.

**Both paths call the same retrieval function.** Same ranking, same filtering, same active-conversation exclusion. What differs is where the results go (context section vs. tool trace) and the caller (context construction vs. the tool dispatch layer).

The separation matters for Principle 9 (infrastructure is hidden, capabilities are experienced). Automatic retrieval is infrastructure — she doesn't see the act. Explicit search is a capability — she does. Same mechanism, different experience.

---

## Trust weighting details

### Why multiplicative on RRF score, not on each signal

If trust were applied per-signal (boost vector hits by trust, separately boost BM25 hits by trust), the same chunk could receive its trust bonus twice when it appears in both lists. Applying trust once on the fused score keeps the weighting clean — trust affects final ranking, fusion affects which chunks make it into final ranking.

### Initial weights

```python
TRUST_WEIGHTS = {
    "firsthand": 1.0,
    "secondhand": 0.85,
    "thirdhand": 0.7,
}
```

Starting values. Tune based on retrieval behavior once the corpus has a mix of chunk types. Sharper spread (e.g., 1.0/0.7/0.5) pushes harder toward firsthand; softer (1.0/0.9/0.8) treats all sources nearly equally. Configuration, not architecture.

### Unknown or missing trust

If a chunk has a `source_trust` value not in the weights dict (new source type added without weights update), treat it as `1.0` (no penalty) and log a warning. Don't silently demote.

---

## Distance threshold details

### Initial value

`DISTANCE_THRESHOLD = 0.8` (cosine distance). Anything > 0.8 on the vector leg gets dropped before fusion.

Rationale: cosine distance on normalized 768-dim embeddings typically produces:

- 0.0–0.4: strong semantic match
- 0.4–0.7: plausible, topical
- 0.7–1.0: weakly related
- 1.0–2.0: unrelated or opposite

0.8 filters truly weak matches while permitting topically-related content. Tune based on behavior. If aggressive filtering drops too much good content, push to 0.9; if too much noise slips through, tighten to 0.7.

### Interaction with BM25

A chunk can make it into final ranking via BM25 alone (strong lexical match, weak or absent vector match above threshold). This is correct — a chunk containing the exact proper noun in the query should surface even if its vector representation is topically adjacent rather than identical. That's the whole point of hybrid retrieval.

---

## Query shape

### Automatic retrieval

Query = the user's most recent message text, verbatim. Same string goes to both vector embedding (for ChromaDB) and FTS5 MATCH (for BM25).

Note on FTS5 MATCH syntax: by default, FTS5 treats the query as a conjunctive token list — all terms must appear somewhere in the text. For retrieval purposes we want the default OR-ish behavior (match any strong term). Query rewrite: split the query into tokens, join with spaces and the `OR` operator, wrap in FTS5 MATCH. Also escape any FTS5 special characters (`"`, `-`, `*`, `(`, `)`) that could be parsed as operators — safest is to wrap each token in double quotes, which makes it a literal term match.

Example rewrite: user message `"What did we decide about save_and_chunk?"` → FTS5 query `"What" OR "did" OR "we" OR "decide" OR "about" OR "save_and_chunk"`. BM25 ranks chunks containing more rare tokens (like `save_and_chunk`) higher automatically.

### Explicit `memory_search`

Query = whatever the entity passed as the tool's argument. Same rewrite pipeline. She formulates her own queries.

### First turn of a new conversation

No active conversation context — retrieval runs against the user's opening message (e.g., "hey"). Results may be weak. Acceptable — the entity handles a sparse first turn the way she would anyway.

### Autonomous sessions

Per Context Construction v1.1, autonomous sessions retrieve against the task description. Handled at the caller layer (context construction for autonomous context). Retrieval doesn't care what the query is; it retrieves against whatever query it's given.

---

## Result count

Context Construction v1.1 already owns this decision: floor 3, ceiling 15, default 8 chunks surfaced into the retrieved-memories section. Memory squeeze adjusts within floor/ceiling based on budget.

**Retrieval does not enforce the floor/ceiling.** It returns up to 20 ranked candidates (`max_results` default). The caller — context construction for automatic, the `memory_search` tool for explicit — decides how many to consume.

20 provides enough headroom for context construction to apply budget selection without running short, and for `memory_search` to return a substantive list the entity can reason over. Callers can pass a different `max_results` if they have a reason.

---

## Interface

```python
def retrieve(
    query: str,
    chromadb_path: str,
    working_path: str,
    active_conversation_id: str | None = None,
    max_results: int = 20,
    distance_threshold: float = 0.8,
    trust_weights: dict | None = None,
    rrf_k: int = 60,
    top_k_per_signal: int = 30,
    ollama_host: str = "http://localhost:11434",
) -> list[dict]:
    """Hybrid retrieve from ChromaDB + FTS5, fused via RRF.

    Args:
        query: natural-language query string.
        chromadb_path: path to the ChromaDB persistent store.
        working_path: path to working.db (hosts the FTS5 index).
        active_conversation_id: if provided, chunks from this conversation
            are excluded (post-filter for vector, SQL filter for BM25).
        max_results: maximum final ranked results to return. Defaults to 20.
        distance_threshold: cosine distance above which vector candidates
            are dropped before fusion. Defaults to 0.8. BM25 has no
            equivalent threshold (MATCH is its own filter).
        trust_weights: mapping of source_trust → multiplier applied to
            fused RRF score. Defaults to firsthand=1.0, secondhand=0.85,
            thirdhand=0.7. Unknown values get weight 1.0.
        rrf_k: RRF fusion constant. Defaults to 60.
        top_k_per_signal: how many candidates each signal returns before
            fusion. Defaults to 30. Higher values increase recall at the
            cost of more filter/fusion work; lower values risk missing
            chunks that rank mid-list in both signals.
        ollama_host: Ollama endpoint for embedding the query.

    Returns:
        A ranked list (most relevant first) of dicts:
            {
                "chunk_id": str,
                "text": str,
                "metadata": dict,              # full chunk metadata
                "vector_distance": float|None, # None if chunk came only from BM25
                "vector_rank": int|None,       # 1-indexed rank in vector list, or None
                "bm25_rank": int|None,         # 1-indexed rank in BM25 list, or None
                "rrf_score": float,            # fused RRF score
                "adjusted_score": float,       # rrf_score * trust_weight
            }
        Empty list if nothing passes filters (valid outcome).

    Raises:
        EmbeddingError: Ollama unreachable or bad response.
        ChromaError: ChromaDB query failure.
        sqlite3.DatabaseError: FTS5 query failure.
        ValueError: empty query or invalid input.
    """
```

### Design notes on the interface

- **Both store paths are parameters.** Retrieval is stateless; caller owns paths. Matches the pattern in `chroma.py`, `embeddings.py`, `writes.py`.
- **Per-signal ranks are returned** so callers and debuggers can see why a chunk ranked where it did. Context construction ignores these; a future retrieval-observability tool would use them.
- **`top_k_per_signal` exposed as a tuning knob.** Separate from `max_results` — controls how much pool each signal contributes to fusion, independent of how many final results come back.
- **Full metadata dict is returned**, not a filtered subset. The caller needs `source_type` for per-chunk framing (CC v1.1 renders by source_type), `user_id` for knowing who the conversation was with, `created_at` for chronological choices.

---

## FTS5 index shape (schema impact)

Adding the FTS5 index requires a schema update. Details in the Schema Design v1.4 companion update to this doc. Summary of impact:

- New virtual table `chunks_fts` in `working.db`:
  ```sql
  CREATE VIRTUAL TABLE chunks_fts USING fts5(
      chunk_id UNINDEXED,
      text,
      conversation_id UNINDEXED,
      user_id UNINDEXED,
      source_type UNINDEXED,
      source_trust UNINDEXED,
      created_at UNINDEXED,
      tokenize = 'unicode61 remove_diacritics 2'
  );
  ```
- Write-path hook: every chunk written to ChromaDB also inserts into `chunks_fts`. The ordering (ChromaDB first, then FTS5) means a mid-write failure leaves a chunk findable via vector search but not BM25 — degraded but functional, and the rechunk-at-close path brings FTS5 back into sync.
- No index on `conversation_id` at SQL level (FTS5 unindexed columns are stored but not searchable via MATCH). The active-conversation filter runs as a normal `WHERE` clause after FTS5 produces its candidate set — SQLite handles this efficiently at FTS5 top-K scales.
- Rebuild path: if `chunks_fts` is wiped or drifts out of sync, rebuild by iterating ChromaDB's collection and re-inserting. Standalone maintenance function.

The *implementation* of the write-path hook and rebuild function is a separate Dev_Doc (BM25 Integration Spec), not this design doc.

---

## Integration points

Three callers will eventually invoke `retrieve`:

1. **Context construction for conversation sessions.** Called at every turn. Passes `active_conversation_id` to exclude the current conversation's own chunks.
2. **Context construction for autonomous sessions.** Same function. Query comes from the task description. `active_conversation_id` is `None` (no conversation is active).
3. **The `memory_search` tool.** Entity-initiated. Pass-through of her query argument. `active_conversation_id` is the current conversation if she's in one.

None of these callers exist in code yet. Retrieval gets built independently and gets called when the conversation engine and context construction code land.

---

## Tuning knobs

All configuration, not architecture:

- `DISTANCE_THRESHOLD` (0.8) — vector-leg filter tightness.
- `TRUST_WEIGHTS` — source bias.
- `rrf_k` (60) — fusion constant.
- `top_k_per_signal` (30) — pool size per signal before fusion.
- `max_results` (20) — final result count upper bound.
- FTS5 tokenizer (`unicode61 remove_diacritics 2`) — stem/accent behavior. Rarely changed.
- Query rewrite shape (OR-joined token list) — could become AND-ish or phrase-aware for specific cases.

All overrideable per call. Sensible defaults ship. Tuning happens by watching retrieval behavior, not by redesigning.

---

## What this design does NOT decide

- **FTS5 write-path integration (implementation).** Covered by the BM25 Integration Spec. This doc specifies the index shape and the semantic; the spec handles the code.
- **Backfill mechanism when FTS5 is added to an existing install.** Mentioned in schema v1.3 and detailed in the integration spec.
- **Cross-encoder reranking.** Known improvement path if vector + BM25 isn't enough. Not day-one.
- **Query expansion.** Reformulating vague queries before retrieval. Not day-one.
- **Negative examples / blocklist.** No mechanism to say "never retrieve this chunk again." Principle 6 (never delete) and Principle 11 (personality earned) both push against this. Not a day-one concern.
- **Per-user retrieval filtering.** Rejected by Requirement 8 and Principle 11. Never a knob we will add.
- **Caching.** Retrieval is stateless. Callers can cache if they want; retrieval itself doesn't.

---

## Open questions

**a. FTS5 query rewrite default.** OR-joined tokens is permissive (any term match). For multi-token exact-phrase queries like `"save_and_chunk"`, phrase matching would be stronger. Simple OR is day-one; add phrase detection if specific queries reveal the need.

**b. Stopword handling in BM25.** FTS5's default tokenizer doesn't remove stopwords. "The" and "is" will match very common chunks and contribute noise to BM25 rank. BM25's IDF weighting mostly compensates — common tokens get low weight. If behavior shows stopwords dominating, add a stopword list.

**c. Distance threshold calibration.** 0.8 is an educated guess. Actual values from running against representative queries will inform. Add a tuning pass after a week of use.

**d. Per-source-type distance thresholds.** Plausible that articles (longer, more verbose) have systematically higher distances than conversation chunks (shorter, focused). A single threshold may be wrong. Flag for tuning.

**e. RRF k value.** 60 is literature default. Values from ~30 to ~80 are plausible. Tuning knob if fusion behavior shows bias.

**f. `top_k_per_signal` tradeoff.** 30 is a guess. Smaller (e.g., 15) runs faster but may miss mid-list hits that would have fused strongly. Larger (e.g., 50) covers more ground at slight query-time cost. Depends on corpus size and chunk count.

**g. What happens if ChromaDB has zero chunks (fresh install).** Vector returns `[]`. BM25 over an empty FTS5 table returns `[]`. Fusion returns `[]`. Retrieval returns `[]`. Context construction handles the empty case (no retrieved-memories section). Nothing to fix; just flagged so tests cover the case.

**h. Query embedding dimensions.** Query embedding must match chunk embedding dimensions — same model (nomic-embed-text), 768 dims. If the embedding model ever changes, the whole collection needs re-embedding. Standard property of vector stores; flagged here because retrieval is where a dimension mismatch would surface.

---

## Deferred

- **User-voice FTS5 index** (per Memory Requirements open question d). A separate narrow BM25 index over user messages only. Likely subsumed by the general-purpose BM25 this doc defines; revisit if specific gaps on user-voice queries appear.
- **Cross-encoder reranking.** Second-stage quality improvement. Not day-one.
- **Query synthesis from recent exchanges** (per Context Construction v1.1 open question b). Day-one uses just-the-last-message. Revisit if short/ambiguous queries produce thin retrievals.
- **Retrieval-quality observability.** A debug surface showing per-chunk vector distance, BM25 rank, fusion score, and trust weight. Useful for tuning pain; not blocking.
- **Phrase-aware FTS5 queries.** Add if query behavior suggests it.
- **Stopword handling tuning.** Add if BM25 behavior shows stopword dominance.

---

## Cross-references

- **Memory Requirements Draft v2** — requirements 15 (unified space), 16 (hybrid support — implemented day-one per this design), 17 (provenance), 18 (trust), 19 (low-confidence filter), 20 (tunability), 25 (fabrication events), and open question (d) (user-voice index — deferred).
- **Schema Design v1.4** — adds `chunks_fts` virtual table and documents FTS5 integration. This retrieval design depends on v1.4.
- **Chunking Strategy v1.1** — flags "same-conversation duplication" which this doc solves via active-conversation exclusion.
- **Context Construction v1.1** — the caller for automatic retrieval; owns floor/ceiling/budget; specifies per-source-type framing that this retrieval supplies metadata for.
- **Tool Framework v1** — `memory_search` is a day-one tool; this retrieval is what it calls.
- **Guiding Principles v1.1** — Principle 7 (retrieval determines intelligence), Principle 8 (framing), Principle 9 (infrastructure vs. capabilities), Principle 11 (personality earned), Principle 14 (diagnose before conclude — the observability bit).

---

## Divergence from Aion (noted for provenance)

This design adopts Aion's core hybrid retrieval pattern because it worked. Specific differences:

- **RRF replaces Aion's fusion method** (whatever Aion used — probably a weighted sum based on the prior-project pattern). RRF is simpler and doesn't require score normalization.
- **General-purpose BM25 over all chunks** rather than Aion's user-voice-specific FTS5 index. Broader coverage on day one; narrower user-voice indexing deferred.
- **Trust weighting is explicit and multiplicative** rather than implicit in source-type-specific handling. Principle 18 framing — trust is a scalar property of chunks, not a category label shaping code paths.

These are refinements, not rejections. If any of them proves worse than the Aion version in practice, the revision path is open.

---

*Project Tír Retrieval Design · v1 · April 2026 (revised same-day from vector-only draft to hybrid day-one per direction)*
