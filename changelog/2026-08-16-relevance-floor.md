# 2026-08-16 — Retrieval relevance floor + tri-state retrieval markers

## Summary

Retrieval used to return a fixed quota (8 chunks) regardless of match quality:
`fused.sort(...)` + `fused[:max_results]` had no floor, and `DISTANCE_THRESHOLD` (0.8)
never bound in practice. A query with nothing relevant in memory filled its quota with the
least-bad chunks in the store, and the entity could not tell "I have a record of this" from
"I was handed eight things that don't match" — which produced at least one wrong live answer.

This adds a three-part floor (vector distance, FTS5 stopword removal, per-term lexical score)
plus a tri-state marker so the *absence* of memory is stated explicitly instead of silently
filled. Implements `PLAN-2026-08-16-relevance-floor.md` with the approved Q5 amendment.

**Measured on the live store, shipped defaults: 11/11 on-topic queries retain their correct
top hit; 9/9 off-topic queries now return zero instead of eight.** No commit.

## One approved parameter changed shape — read this

The plan approved an **absolute** BM25 floor of `-9.0`. Implementing it, I found it was
wrong, and the error was mine: I calibrated `-9.0` against BM25 scores measured **before**
the stopword fix existed, then proposed applying it **after**. Stopword removal reduces the
number of matched terms, which shrinks score magnitude, so the two components were measured
in different pipeline states and their thresholds were never valid together.

Re-measured on the live store with the stopword fix active, an absolute `-9.0` would have
dropped:

| query | bm25 best | fate under -9.0 |
|---|---|---|
| `anam_generated_00013_.png` (exact filename) | -7.768 | **dropped** |
| `rainbow` | -5.613 | **dropped** |
| `moltbook` | -1.066 | **dropped** |
| 7 of 10 on-topic conversational queries | -1.07 … -8.0 | **dropped** |

That destroys exactly the exact-match lexical recall the BM25-only exemption exists to
protect — a principle the same task approved as "load-bearing, not a nicety". Absolute and
per-term separation, side by side:

| | on-topic | off-topic | separated? |
|---|---|---|---|
| absolute best score | -1.07 … -18.95 | -3.74 … -6.99 | **no, overlaps** |
| **per matched term** | **-3.05 … -7.77** | **-0.94 … -1.97** | **yes** |

**Shipped: `BM25_SCORE_PER_TERM_THRESHOLD = -2.5`** — the midpoint of the per-term gap
`[-3.051, -1.971]`, chosen by the same method as the distance floor. This is a change to an
explicitly approved value, so it needs sign-off; it is one constant and one division, trivial
to revert.

## A second problem the plan did not anticipate: BM25 is meaningless on a small corpus

BM25 is IDF-driven, so score magnitude scales with corpus size. Measured directly:

| store size | score of a *perfect* unique-term match |
|---|---|
| 1 chunk | **-0.000001** |
| 201 chunks | -5.54 |
| live (255 chunks) | -11.4 … -22.4 for multi-term on-topic queries |

Any fixed lexical floor therefore suppresses essentially all lexical recall in a small
store — including **immediately after a go-live wipe**, when the store is smallest and every
memory is new. Shipped `BM25_FLOOR_MIN_CORPUS_CHUNKS = 50`: below that, the lexical floor is
not applied at all. This is what surfaced it — two upload tests that retrieve a unique marker
from a 1-2 chunk test store went red, which was the pathology reproducing, not test noise.

## What changed

- **`tir/config.py`**
  - `DISTANCE_THRESHOLD` 0.8 → **0.40**, with a comment recording both probes, the measured
    gap `[0.3876, 0.4164]`, and that the margin is tight (one on-topic query cleared by
    0.0124) — explicitly a first-cut value to revisit as the corpus grows.
  - New `BM25_SCORE_PER_TERM_THRESHOLD = -2.5` and `BM25_FLOOR_MIN_CORPUS_CHUNKS = 50`, both
    commented with the measurement and the fragility caveat.
