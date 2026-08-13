# PLAN — Orphaned Conversation Recovery. PLAN ONLY.

**Date:** 2026-07-04 · **Mode:** plan only. **No code, no commit.** For review before implementation.
**Targets (only these three):** `0b6acc0e`, `74641c53`, `92f127b9` — ended conversations left `chunked=0` by the historical embed over-length failures, since fixed for new data by the sub-chunk split (commits 3250240 / 25682de).

## NORTH_STAR check
Restoring orphaned lived memory into the retrievable store, using the existing (fixed) pipeline, preserving provenance. Squarely serves Invariant 4 (protect the raw/accumulated stream; provenance is sacred). No enforcement/behavior change. One provenance caveat requires a reviewer decision (§6) — surfaced, not decided unilaterally.

---

## 1. Diagnose-first: the read-only audit step (with preliminary findings)

**The recovery run MUST begin with a per-orphan read-only audit** (queries below), re-run at execution time. A preliminary read-only pass was done to ground this plan; the store is unchanged since (server stopped precondition), so these numbers should hold — but the implementer re-runs and reports fresh.

**Audit queries, per conversation** (working.db + Chroma, read-only):
- `SELECT id, user_id, started_at, ended_at, chunked, message_count FROM conversations WHERE id LIKE '<pfx>%'`
- `SELECT COUNT(*) FROM messages WHERE conversation_id = ?`
- `SELECT COUNT(*) FROM chunks_fts WHERE conversation_id = ?` (existing FTS chunk rows)
- `collection.get(where={"conversation_id": <id>}, include=[])` → count (existing Chroma chunk rows)

**Preliminary findings (do not assume all three failed identically — they did not):**

| conv | msgs | ended | chunked | FTS chunks | Chroma chunks | orphan cause |
|---|---|---|---|---|---|---|
| `0b6acc0e` | 74 | yes | 0 | **9** | **8** | over-length final-chunking 400 → left `chunked=0`; **plus an FTS/Chroma mismatch** (1 chunk in FTS, missing from Chroma — a Defect-2 "degrade, don't destroy" artifact) |
| `74641c53` | 74 | yes | 0 | 8 | 8 | over-length final-chunking 400 → `chunked=0`; partial live-checkpoint chunks present, counts matched |
| `92f127b9` | 68 | yes | 0 | 7 | 7 | over-length final-chunking 400 → `chunked=0`; partial live-checkpoint chunks present, counts matched |

