# 2026-06-28 — Embed over-length fix: sub-chunk splitting + degrade-don't-destroy (Option B)

## Summary

Conversation chunks sized by turn count could exceed nomic-embed-text's ~2048-token
context, producing a deterministic Ollama `400 {"error":"the input length exceeds
the context length"}` that dropped the chunk from **both** Chroma and FTS with no
retry (`truncate=true` does not prevent it — confirmed in diagnosis). This implements
the approved Option B:

- **Defect 1 — oversized chunks:** when a *formed* turn-group's text exceeds a safe
  char budget, split that group's text into embed-sized sub-units (turn-based
  grouping is unchanged — this is a post-grouping split only).
- **Defect 2 — silent destroy-on-failure:** if the vector write still fails, write
  FTS anyway (degrade to lexically-searchable) and leave the conversation
  `chunked=0` (recoverable) instead of losing it from both stores.

## Commit structure — recommendation: ONE commit

Defect 1 and Defect 2 converge on the same write path (`_store_chunk` and the new
`_store_chunk_group`) and are one logical fix to "embedding can silently lose
memory." Defect 2 is the safety net that makes Defect 1 robust (if a sub-unit is
still somehow over budget, or Ollama is down, degrade-don't-destroy catches it).
Splitting them would create an incoherent intermediate state (split-but-still-
destroys, or degrades-but-still-oversized) and they share the same new tests and
fixture. **Recommend committing together as one commit.**

## What changed

- `tir/config.py` — repurposed the previously-dead `EMBED_MAX_CHARS` constant as the
  per-embed char budget, set to **5000** (conservative proxy for ~2048 tokens; 400s
  were seen at ~8900 chars on prose, dense content runs denser, so 5000 buys
  headroom). Commented; token-counting flagged as a post-launch follow-up only if
  slip-throughs appear (no tokenizer dependency added).
- `tir/memory/chunking.py`:
  - `_format_message_line` (extracted) + `_hard_split_text` (str/codepoint-space
    slicing — explicitly never byte-slicing, so multibyte chars aren't corrupted).
  - `_split_chunk_for_embedding` — splits a group into sub-units, **preferring whole-
    message boundaries**; only hard-splits a single message that alone exceeds budget.
    Lossless (concatenation reproduces the group). Removed the now-unused
    `_format_chunk_text` (superseded).
  - `_store_chunk_group` — computes sub-units, performs **delete-before-write** for
    `(conversation_id, chunk_index)` across both stores (convergence/idempotency),
    then writes each sub-unit; returns `(intended, written)`.
  - `_store_chunk` (Defect 2) — on vector-write failure, still attempt the FTS write,
    then re-raise so the caller leaves the conversation recoverable.
  - `maybe_chunk_live`, `checkpoint_conversation`, `chunk_conversation_final` rewired
    through `_store_chunk_group`; the completion gate now compares **stored sub-units**
    (not turn-groups), so a split conversation can reach `chunked=1`.
- `tir/memory/chroma.py` — `delete_chunk_records_by_index(conversation_id, chunk_index)`:
  metadata-filtered Chroma delete (exact, no full-store scan, no need to recompute the
  old split shape).
- `tir/memory/db.py` — `delete_fts_chunk_index(conversation_id, chunk_index)`: FTS delete
  of the bare `{conv}_chunk_{i}` + GLOB `{conv}_chunk_{i}_*` sub-units (GLOB treats `_`
  literally, unlike LIKE).
- `tir/memory/audit.py` — note marking the partial-store ("chunked-but-missing-Chroma")
  audit check as a deliberate follow-up hook (not built here).
- `tests/test_chunking.py` — fixture now uses a temp Chroma dir; added 6 tests (below).

## ID scheme & idempotency (per plan Conditions 1/2)

- Unsplit groups keep the **bare** `{conv}_chunk_{i}` ID → **no migration/re-embed of
  the existing corpus**, boundaries unchanged.
- Over-budget groups become `{conv}_chunk_{i}_{j}`, a deterministic function of frozen
  content → re-chunk-from-scratch reproduces the same stored set.
- Delete-before-write makes each group-write authoritative for its index, so a growing
  live tail that crosses the split threshold (`_chunk_i` → `_chunk_i_0/_1`) leaves no
  orphan. (Mechanism stated in code comments.)
- Retrieval is transparent: RRF fusion dedups on `chunk_id`; sub-units are just more
  retrievable units (no retrieval change).

## Behavior changed

- Over-budget conversation chunks now embed + store as multiple sub-units instead of
  400ing and being lost.
- A vector-write failure now leaves the chunk in FTS (lexically searchable) and the
  conversation `chunked=0` (recoverable), instead of dropping it from both stores.
- Split conversations reach `chunked=1` on success.

## Tests / checks run

- `tests/test_chunking.py` → 15 passed (9 existing unchanged + 6 new):
  (a) over-budget chunk splits; all sub-units embed + store in both stores, each ≤ budget;
  (b) a split conversation reaches `chunked=1`;
  (c) re-chunk-from-scratch of a split conversation is idempotent (same IDs, no
  orphans/dupes); plus a live-tail threshold-crossing test (bare id removed, no orphan);
  (d) embed failure leaves FTS written + conversation `chunked=0` (Defect 2 degrade);
  (e) a multibyte (emoji) message at the split boundary is not corrupted and is lossless.
- Full suite: **898 passed**.
- Import smoke: `tir.memory.chunking` / `chroma` / `db` import clean.

## Known limitations / follow-ups (separate tasks)

- **No recovery run in this task.** The orphaned `chunked=0` conversations
  (`0b6acc0e`, `74641c53`, `92f127b9`; `6428649f` still open; `bcfded18` already
  `chunked=1`) are recovered in a **separate** next task — running recovery before this
  fix would just 400 again. Recovery remains manual-CLI-only this commit.
- Budget is a char proxy; token-counting only if slip-throughs appear.
- Partial-store audit check is a flagged hook, not built.

## Project Anam alignment check

- Did not name the entity; no personality; no Anam/Tír naming.
- **Serves Invariant 4 (provenance/memory integrity):** the entity's experienced
  stream is actually retained instead of silently dropped.
- Turn-based grouping unchanged (no conversion to token-based chunking). Additive,
  scoped to the chunk write path. No schema change / migration. No new dependency.
- Existing corpus untouched (unsplit IDs unchanged).
