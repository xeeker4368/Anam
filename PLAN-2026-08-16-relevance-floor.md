# PLAN — Post-fusion relevance floor for retrieval. PLAN ONLY.

**Date:** 2026-08-16 · **Mode:** plan only. **No code, no commit.** Every number below was
measured read-only against the live store today. The three decisions in `ACTIVE_TASK.md` are
honoured, not relitigated — but one of them turns out to be **insufficient as stated**, and
§4 reports that with the measurement rather than quietly patching around it.

---

## NORTH_STAR check

Retrieval currently hands the entity eight chunks whether or not anything matched, so the
entity cannot tell "I have a record of this" from "I was handed the eight least-irrelevant
things in the store." That is a direct threat to Invariant 4 — the entity must be able to
distinguish what it experienced from what it did not — and it has already produced a wrong
answer in a live incident. A floor plus an explicit "the search found nothing" marker makes
the *absence* of memory legible instead of silently filled. No content is authored, nothing
is deleted, and the mechanism is a filter plus one prompt line. **Aligned.**

The honest tension: a floor can hide a real memory that scored badly. That is why the
BM25-only exemption exists (§3), why the marker exists (§5), and why §2 states the margin
rather than claiming a safe threshold.

---

## 0. Headline — the floor alone does nothing. Measured.

End-to-end `retrieve()` result counts, `max_results=8`, 8 on-topic and 9 off-topic
conversational queries:

| configuration | on-topic | off-topic |
|---|---|---|
| today | 8 everywhere | **8 everywhere** |
| **distance floor 0.40 only** | 8 everywhere | **8 everywhere — no change at all** |
| distance floor + stopword fix | 8 everywhere | 0–8, still leaks (4 of 9 return ≥7) |
| **distance floor + stopwords + BM25 score floor** | **2–8, every query keeps its correct top hit** | **0 for all 9** |

The distance floor changes *nothing* end-to-end on its own, because BM25 returns 30
candidates for any query and BM25-only chunks are exempt by design (decision 2). The pairing
with the stopword fix is therefore not a nicety — it is load-bearing. And the stopword fix
**by itself does not close the loophole either**: after stopword removal, "what's a good
recipe for sourdough starter?" still returns 30 BM25 candidates, because OR-matching on
ordinary content words ("good", "time", "much") hits the corpus everywhere. See §4.

---

## 1. Q1 — Conversational distance probe. **The gap holds, and it is wider than the image probe suggested.**

Method: pulled real user turns out of the conversation chunks, built queries a person would
plausibly ask whose answers *are* in the store, plus realistic household questions whose
answers are *not*, plus three deliberately hard near-misses.

