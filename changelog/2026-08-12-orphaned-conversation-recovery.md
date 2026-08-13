# 2026-08-12 — Orphaned conversation recovery (0b6acc0e, 74641c53, 92f127b9)

## Summary

Three ended conversations were left `chunked=0` by the historical embed
over-length failures (since fixed for new data by the sub-chunk split,
`3250240`/`25682de`). They predated the fix and were never re-processed. Recovered
them by running the existing, unmodified `memory-repair` admin path — a shakedown of
`memory-repair` + the split fix on pre-wipe throwaway data. Implements
`PLAN-2026-07-04-orphaned-conversation-recovery.md`; reviewer ruled Option A on §6.
No commit.

## Mechanism (no new code)

`python -m tir.admin memory-repair` → `repair_memory_integrity()` →
`recover_unchunked_ended_conversations()` → the fixed `chunk_conversation_final()`
per conversation. No bespoke chunking/embedding logic; the over-length groups that
previously 400'd now split into sub-units and store cleanly. Idempotent via
deterministic chunk IDs + delete-before-write per `(conversation_id, chunk_index)`;
per-conversation `try/except` so one failure can't corrupt another's recovery.

## Sequence executed

1. Operator backup confirmed (gated the real run — the newest on-disk backup was
   ~1 month old, so a fresh pre-recovery backup was required and confirmed).
2. `--dry-run` (read-only) → confirmed exactly the three targets, nothing else
   (1 active conversation untouched).
3. Real run → `Attempted: 3, Succeeded: 3, Failed: 0, Chunks written: 41`.
4. Verification (below).

## Verification (per-orphan, conversation chunks)

Counts scoped to conversation chunks (`chunk_id LIKE '<cid>_chunk_%'`):

| conv | chunked | conv-chunks before (fts/chroma) | after (fts/chroma) | FTS==Chroma |
|---|---|---|---|---|
| `0b6acc0e` | 1 | 9/8 (mismatch) | 11/11 | ✓ (reconciled) |
| `74641c53` | 1 | 8/8 | 19/19 | ✓ |
| `92f127b9` | 1 | 7/7 | 11/11 | ✓ |

- No ended + `chunked=0` conversations remain (0).
- **Retrieval probes (real read path, `retrieve(query=...)`):** `0b6acc0e` →
  `"rainbow"`; `74641c53` → `"destabilization"`; `92f127b9` → `"learning"`. All three
  returned hits that surface the recovered conversation. Content is genuinely
  retrievable, not just stored.

## Provenance (Option A, as ruled)

- **Original (correct):** message timestamps inside each chunk's transcript,
  `conversation_id`, and `user_id`/attribution (all three: `9a126207`) — sourced from
  the frozen working.db rows.
- **Recovery-time (accepted caveat):** the chunk-envelope `created_at` is stamped
  `datetime.now()` by the unmodified pipeline. It is **display-only** (`context.py`
  `[Conversation — {created_at}]` header) and is **not** a retrieval-ranking input, so
  it does not affect recency/ranking — only the header date reads the recovery date;
  the transcript body shows real dates. Acceptable here because these are pre-wipe
  throwaway orphans. A backlog item was added to source `created_at` from message
  timestamps before `memory-repair` is ever run on post-launch data
  (`BACKLOG.md` → Memory / recovery).

## Reported, NOT fixed (out-of-scope historical quirks)

- **`0b6acc0e` carries an artifact event chunk (`artifact_51bcd3eb-..._event`)
  present in FTS but missing from Chroma.** This is NOT a conversation chunk and NOT a
  recovery failure — it references this conversation via `conversation_id` because the
  artifact was created during it. Its FTS-without-Chroma state is a separate artifact
  of the historical `artifact_indexing` path (the indexer that lacked the
  `_chroma_metadata` None-sanitizer, per `CODE_REVIEW_2026-06-24.md`), independent of
  the conversation orphans. `memory-repair` does not touch artifact chunks, so it
  remains. **Reported per scope; left unfixed.** (It initially made the naive
  by-`conversation_id` count read 12/11 for `0b6acc0e`; scoping to conversation chunks
  shows the actual recovery is clean at 11/11.)
- All three orphans started with partial pre-existing chunks (live checkpoints that
  succeeded before the over-length 400); "orphaned" meant `chunked=0` with
  incomplete/inconsistent indexing, not absent.

## Files changed

- `BACKLOG.md` — added the `created_at`-from-message-timestamps follow-up (Option A
  caveat; must be planned before any post-launch `memory-repair`).
- No code changed. Recovery ran through the existing admin path; the store
  (`data/prod/*`) was mutated by the recovery run itself (gitignored, not committed).

## Rollback

If needed: restore from the confirmed pre-recovery backup
(`python -m tir.admin restore <snapshot>`). Because recovery is idempotent and
per-conversation isolated, re-running `memory-repair` is the lighter remedy; full
restore is the hard fallback. Not needed — all three succeeded and verified.

## Project Anam alignment check

- Restored orphaned lived memory into the retrievable store via the existing
  pipeline, preserving content/conversation/user provenance (Invariant 4). The one
  display-only recovery-time field is documented and backlogged.
- No change to chunking, retrieval ranking, or embedding logic. No new capability,
  flag, schema, or migration. Only the three named conversations were touched; other
  historical quirks were reported, not fixed.
