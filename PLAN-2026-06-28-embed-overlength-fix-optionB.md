# PLAN — Embed over-length fix (Option B: sub-chunk splitting). PLAN ONLY.

**Date:** 2026-06-28 · **Mode:** read + plan only. **No code changed, no commit.** Costs the approach before approval.
**Pairs with:** `CODE_REVIEW_2026-06-27-embed-diagnosis.md` (root cause confirmed: turn-sized chunks can exceed nomic's ~2048-token context → deterministic `400 {"error":"the input length exceeds the context length"}` → chunk dropped from both stores, no retry; `truncate=true` does **not** help, so the app must size the input itself).

## NORTH_STAR check
A correctness/integrity fix for memory persistence (Invariant 4: the entity's experienced stream must actually be retained). KISS-preserving (no new always-on mechanism, no schema rewrite). Aligned.

---

## STEP 1 — Idempotency answer (front and center)

> **Q: Does introducing sub-chunks (`{conv}_chunk_{N}_{j}`) break the deterministic-ID / idempotent re-chunk-from-scratch property that `chunk_conversation_final` relies on?**

**A: No — re-chunk-from-scratch idempotency is preserved, provided two conditions hold. There is one *separate* hazard on the live/checkpoint path (not the re-chunk property) that the plan handles explicitly. The recommendation stands; we do not need to stop.**

`chunk_conversation_final` (`chunking.py:336-396`) regenerates IDs as `{conv}_chunk_{i}` from the turn-group index `i`, and relies on: same messages → same groups → same IDs → `upsert` overwrites identical content = no-op. Sub-chunking keeps this **iff**:

1. **The split is a pure deterministic function of the fixed group content.** Split the group's *message list* into the minimal contiguous runs that each fit the budget (deterministic greedy); hard-split any single over-budget message by a fixed char rule. For a **closed** conversation the messages are frozen → identical sub-units → identical IDs → no-op upsert. ✓
2. **Unsplit chunks keep their existing bare ID `{conv}_chunk_{i}`** (no suffix). Only over-budget chunks gain `_{j}` suffixes. So the boundaries *and* IDs of normally-sized chunks do not move, and the existing stored corpus needs **no migration/re-embed**. ✓

Under (1)+(2), the property `chunk_conversation_final` depends on is intact: re-running it over a fixed conversation is a byte-identical no-op.

**Two things that must change alongside it (or idempotency/marking breaks):**

- **The completion gate.** `chunk_conversation_final` marks the conversation chunked only when `chunks_written == intended_chunk_count`, where `intended_chunk_count = len(chunk_groups)` (turn-groups) — `chunking.py:355,383`. With splitting, stored **sub-units ≥ groups**, so this equality must be redefined in terms of **stored sub-units**, or any conversation containing a split would never be marked chunked. (Mechanical change; flagged so it isn't missed.)

- **Live-tail orphan hazard (this is convergence, NOT the re-chunk property).** On the live/checkpoint path the *same* group index `i` is rewritten every turn as the tail grows (`checkpoint_conversation` re-embeds the tail group; `chunking.py:276-298`). If group `i` crosses the split threshold between writes — was 1 unit `_chunk_i`, becomes 2 units `_chunk_i_0/_1` — the earlier `_chunk_i` record is no longer overwritten and becomes a **stale orphan** (`upsert` never deletes). Handle by making each group-write **authoritative for its index**: before writing group `i`'s sub-units, delete the stale IDs for that index — the bare `_chunk_i` (if now split) and any `_chunk_i_j` with `j ≥` the new sub-count. These IDs are **computed deterministically** (no full-store scan — avoids the P5 `delete_chunks_by_prefix` cost). Final chunking, rewriting every index authoritatively, then also cleans up any orphans live chunking left.

**Bottom line:** keep `_chunk_i` for unsplit, deterministic message-run split for over-budget, authoritative per-index delete-before-write, and a sub-unit-based completion gate → idempotent and convergent. **Proceed.**

---

## CONSTRAINT (held)
Turn-based grouping is **unchanged**. `_assign_messages_to_chunks` and `CHUNK_TURN_SIZE=5` stay exactly as-is. The only new behavior: when a *formed* group's text exceeds a safe token budget, that group's text is split into embed-sized sub-units. Boundaries for normally-sized groups do not move. This is **not** token-based chunking — it's a post-grouping safety split.

---

## DEFECT 1 — Sub-chunk splitting (the actual fix)

### Budget
- Empirically (diagnosis repro): ~8,637 chars embedded (200) but ~8,895 chars failed (400) → threshold ≈ 2,048 tokens, and char↔token density varies. **`truncate=true` does not prevent the 400**, so the app must size input below the limit with headroom.
- **Repurpose the existing dead `EMBED_MAX_CHARS` (`config.py:249`, currently `8000`, zero references) — but lower it.** 8000 is unsafe (failures seen at ~8,900; 8,637 passed by luck). Recommend a conservative budget with headroom: target ≈ **1,800 tokens**. For KISS v1 a char proxy (`EMBED_MAX_CHARS ≈ 6,000`, configurable) is adequate and deterministic; flag that a true token count (Ollama tokenize call or a local tokenizer) is more accurate but adds a dependency/round-trip — **open decision** (recommend char proxy first, revisit only if a chunk near the boundary still 400s).

### Split method (no content lost)
1. Format the group as today. If under budget → store as `{conv}_chunk_{i}` (unchanged path).
2. If over budget → split the group's **ordered message list** greedily into contiguous runs whose formatted text each fits the budget. Format each run with `_format_chunk_text` (timestamps/speaker preserved). No message reordering, no dropping.
3. **Edge case:** a single message whose formatted line alone exceeds budget (huge pasted block / long assistant turn / artifact provenance text) → hard-split that one message's text into deterministic fixed-size windows, each its own sub-unit. Still deterministic; nothing dropped.

### Sub-chunk IDs & metadata
- IDs: unsplit → `{conv}_chunk_{i}` (bare, unchanged). Split → `{conv}_chunk_{i}_{j}`, `j = 0..k-1`.
- Metadata: keep `chunk_index = i` for all sub-units of group `i`; add `sub_index = j` (and optionally `sub_count = k`). `message_count` becomes the sub-unit's message count.

### Retrieval treatment (transparent — verified)
- RRF fusion dedups on `chunk_id` (`retrieval.py:216,229`); nothing dedups on `(conversation_id, chunk_index)`. Sub-units are distinct `chunk_id`s → simply more retrievable units. **No retrieval change required.**
- Audit counts (`fts_chunk_count` vs `chroma_chunk_count`, `chunked_*_missing_fts`) stay consistent because each sub-unit writes one FTS row + one Chroma row. ✓

---

## DEFECT 2 — Embed-failure guard (stop silent destroy-from-both-stores)

**Current:** `_store_chunk` (`chunking.py:168-191`) writes Chroma **first** and `raise`s on embed failure (line 177) → the FTS write (line 180) is **never reached** → an embed failure drops the chunk from **both** stores.

**Minimal change:** do not let an embed/Chroma failure skip the FTS write. Attempt the FTS (lexical) write regardless of the embed outcome, and signal the result to the caller instead of raising before FTS. Net effect: an embed failure degrades to **"vector-missing but lexically searchable"** rather than total loss — and retrieval already fuses FTS+vector, so the memory remains findable by keyword.

**Partial-store IS a new state to handle (flagged):**
- New state: a chunk present in FTS but absent from Chroma (or vice-versa).
- Completion gate must treat partial-store as **not fully chunked** → leave the conversation `chunked=0` so recovery re-attempts the vector side (do **not** mark chunked on a partial write — otherwise the gap is masked).
- Audit: add a "chunked-but-missing-Chroma" check mirroring the existing `chunked_conversations_missing_fts_chunk_ids` (`audit.py:170`). **Follow-up, not required for the core fix.**
- Note: with Defect 1 in place, embed failures should essentially stop for normal content; Defect 2 is the safety net for genuinely anomalous inputs / Ollama being down / dimension mismatch.

---

## RECOVERY SEQUENCING (do NOT run now — just sequenced)

Confirmed status of the orphaned conversations (working.db `conversations`):

| conv | ended_at | chunked | recovery action |
|------|----------|---------|-----------------|
| `0b6acc0e` | ended 2026-06-25 | **0** | recovery target (ended + unchunked) |
| `74641c53` | ended 2026-06-25 | **0** | recovery target |
| `92f127b9` | ended 2026-06-23 | **0** | recovery target |
| `6428649f` | **open (None)** | 0 | **not** a recovery target (recovery handles *ended* unchunked); self-heals on its next checkpoint/close after the fix, or via recovery once it ends |
| `bcfded18` | ended 2026-06-25 | **1** | already chunked (its 404 was the transient post-restart blip, later resolved) — no action |

**Order (mandatory):**
1. Land Defect 1 (+ Defect 2). 
2. **Then** run recovery for the ended+`chunked=0` set (`0b6acc0e`, `74641c53`, `92f127b9`) — `chunk_conversation_final` now re-chunks them at safe sub-sizes and succeeds. `6428649f` will chunk on its next close/checkpoint post-fix.
3. **Running recovery before the fix is pointless** — it re-embeds the same oversized text and 400s again, leaving them `chunked=0`. (Separately: recovery itself is **manual-CLI-only** — `memory-repair`; nothing auto-invokes it. Deciding whether to auto-wire recovery is a **separate** scope item, not part of this fix.)

---

## Cost / blast radius

- **Files:** `tir/memory/chunking.py` (split helper + authoritative per-index store + completion-gate change + FTS-guard reorder), `tir/config.py` (lower/rename the budget constant). Optional follow-ups: `tir/memory/db.py` (a deterministic delete-by-ids helper if not already trivial), `tir/memory/audit.py` (partial-store check).
- **No migration / no re-embed of existing chunks** (unsplit IDs unchanged). Existing corpus untouched.
- **Tests to add:** over-budget group splits deterministically; re-running final chunking on a split conversation is a no-op (idempotency); single-giant-message hard-split; completion-gate marks chunked by sub-unit count; live-tail crossing the threshold cleans up the bare `_chunk_i` orphan; embed failure still writes FTS and leaves `chunked=0`; recovery re-embeds a previously-400ing conversation successfully at safe size.
- **Risk:** low-medium. The live-tail orphan cleanup and the completion-gate redefinition are the two places a careless implementation regresses idempotency — called out above so they're explicit.

## Open decisions for approval
1. **Budget unit:** char proxy (`EMBED_MAX_CHARS ≈ 6000`, KISS) vs real token count (accurate, adds a tokenize call/dep). Recommend char proxy first.
2. **Defect 2 marking policy:** treat partial-store as not-chunked (recommended, safe, recoverable) vs mark-chunked-and-backfill. 
3. **Auto-wire recovery** (separate item): leave manual `memory-repair`, or invoke recovery on a schedule / at startup. Out of scope for this fix; noted.

*Plan only. No code changed, no commit, no recovery run.*