**Key facts this establishes:**
- The orphans are **partially indexed, not absent** — each already has chunk rows from live checkpoints that succeeded before an over-length group 400'd; `chunked=0` because final chunking never completed.
- `0b6acc0e` is **not the same failure** as the other two: it carries a store mismatch (FTS has a chunk Chroma lacks). Recovery must (and does) reconcile this, not just fill gaps.
- Cause cross-checked against `CODE_REVIEW_2026-06-27-embed-diagnosis.md` (these exact IDs 400'd with `"input length exceeds the context length"`).
- **Scope is safe:** the *complete* set of ended + `chunked=0` conversations is exactly these three (`SELECT COUNT(*) ... WHERE ended_at IS NOT NULL AND chunked=0` → 3). So the recovery queue touches nothing else.

---

## 2. Recovery mechanism — the EXISTING admin path (no bespoke code)

**It already exists.** `python -m tir.admin memory-repair` → `tir.memory.audit.repair_memory_integrity()` → `tir.memory.chunking.recover_unchunked_ended_conversations()`:
- selects `get_unchunked_ended_conversations()` (ended + `chunked=0`) — exactly the three (§1);
- per conversation calls the **fixed** `chunk_conversation_final(conv_id, conv["user_id"])` — the same pipeline live/close use, now with sub-chunk splitting;
- supports `--dry-run` and `--limit` (via `repair_memory_integrity(limit, dry_run)`).

**No new chunking/embedding code is written.** Recovery re-runs `chunk_conversation_final`, which re-chunks each conversation from frozen messages via `_store_chunk_group` → `_split_chunk_for_embedding` → `_store_chunk` (embed + Chroma + FTS). The over-length groups that previously 400'd now split into sub-units and succeed.

**One gap that requires a reviewer decision before proceeding — see §6** (chunk `created_at` provenance). Aside from that, the pipeline runs on these historical conversations **without modification**.

Recommended invocation: `--dry-run` first (preview), then the real run.

---

## 3. Idempotency & partial-failure safety

- **Idempotent (no duplicate chunks):** `chunk_conversation_final` regenerates deterministic chunk IDs (`{conv}_chunk_{i}` / `{conv}_chunk_{i}_{j}`) from frozen messages, and `_store_chunk_group` does **delete-before-write per (conversation_id, chunk_index)** across both stores (`delete_chunk_records_by_index` = Chroma metadata-filtered delete on `(conversation_id, chunk_index)`; `delete_fts_chunk_index` = FTS delete of the bare id + `_*` sub-ids via GLOB) *before* re-writing the current shape. So re-running produces the same stored set — and this is exactly what **reconciles `0b6acc0e`'s FTS/Chroma mismatch**: the affected index is deleted from both stores and rewritten consistently. Chroma `upsert` + the FTS delete-then-insert give idempotent overwrite on top.
- **Partial-failure-safe across orphans:** `recover_unchunked_ended_conversations` wraps each conversation in its own `try/except` and only marks `chunked=1` when `chunk_conversation_final` fully succeeded (all sub-units written). A failure on orphan 2 records a failure entry and moves on — **orphan 1's completed recovery is already committed and untouched** (separate conversations, separate indices).
- **Within a conversation:** each turn-group index is delete-then-written independently; a mid-conversation failure leaves `chunked=0` (recoverable) and the successfully-written indices in place, so a re-run converges.

---

## 4. Provenance sourcing — per field

| field | source in the pipeline | original or recovery-time |
|---|---|---|
| **message timestamps in chunk text** | `_format_message_line` → `msg["timestamp"]` (per message, from working.db) | **ORIGINAL** ✓ — the transcript the entity actually reads carries the real dates |
| **conversation_id** (metadata + FTS) | passed through `conv["id"]` → `_store_chunk` | **ORIGINAL** ✓ |
| **user_id / user attribution** (metadata + FTS) | `conv["user_id"]` → `chunk_conversation_final` → `get_user(user_id)` for the display name | **ORIGINAL** ✓ (all three: `9a126207`) |
| **source_type / source_trust** | `"conversation"` / `"firsthand"` (unchanged) | correct ✓ |
| **chunk `created_at`** (metadata + FTS) | `_store_chunk` line 210: `datetime.now(timezone.utc)` | **RECOVERY-TIME** ✗ — see §6 |

Everything that determines the memory's *meaning* — the transcript timestamps, which conversation it was, and who spoke — is original. The only recovery-time field is the chunk-envelope `created_at`.

---

## 5. Verification step (after recovery)

Per orphan, prove retrieval actually surfaces the content:
1. **State:** `conversations.chunked == 1` for all three.
2. **Before/after chunk counts** (from the §1 audit, re-run): report FTS and Chroma counts per conversation; assert **FTS == Chroma** per conversation (reconciles `0b6acc0e`'s 9≠8), and counts are ≥ the pre-recovery numbers.
3. **Retrieval probe per conversation:** pick a distinctive phrase from each conversation's messages (read-only, from working.db) and run the real read path — `retrieve(query=<phrase>)` (or `memory_search`) — and assert at least one returned chunk has that `conversation_id`. This proves the recovered content is vector/FTS-retrievable, not just stored. (`0b6acc0e` is the "rainbow" conversation, so `retrieve("rainbow")` is a natural probe; the other two get a phrase chosen from their transcripts at verification time.)
4. Re-run `memory-audit` and confirm no ended+`chunked=0` conversations remain and FTS/Chroma counts match.

---

## 6. THE ONE DECISION FOR THE REVIEWER (report & stop, per requirement 2)

**The existing pipeline stamps chunk `created_at = datetime.now()` (recovery-time). It cannot be told the original timestamp without modifying chunking.** This conflicts with requirement 4 as written ("not recovery-time metadata").

Mitigating facts (so the decision is informed):
- `created_at` is used **only for display** — `context.py:304-351` renders `[Conversation — {created_at}]`. It is **NOT** a retrieval-ranking/sort input (retrieval is RRF, time-blind), so recovery-time `created_at` is a cosmetic header imperfection, **not** a ranking/recency contamination.
- The transcript inside each chunk still shows the **original** message dates, so the body is correct; only the chunk header date would read the recovery date.

**Options (reviewer chooses; I do NOT modify chunking on my own):**
- **(A) Recommended — recover via the unmodified pipeline, accept recovery-time chunk `created_at`.** Honors "reuse the existing pipeline / no chunking changes." Content, conversation, and user provenance are original; the only imperfection is a display-only header date. Document the caveat.
- **(B) Source `created_at` from the chunk's message timestamps first** (e.g. the group's last message `timestamp`). Fully satisfies requirement 4, but is an **out-of-scope chunking modification** requiring separate approval — it touches `_store_chunk`/`_store_chunk_group`/`chunk_conversation_final` and would change live behavior or need a recovery-only parameter. Per requirement 2, not done unilaterally; if chosen, it becomes its own approved change *before* recovery.

**Recommendation: A**, with the caveat documented — unless the reviewer holds requirement 4 strictly, in which case B is a prerequisite task. **Recovery does not proceed until this is ruled on.**

---

## 7. Operator preconditions (documented)
- **Server stopped** — no concurrent chat writes to working.db/Chroma/FTS during recovery (avoids racing the store while re-chunking).
- **Ollama running** with the embedding model — `chunk_conversation_final` re-embeds every chunk; recovery cannot run offline.
- **Backup taken** before implementation begins (operator already does this). Rollback depends on it (§8).
- Run **`--dry-run` first** to preview, then the real run.

## 8. Rollback statement
Recovery only *adds/overwrites* chunk rows for these three conversations (delete-before-write per index) and flips their `chunked` flag; it does not touch messages or other conversations. If anything goes wrong, **stop and restore from the pre-recovery backup** (`python -m tir.admin restore <snapshot>` — restore is gated `force=True` and copy-then-rename with rollback). Because recovery is idempotent and per-conversation isolated, the more common remedy is simply **re-running `memory-repair`** (a partial run converges on re-run); full restore is the hard fallback.

## 9. Out-of-scope quirks found — REPORTED, not fixed
- **`0b6acc0e` FTS/Chroma mismatch (9 vs 8):** a chunk exists in FTS but not Chroma — a Defect-2 "degrade, don't destroy" artifact from the original failure. Recovery reconciles it as a side effect of delete-before-write; noted so it isn't a surprise in the before/after counts.
- **All three carry partial pre-existing chunks** (from live checkpoints before the failure). "Orphaned" here = `chunked=0` with incomplete/inconsistent indexing, not absent. Relevant to reading the before/after counts (they start non-zero).
- No other ended+`chunked=0` conversations exist; no other historical quirks are in scope to fix.

## 10. Open items for the reviewer
1. **Rule on §6 (A vs B)** — this gates the whole recovery.
2. Confirm the existing `memory-repair` path (vs. a per-ID script) is acceptable given the queue is provably exactly the three.

*Plan only. No code, no commit, no recovery run.*