| bucket | n | best-hit cosine distance |
|---|---|---|
| **on-topic** (temperature settings, refusal, May 8 journal, moltbook, source labels, personality, Cleveland weather, two-user question, green cheese) | 9 | **0.2127 – 0.3876** |
| **near-miss** (AI *humidity* settings, sister's birthday, garage renovation) | 3 | **0.4164 – 0.4688** |
| **off-topic** (brake pads, sourdough, dentist, blood test, roof repair, keys, pharmacy) | 7 | **0.4191 – 0.5518** |

**The separation holds cleanly: worst on-topic 0.3876 < best near-miss 0.4164.** Every
on-topic query's top hit was verified to be the *correct* memory, not a coincidence.

It is not the same numbers as the image-prompt probe, though, and the difference matters:
conversational on-topic hits go *lower* (0.2127 vs 0.3132 best) and also *higher* (0.3876 vs
0.3219 worst). So the on-topic band is wider for conversational recall, and the usable gap is
narrower than the image probe implied. The direction of the original finding survives; the
comfort margin does not.

## 2. Q2 — Threshold. **0.40, from both probes combined.**

| probe | on-topic best-hit | off-topic / near-miss best-hit |
|---|---|---|
| image-prompt (2026-08-15) | 0.3132 – 0.3219 | 0.4242 – 0.5684 |
| conversational (2026-08-16) | 0.2127 – 0.3876 | 0.4164 – 0.5518 |
| **combined** | **max 0.3876** | **min 0.4164** |

The whole usable gap is `[0.3876, 0.4164]`, width 0.0288, midpoint 0.4020. **0.40** sits
essentially at the midpoint: it admits all 12 measured on-topic queries and excludes all 10
off-topic and all 3 near-miss queries.

Per-query survivor counts at 0.40 (of 30 vector candidates): on-topic retain 1–13; off-topic
retain **0** in every case. One on-topic query ("how should you treat contributions from
Lyle and his wife?") retains exactly **1** — the margin there is 0.0124.

**Stated plainly: this is tight.** A legitimate but awkwardly-phrased query could land above
0.40 and lose its vector leg. Two things keep that from being a silent failure: the BM25-only
exemption (§3), which measurably rescues exactly this kind of query, and the marker (§5),
which makes a miss visible rather than answered around. The threshold is calibrated to this
corpus at this size and should be re-probed as the store grows.

## 3. Q3 — BM25-only exemption. **Structural, not new code. Cited from the actual shape.**

The floor is applied **pre-fusion** on the vector leg (`retrieval.py:320-323`), so the
exemption falls out of the existing architecture rather than needing a rule: a chunk failing
the floor is simply absent from `vector_filtered`, and if BM25 also returned it, it enters
fusion through the BM25 branch instead.

`_fuse_rrf` (`retrieval.py:234-250`) gives a BM25-only chunk exactly this shape:

```python
chunks[cid] = {
    "chunk_id": cid, "text": item["text"],
    "metadata": {"source_type": item.get("source_type", "unknown"), ...},
    "vector_distance": None,      # <-- the detection signal
    "vector_rank": None,
    "bm25_rank": rank,
    "rrf_score": 1.0 / (k + rank),
}
```

So "BM25-only" is `vector_rank is None` / `vector_distance is None`. No new field, no
change to `_fuse_rrf`.

**The exemption earns its place — measured.** Under the full proposal, 10 of the 44 chunks
retained across the 8 on-topic queries (23%) arrive BM25-only. The clearest case is
"you said the moon is made of green cheese": 6 chunks retained, **5 of them lexical-only**.
That is an exact-phrase recall the vector leg largely missed, and a distance-only floor
would have thrown it away.

## 4. Q4 — FTS5 stopword fix. **Necessary, and NOT sufficient. This is the one place the task brief falls short.**

Current `_sanitize_fts5_query` (`retrieval.py:69-87`) splits on whitespace, strips FTS5
operators, quotes each token and joins with `OR`. No stopword removal, so `"a of the"`
matches 30 chunks.

**Proposed change:** drop a small explicit English stopword list (~80 function words,
lower-cased, punctuation-stripped) before quoting; if no tokens survive, return `""`, which
the existing `if fts5_query:` guard (`retrieval.py:336`) already handles by skipping the BM25
leg entirely. Legitimate phrases are unaffected because the *content* words survive: "the
roof repair" → `"roof" OR "repair"`, "The Architecture of Thought" → `"Architecture" OR
"Thought"`. A title that is *only* stopwords would lose its BM25 leg, which is the correct
trade and is why the vector leg still runs.

**But measured, that is not enough.** BM25 candidate counts after stopword filtering:

| off-topic query | before | after stopwords |
|---|---|---|
| dentist appointment | 30 | **0** ✓ |
| brake pads / Subaru | 30 | **4** ✓ |
| keys in the kitchen | 30 | **2** ✓ |
| **sourdough starter** | 30 | **30** ✗ |
| **roof repair** | 30 | **30** ✗ |
| **pharmacy close Sunday** | 30 | **30** ✗ |

OR-matching on ordinary content words still hits the whole corpus. End-to-end, distance floor
+ stopwords leaves 4 of 9 off-topic queries returning ≥7 chunks.

**Recommended addition: a BM25 score floor.** `search_bm25` already returns `bm25_score`
(`db.py:917` — SQLite FTS5 `rank`, more negative = better). Measured best-hit scores:

| bucket | best-hit `bm25_score` |
|---|---|
| on-topic | **−11.40 to −22.42** |
| off-topic | **−6.10 to −7.72** |

Gap `[−11.40, −7.72]`, midpoint ≈ −9.55. **Proposed floor: −9.0**, biased slightly toward
keeping recall. With all three components, every off-topic query returns **0** and every
on-topic query keeps its correct top hit.

**Caveat, stated because it matters:** FTS5 `rank` is not normalised — its magnitude depends
on query length and corpus statistics — so this floor is more fragile than the distance one
and is calibrated to the store as it stands today. It should be re-probed as the corpus
grows, and it is the first thing to suspect if legitimate lexical recall degrades. This
addition goes beyond decision 2 as written (which specified only the stopword fix), so it is
flagged for the reviewer in §Open items rather than assumed.

## 5. Q5 — Zero-result marker. **Needs a tri-state, because `[]` is currently ambiguous.**

`context.py:258-273` cannot tell the difference today:

```python
if retrieved_chunks is None and user_message and not is_greeting(user_message):
    try:    retrieved_chunks = retrieve(...)
    except: retrieved_chunks = []          # failure
if retrieved_chunks:                        # truthiness only
    sections.append(_format_retrieved_memories(retrieved_chunks))
```

And on the live API path the auto-retrieval branch never runs at all: `routes.py:577-582`
calls `build_system_prompt_with_debug(user_name=…, retrieved_chunks=retrieved_chunks, …)`
without `user_message`, and `retrieved_chunks` is initialised to `[]` and left that way when
`retrieval_skipped` is true. So `[]` currently means any of: retrieval found nothing,
retrieval raised, retrieval was skipped as a greeting, or the policy said `skip_memory`.
**Only the first should fire the marker.**

**Design:** add an explicit `retrieval_attempted: bool = False` parameter to
`build_system_prompt` / `build_system_prompt_with_debug`; set it `True` only when `retrieve()`
returned normally. `routes.py` passes `retrieval_attempted = not retrieval_skipped and not
retrieval_failed`. The marker becomes an `else` branch gated on it:

```python
if retrieved_chunks:
    sections.append(_format_retrieved_memories(retrieved_chunks))
elif retrieval_attempted:
    sections.append(ZERO_RESULT_MARKER)
```

**Proposed wording** (a statement about the search, never about the past, per decision 3):

> Memory search ran for this message and returned nothing above the relevance threshold.
> That is a fact about the search, not about the past: no closely-matching memory was
> retrieved, which is not the same as the thing never having happened.

Fires only when retrieval ran and returned empty. Does **not** fire on greetings, on
`skip_memory` policy turns, on retrieval exceptions, or on any turn that produced chunks.

## 6. Q6 — Artifact boosts. **No interaction. Verified, not assumed.**

`_apply_artifact_boosts` runs **post-fusion** (`retrieval.py:362-363`) and only multiplies
`adjusted_score`; it can never resurrect a chunk the pre-fusion floor removed. `artifact_intent`
remains `False` for image-generation requests (the prior diagnostic's finding is unchanged —
nothing here touches `has_recent_artifact_intent`).

Artifact chunks arriving BM25-only keep their boost eligibility: `search_bm25` selects
`source_type`, and `_fuse_rrf`'s BM25-only branch copies it into `metadata`, which is what
`_apply_artifact_boosts` reads (`retrieval.py:164`).

Measured under the full proposal — artifact recall is unharmed:

| query | chunks | top hit |
|---|---|---|
| `anam_generated_00013_.png` | 8 | artifact chunks at distance 0.33–0.36 |
| `tell me about artifact 5c1577e5-…` | 8 | artifact chunks at 0.235–0.273 |
| `what is in the file project_anam_simple_roadmap_recent.md` | 8 | correct artifact, `_artifact_match` → `True/filename` |

Artifact queries sit far below 0.40 and are never near the floor.

---

## EXACT DIFF SCOPE

### `tir/config.py`
- `DISTANCE_THRESHOLD` 0.8 → **0.40**, with a comment recording the two probes and the
  measured gap.
- New `BM25_SCORE_THRESHOLD = -9.0` (only if §Open item 2 is approved).

### `tir/memory/retrieval.py`
- New `_STOPWORDS` frozenset (~80 function words) and stopword filtering inside
  `_sanitize_fts5_query`; return `""` when nothing survives.
- After `search_bm25`, drop candidates with `bm25_score > BM25_SCORE_THRESHOLD`
  (pending Open item 2).
- No change to `_fuse_rrf`, `_apply_artifact_boosts`, `_artifact_match`, or the vector
  filtering line itself — the floor is the existing `distance_threshold` comparison with a
  new default.

### `tir/engine/context.py`
- `ZERO_RESULT_MARKER` constant; `retrieval_attempted` parameter on `build_system_prompt` and
  `build_system_prompt_with_debug`; the `elif` branch in Section 6.

### `tir/api/routes.py`
- Track whether retrieval ran and succeeded; pass `retrieval_attempted` to the prompt builder.
  Surface it in the debug event beside `retrieval_skipped` / `chunks_retrieved`.

### `tests/test_retrieval.py` (extend) and `tests/test_context.py` (extend)
No new test file needed; both already cover these units.

---

## Tests (plan)

- distance floor: a candidate above the threshold is dropped pre-fusion; one below survives
- BM25-only chunk with a bad/absent distance still reaches the result (the exemption)
- `_sanitize_fts5_query`: stopwords removed; content words kept; a phrase containing "the"
  still matches; an all-stopword query returns `""` and the BM25 leg is skipped
- BM25 score floor drops weak candidates and keeps strong ones
- `retrieve()` returns `[]` when nothing clears either floor (a valid outcome, already
  supported by the `if not vector_filtered and not bm25_raw` guard at `retrieval.py:350`)
- marker fires when retrieval ran and returned empty; does **not** fire on a greeting, on
  `skip_memory`, on a retrieval exception, or when chunks were returned
- `_apply_artifact_boosts` and `_artifact_match` unchanged for a surviving artifact chunk,
  including a BM25-only one
- regression: the existing retrieval tests' fixtures may assume the 0.8 default — audit and
  update any that do

## Live verification (after implementation)

Re-run both probe scripts (`scratchpad/probe_retrieval.py`, `probe_conversational.py`) and
confirm: off-topic conversational queries return 0, on-topic keep their correct top hit, and
one real chat turn with `ANAM_DEBUG_PROMPT=1` shows the marker text in the assembled prompt
for a deliberately unanswerable question.

## Open items for reviewer

1. **Confirm 0.40**, accepting the measured 0.0124 margin above the worst on-topic query.
   The alternative, 0.42, buys recall margin but admits the dentist query and both
   near-misses — i.e. it re-opens the hole this task exists to close.
2. **Approve the BM25 score floor (−9.0) as a third component.** This goes beyond decision 2
   as written. Without it the stopword fix leaves 4 of 9 off-topic queries returning ≥7
   chunks and the whole change accomplishes very little. If you would rather keep the change
   to exactly the two stated components, say so and I will scope it that way — but the
   measurement says the result will be weak.
3. **Should `memory_search` (the entity's explicit tool, `memory_search.py:24`, `max_results=5`)
   inherit the same floor?** Recommended yes, for consistency: an explicit search that finds
   nothing should say so rather than return filler. Flagging because it changes tool
   behaviour, not just automatic context.
4. **Confirm the marker wording**, and that it is a system-prompt section rather than a
   tool-result-shaped message.
5. **Threshold maintenance:** both floors are calibrated to a 255-chunk store. Worth a note in
   `DECISIONS.md` that they are empirical and need re-probing as the corpus grows.

## Out of scope

- Implementation (this is plan only).
- `_apply_artifact_boosts` itself, `has_recent_artifact_intent`, and `_artifact_match` —
  confirmed unaffected, not modified.
- The artifact backfill, the `CHROMA_DIR` isolation fix, and the orphan purge (all shipped).
- `routes.py`'s import-time `CHAT_DEBUG_TRACE_PATH` snapshot.
- The dead-code / patch-bloat cleanup.
- Any change to RRF, `max_results`, `AUTO_RETRIEVAL_RESULTS`, or the char budget.

*Plan only. No code, no commit.*