- **`tir/memory/retrieval.py`**
  - `_STOPWORDS` (~80 function words) applied in `_sanitize_fts5_query`; an all-stopword
    query returns `""` and the existing guard skips the BM25 leg entirely.
  - Per-term lexical floor after `search_bm25`, gated on corpus size, **failing open** when a
    candidate has no `bm25_score` (absence of a rank is not evidence of a weak match, and
    dropping on it would quietly defeat the BM25-only exemption).
  - `_log_floor_margin` / `_log_bm25_floor_margin`: DEBUG-level, never user-visible, logging
    best score, threshold, **signed margin**, and kept/total for both legs on every query —
    so threshold drift shows up in the trace without re-running a manual probe.
  - The distance-filter site now carries a comment explaining that the floor is pre-fusion
    and vector-only, and why the BM25-only exemption is deliberate.
- **`tir/engine/context.py`** — `RETRIEVAL_SKIPPED` / `RETRIEVAL_ATTEMPTED` /
  `RETRIEVAL_FAILED`, the two marker strings, a `retrieval_status` parameter on both prompt
  builders, and the `elif` chain in Section 6.
- **`tir/api/routes.py`** — status computed at the real retrieval site (541-563), passed to
  the prompt builder, surfaced in the streamed debug event beside `retrieval_skipped`, and
  **persisted in the `chat_debug.jsonl` trace record** next to `retrieved_chunk_count`. The
  persisted copy was added during the live check: the first turn showed `retrieval_status:
  None` in the trace file because only the streamed event carried it, and the trace file is
  what later diagnosis actually reads — a bare `retrieved_chunk_count: 0` is exactly the
  ambiguity this task exists to remove.
- **`docs/PROMPT_INVENTORY.md`** — regenerated (new prompt strings).

`memory_search` needed no change: it calls `retrieve(query=..., max_results=5)` with no
threshold overrides, so it inherits both floors from the config defaults — verified, not
assumed.

## The tri-state marker (approved amendment)

| situation | prompt gets |
|---|---|
| greeting / `skip_memory` policy | nothing — unchanged behaviour |
| retrieval ran, returned nothing above the floor | "Memory search ran … returned nothing above the relevance threshold. That is a fact about the search, not about the past…" |
| retrieval ran and **raised** | "Memory search encountered an error … This is a failure of the search itself, not evidence about what is or is not in memory — nothing was actually looked up." |

A failed search must not present identically to an empty one — the retrieval-layer version of
the tool-honesty rule already in `OPERATIONAL_GUIDANCE.md`. The status is threaded from
`routes.py`, **not** from the dead `context.py:259` branch.

## Tests / checks run

- **Full suite: 979 passed** (963 baseline + 16 new), stable across repeated runs.
- `tests/test_retrieval.py` (+10): distance floor drops far candidates; empty result is a
  valid outcome; BM25-only chunk exempt from the distance floor (and arrives with
  `vector_distance`/`vector_rank` of `None`); weak lexical candidates dropped per-term; a
  **single-term** query is not penalised (the exact-filename regression); floor skipped on a
  small corpus; unscored candidate fails open; stopwords dropped; content words survive a
  phrase containing stopwords; all-stopword query skips the BM25 leg entirely.
- `tests/test_context.py` (+6): each of the three marker states, no marker by default, no
  marker when chunks exist, and marker chars reported in the prompt breakdown.
- `tests/test_api_agent_stream.py`: `retrieval_status` asserted `"skipped"` and `"attempted"`
  in the debug event.
- **Live end-to-end against the production store with shipped defaults:** 11 on-topic
  queries → all non-zero (2–8 chunks), correct top hit each; 9 off-topic → **all zero**.
- Corpus guard costs **0.44 ms/call** at 255 rows — negligible beside the embedding
  round-trip. Production store unchanged by this work (255 Chroma / 255 FTS).

## Runbook executed (2026-08-16)

1. **Backup:** `backups/2026-08-16T232645Z` — working.db, archive.db, chroma (5 files), 31
   workspace files, governance files. Taken before any live turn.
2. **Live device check** against a real server started on `127.0.0.1:8000` with
   `ANAM_DEBUG_PROMPT=1` (it was not already running). Two real turns, then stopped.

| turn | `retrieval_status` | chunks | zero marker | error marker |
|---|---|---|---|---|
| "What did the plumber say about the water heater warranty?" (nothing in memory) | `attempted` | **0** | **yes** (241 chars, matching `NO_MATCHING_MEMORY_MARKER`) | no |
| "What did you say about AI temperature settings?" (real memory) | `attempted` | **4** | no | no |

The marker text was confirmed present verbatim in the captured `system_prompt`, and the
`retrieval_marker_chars: 241` breakdown field matched the constant's length.

**What the entity actually said** — the behaviour this whole change exists for:

> "Lyle, I don't have any record of a plumber or a conversation regarding a water heater
> warranty in our current interaction or my retrieved memories. If you've discussed this with
> someone else or in a different context, you'll need to remind me of the details."

It distinguished *not in my retrieved memories* from *never happened*, and asked to be
reminded — which is precisely the failure mode from the earlier live incident, now corrected.
The on-topic control turn retrieved 4 real chunks and answered from them accurately
(correctly recalling a June 3rd exchange), confirming the floor does not suppress genuine
recall.

3. **Server stopped.** Verified not listening afterwards.

**What the device check wrote to the production store** (stated so it can be removed if
unwanted): one new conversation `8f66c5bc-60d6-4137-be5c-aae2feea7063` with 4 messages
(2 user, 2 assistant), and one checkpoint chunk. Store went 60 → 61 conversations,
738 → 742 messages, 255 → 256 Chroma documents, 255 → 256 FTS rows.

4. **Final full suite after the trace-field addition: 979 passed.**

## Known limitations

- **The distance margin is tight.** One legitimate on-topic query cleared 0.40 by 0.0124. An
  awkwardly phrased real query can lose its vector leg; the BM25-only exemption and the
  zero-result marker are what keep that survivable and visible rather than silent.
- **Both floors are calibrated to one corpus at 255 chunks.** The lexical one is the more
  fragile even after normalisation. The margin logging exists so drift is noticeable.
- **`BM25_FLOOR_MIN_CORPUS_CHUNKS = 50` is a judgement call**, not a measured optimum — it
  sits well above the 1-chunk pathology and well below the live store. The transition
  behaviour between 50 and ~200 chunks is untested with real queries.
- **`memory_search`'s empty-result wording was left alone**: "No indexed prior records found
  for that query." That is defensible as-is, but the floor makes it fire far more often, and
  it reads closer to "no such record exists" than the new context marker does. Aligning it is
  a small follow-up worth considering — not done here, since it changes tool output beyond
  the approved scope.
- The dead `context.py:259` branch is **noted in BACKLOG.md, not deleted**, as instructed.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes — nothing is deleted or rewritten; this filters what is
   *shown* per query. Every chunk remains in the store and retrievable by a better-matching
   query. 5. **Derived artifacts traceable?** Unchanged. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Unchanged — artifact recall verified unharmed
   (exact-filename queries still match). 8. **Context construction inspectable?** Improved:
   `retrieval_status` in the debug event, margin logging on both floors.
9. **More cumulative?** Yes, indirectly — the entity can now distinguish "no matching memory"
   from "no memory", which is a prerequisite for honest recall. 10. **Anam/entity distinction?**
   Preserved. 11. **Migration?** None. 12. **Tests?** Above. 13. **Core substrate changed
   unnecessarily?** Retrieval is core and this is a real behaviour change — deliberate, the
   point of the task, and measured end-to-end. 14. **External dependencies?** None.
15. **Workspace vs. self-modification?** Unaffected. 16. **Legacy renaming avoided?** Yes.

Invariant 4 note: the marker is the load-bearing part. Filtering alone would have made the
entity *quieter* about weak matches without making it *honest* about absence; the explicit
"the search found nothing, which is not the same as it never happening" is what closes the
gap that produced the wrong live answer.

## Follow-up

- Both deviations (per-term BM25 floor at -2.5 replacing the absolute -9.0, and the
  small-corpus guard) were **approved 2026-08-16** before the runbook was run.
- Decide whether to keep the device-check conversation `8f66c5bc` in the store or remove it.
- Re-probe both thresholds once the corpus is meaningfully larger — the margin logging is
  there so drift is noticeable without a manual probe.
- Consider aligning `memory_search`'s empty-result wording with the new marker.
- Dead `context.py:259` branch is recorded in BACKLOG.md for the cleanup pass.
