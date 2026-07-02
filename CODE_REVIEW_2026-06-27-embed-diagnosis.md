# Embed / memory-loss bug — DIAGNOSIS

**Date:** 2026-06-27 · **Mode:** diagnosis only. No fix, no chunking refactor, no commit. The only code change is the observability log line in `embed_text` (changelog `2026-06-27-embed-error-body-logging.md`). Everything else here is read-only / shell. **The fix decision waits on the verbatim error body, which is not yet in hand.**

## NORTH_STAR check
Diagnosis/observability only; preserves instrumentation. Aligned, no invariant touched.

---

## TL;DR

- The persistent failure is **HTTP 400 on `/api/embed`**, on the **checkpoint / live-chunking write path** — **46** occurrences over ~7 weeks (2026-05-03 → 2026-06-25). The **404s are a one-off**: **3** occurrences in a single ~1-minute window right after a server restart on 2026-05-21, never recurred.
- Both standing hypotheses are **weakened/falsified by direct probing** of the current Ollama (0.24.0): over-length input does **not** 400 (it truncates to 200), and 404 means "model not found," not eviction.
- The log shows the 400 is **content-dependent, on the growing tail chunk**: a given chunk embeds fine while small, then 400s deterministically once it grows — while *other* chunks of the same conversation reached full size without error. So it is not a simple length threshold.
- **Data-loss mechanism confirmed:** `_store_chunk` writes Chroma first and `raise`s on embed failure (`chunking.py:177`), so the FTS5 write is never reached → a failed embed loses the chunk from **both** stores. The recovery helper is **manual-CLI-only** (never automatic), so the loss is permanent until an operator runs `memory-repair`.
- **What's missing:** the verbatim Ollama 400 body. `raise_for_status()` discarded it historically; step-1 logging (now deployed) will capture it on the next failure. **No fix proposed until then.**

---

## Step 1 — Observability line (the one permitted change)

`tir/memory/chroma.py::embed_text` now wraps `resp.raise_for_status()` and logs, before re-raising:
```
Ollama /api/embed failed: status=%s model=%s text_len=%d body=%s
```
`status` + `text_len` split the hypotheses (over-length vs other); `body` is the verbatim Ollama reason that was previously discarded. Re-raises unchanged. Tests green (32 passed). Changelog written. **Not committed.**

---

## Step 2 — Ollama environment (endpoint / model availability)

```
$ ollama --version        → ollama version is 0.24.0
$ ollama list             → nomic-embed-text:latest   0a109f422b47   274 MB   (present)
                            (also gemma4:26b/-mlx 16-17GB, qwen3.5/3.6 27b 17-19GB, mistral-small3.2 15GB)
config: OLLAMA_HOST=http://localhost:11434  EMBED_MODEL=nomic-embed-text  EXPECTED_DIM=768
```

Manual curl, known-good payload:
```
POST /api/embed {"model":"nomic-embed-text","input":"hello world"}
→ HTTP 200, keys=[model, embeddings, total_duration, load_duration, prompt_eval_count], n=1, dim=768  ✓
```

**404 shape probe** (wrong tag):
```
POST /api/embed {"model":"nomic-embed-text:doesnotexist", ...}
→ HTTP 404  {"error":"model \"nomic-embed-text:doesnotexist\" not found, try pulling it first"}
```
→ **A 404 on `/api/embed` means the model name/tag is not resolvable**, not "loaded-but-evicted." Ollama auto-loads an evicted-but-present model on demand. `nomic-embed-text` (bare → `:latest`) resolves correctly right now. **Endpoint + model: IN.**

**Over-length probe (tests the 400 hypothesis):**
```
input ~25,000 chars   → HTTP 200, dim=768, prompt_eval_count=2048
input ~250,000 chars  → HTTP 200, dim=768, prompt_eval_count=2048
input ~1,000,000 chars→ HTTP 200, dim=768, prompt_eval_count=2048
```
→ Current Ollama **silently truncates to 2048 tokens and returns 200**. **The "400 = over-length input" hypothesis is FALSIFIED on Ollama 0.24.0.** (Caveat: the historical 400s date from May–June; if production ran an *older* Ollama then, that version may have 400'd on over-length where 0.24.0 truncates. The verbatim body + version-at-failure are needed to settle this.)

---

## Step 3 — Verbatim error bodies: **PENDING (cannot fabricate)**

The historical failures in `tir.log` were logged *after* `raise_for_status()` stripped the body, so they read only `400 Client Error: Bad Request for url: .../api/embed` with **no reason**. The verbatim body is exactly what step-1 logging now captures — but only for failures occurring **after** deployment. As of this diagnosis, **no failure has yet been captured with the body.** This step remains open; the fix decision is correctly gated on it.

What we *can* state from the existing (body-less) logs is in Steps 4–5.

---

## Step 4 — Timestamp correlation (`data/prod/tir.log`, 2,860 lines, 2026-04-26 → 2026-06-26)

### 400 vs 404 split
| Status | Count | Span | Path |
|--------|-------|------|------|
| **400 Bad Request** | **46** | 2026-05-03 → 2026-06-25 (persistent) | checkpoint / live-chunking write |
| **404 Not Found** | **3** | 2026-05-21 19:11–19:12 only (one burst) | 1 retrieval + 2 chunking, then gone |

Failure sources (verbatim log prefixes):
```
20  tir.memory.chunking ERROR: ChromaDB upsert failed for <conv>_chunk_N
14  tir.api.routes      WARNING: Conversation checkpointing failed
 6  tir.memory.chunking ERROR: Failed to write chunk
 1  tir.memory.retrieval WARNING: Vector search failed, falling back to BM25 only
 1  tir.api.routes      WARNING: Live chunking failed
```
→ Memory loss is on the **write/checkpoint path**, not the read path (retrieval has a BM25 fallback; writes do not).

### The 404 cluster correlates with a RESTART, not an idle sweep
```
19:11:31  Tír API started — 14 tools loaded        ← server restart
19:11:43  ChromaDB collection ready, 43 chunks
19:11:46  Started conversation bcfded18 for Lyle
19:11:46  Vector search failed … 404 … /api/embed   ← first turn after restart
19:12:29  ChromaDB upsert failed … bcfded18_chunk_0 … 404
19:12:29  Conversation checkpointing failed … 404
```
The 404s fired on the **first turn after a server restart** and never recurred — a transient environmental state (model briefly unresolvable, e.g. Ollama also restarting / model mid-pull). **Not** tied to the idle sweep or ComfyUI.

### The 400 pattern correlates with **tail-chunk growth**, not sweeps/ComfyUI
Conversation `09c8b90f` timeline (verbatim):
```
chunk 0: checkpointed at 2,4,6,8,10 messages   → all OK
chunk 1: checkpointed at 2,4,6,8,10 messages   → all OK
chunk 2: checkpointed at 2 (OK), 4 (OK), 6 (OK), then 20:25 → 400; 20:32 → 400 (same chunk, re-embedded each turn)
chunk 3: checkpointed at 2 (OK), then 20:47 → 400; 20:50 → 400
```
- The checkpoint path re-embeds the **growing tail chunk every turn** (perf review P2). A chunk embeds fine while small, then 400s once it grows, and **keeps 400ing every subsequent turn** for that chunk until the 5-turn boundary rolls to a fresh chunk — which itself succeeds while small.
- **But it is content-dependent, not a fixed length:** chunks 0 and 1 reached the full 10 messages with no error, while chunk 2 began 400ing at 6 messages. Same conversation, same per-message size order of magnitude. So whatever triggers the 400 is in the *content* of specific message groups, not raw length alone (consistent with the over-length falsification in Step 2).

### Memory-pressure / eviction-burst story (idle sweep + ComfyUI): NOT SUPPORTED by the log
- Markers present: `idle`=32, `Closed conversation`=32, `image_generate`=38. Markers absent: `ComfyUI`/`comfyui`=0, `gemma`=0, `sweep`=0.
- The 400s sit **immediately after successful `Checkpointed conversation … chunk N` lines** during normal turns — i.e. on the per-turn checkpoint, **not** clustered around `Closed conversation` (idle-close) events or `image_generate` events.
- **Limitation:** ComfyUI activity and the chat model name (gemma) are **not logged to `tir.log` at all**, so this log cannot directly confirm or refute co-occurrence with ComfyUI renders or large gemma turns. The memory-pressure story can only be tested once the verbatim body (Step 3) shows whether the 400 is a load/memory error vs an input error — another reason the fix waits on the body.

---

## Step 5 — Is `recover_unchunked_ended_conversations` wired? (caller grep, verified against code)

```
$ grep -rn recover_unchunked_ended_conversations tir/ skills/ tests/
tir/memory/chunking.py:399  def recover_unchunked_ended_conversations(...)   ← definition
tir/memory/audit.py:198     summary = chunking.recover_unchunked_ended_conversations(limit=limit)   ← only caller
tests/test_chunking.py:176,202,225                                            ← tests
tests/test_memory_audit.py:156,173                                            ← tests
```
Its only caller is `audit.py::repair_memory_integrity` (audit.py:175). Tracing *that*:
```
$ grep -rn repair_memory_integrity tir/ …
tir/admin.py:524   cmd_memory_repair → repair_memory_integrity(limit=…, dry_run=…)   ← only non-test caller
tir/admin.py:1513/1974  CLI subcommand "memory-repair"
```
**Confirmed against code (not the changelog):** recovery runs **only** via the manual `python -m tir.admin memory-repair` CLI. It is **not** invoked by any request path (`routes.py`), the scheduler (`nightly.py`), or any API endpoint — **it never runs automatically.** So a conversation whose chunk embed 400s stays `chunked=0` indefinitely; nothing retries it, and final-chunking-at-close re-embeds the *same* failing text so it 400s again. The memory is lost unless an operator manually runs `memory-repair`.

---

## Mechanism of memory loss (confirmed)

`tir/memory/chunking.py::_store_chunk` (lines 168–191):
```python
# ChromaDB (vector) — primary store
try:
    upsert_chunk(...)            # ← embeds; raises on 400/404
except Exception as e:
    logger.error("ChromaDB upsert failed for %s: %s", chunk_id, e)
    raise                        # ← "Can't proceed without vector storage"
# FTS5 (lexical) — secondary store   ← NEVER REACHED on embed failure
upsert_chunk_fts(...)
```
Because Chroma is written first and the embed failure re-raises, the **FTS5 write is skipped**. A failed embed therefore drops the chunk from **both** the vector store and the lexical index — the turn group becomes wholly unsearchable. Combined with Step 5 (no automatic recovery), this is the memory-loss path.

---

## Hypothesis status after diagnosis

| Hypothesis | Status |
|---|---|
| "400 = empty chunk" (handoff) | **Refuted** — `embed_text` guards empty/whitespace before POST (`chroma.py:87-88`). |
| "400 = over-length input vs nomic context limit" | **Falsified on Ollama 0.24.0** (truncates → 200). Possible only if production ran an older Ollama at failure time. Content-dependent pattern (chunk 2 fails at 6 msgs while chunk 0/1 fine at 10) argues against pure length. |
| "404 = model eviction / not loaded" | **Weakened** — 404 = name-not-found; evicted models auto-load. The 3 404s correlate with a **restart**, not eviction, and never recurred. |
| "idle-sweep burst clusters the failures" | **Not supported** by log timestamps (400s are per-turn checkpoint, not at `Closed conversation`); ComfyUI/gemma not logged, so untestable from this log. |
| **Surviving lead:** content-specific 400 on the growing tail chunk (e.g. a token/character pattern the embed endpoint or the then-current Ollama version rejected) | **Open — needs the verbatim body** now being captured. |

## What's needed next (no fix proposed yet)
1. **The verbatim 400 body** from the next live failure (step-1 logging is deployed). That single string decides input-error vs load/memory-error and selects the fix.
2. The **Ollama version that was running at the historical failure times** (to know whether over-length 400s were a since-fixed version behavior).
3. Once the body is known: decide the fix (e.g. cap/normalize chunk text before embed, and/or wire recovery into an automatic path). **Deliberately deferred.**

*Diagnosis only. The single behavior-adjacent change is the observability log line; it is uncommitted and reversible. No fix applied.*

---

# ADDENDUM (2026-06-27, later) — REPRODUCED from on-disk chunks. Root cause confirmed.

**Outcome: the 400 reproduces deterministically on current Ollama 0.24.0. Verbatim body:**
```
{"error":"the input length exceeds the context length"}
```
**It is genuine over-length (token count exceeds nomic-embed-text's ~2048 context), NOT a control character or invalid UTF-8.** My earlier Step-2 "over-length falsified" conclusion was **wrong** — see the reconciliation below.

## Repro recipe (deterministic, no waiting for a live failure)

The originally-cited conversation `09c8b90f` has been **wiped** (0 rows in both working.db and archive.db — a reset since 2026-05-06), so it can't be reconstructed. Instead I used the **recent failing conversations still on disk** (verified present in both DBs), reconstructing each chunk exactly as the checkpoint path does:

`messages = get_conversation_messages(conv)` → `_assign_messages_to_chunks(messages)` → for each group `_format_chunk_text(group, user["name"])` → `embed_text(text)` against current Ollama. (`user_name` resolved via `get_user(user_id)` where `user_id` came from `archive.messages`.)

Result per conversation (HTTP status of embedding each reconstructed chunk):

| conv | chunks (sizes) | failures |
|------|----------------|----------|
| `6428649f` (most recent 400, 06-25 18:41) | 5 chunks [10,10,10,10,6] | **chunk 1 (11,488 chars) → 400** |
| `0b6acc0e` (rainbow) | 8 chunks | **chunk 1 (8,895 chars) → 400** |
| `74641c53` | 8 chunks | **chunks 1,4,5,6 (9,184–12,061 chars) → 400** |
| `92f127b9` | 7 chunks | **chunk 4 (9,500 chars) → 400** |

Every failing chunk returned the identical body above. Pattern: chunks **≳ 8,000–9,000 chars (≈2,048 tokens) → 400; smaller chunks → 200**. This is reproducible *now*, so the bug is **current on Ollama 0.24.0**, not a since-fixed version quirk.

## Bisect — kills the control-character hypothesis

Taking the worst case (`6428649f` chunk 1, 11,488 chars → 400):
```
len=11488 -> 400
  halves: first(5744)->200   second(5744)->200
  -> neither half 400s: cumulative LENGTH, no localized bad span
```
Both halves embed fine. There is **no offending byte span** to isolate or `hexdump` — the failure is purely cumulative length crossing the context window. The "control character / invalid-UTF-8 before truncation" hypothesis is **killed**.

## Reconciliation — why Step 2 wrongly showed "200 at 1M chars"

| input | result |
|-------|--------|
| `"word "*5000` (25,000 chars, one repeated token) | **200**, `prompt_eval_count=2048` (handled/truncated) |
| real chunk text (11,488 chars), `truncate` default | **400** "input length exceeds the context length" |
| same text, `truncate=true` | **400** (truncation does **not** save it) |
| same text, `truncate=false` | **400** |

My Step-2 probe used a pathologically repetitive single-token string, which Ollama handled (returned 200 at 2048 prompt-eval). **Real, varied chunk text over ~2048 tokens deterministically 400s**, and **passing `truncate=true` does not prevent it** on 0.24.0 — so the app cannot rely on Ollama-side truncation. I'm correcting the earlier record: over-length is the cause, confirmed by verbatim body + reproduction.

## Why the log looked "content-dependent, not length-gated"

It *is* length — but length **per chunk varies with message verbosity, not message count**. A 10-message chunk ranges from ~2,200 to ~12,000 chars depending on how long the turns are (long assistant replies, pasted artifact provenance blocks, code). So terse 10-message chunks embed fine while verbose ones cross ~2,048 tokens and 400. That fully explains the earlier observation that "chunk 2 failed while chunks 0–1 succeeded at the same message count" — same count, different char/token length.

## Confirmed end-to-end picture

1. Conversation chunk text exceeds nomic-embed-text's ~2,048-token context → Ollama 0.24.0 returns **400 `{"error":"the input length exceeds the context length"}`** (truncate flag does not help).
2. `_store_chunk` writes Chroma first and re-raises on that 400 (`chunking.py:177`) → the FTS5 write is skipped → the chunk is lost from **both** stores.
3. The growing tail chunk is re-embedded every turn; once it crosses the limit it 400s on every subsequent checkpoint and at final-close (same text) → the chunk never lands.
4. Recovery is **manual-CLI-only** (`memory-repair`); nothing retries automatically → memory loss is permanent for verbose chunks.

This is a **current, ongoing** memory-loss path affecting long/verbose turns — confirmed by reproducing it against real on-disk conversations, not a historical artifact.

## Hypothesis status (final)

| Hypothesis | Status |
|---|---|
| 400 = empty chunk | Refuted (guard). |
| 400 = over-length vs nomic context | **CONFIRMED** — verbatim body, reproduced on 0.24.0; `truncate=true` does not help. |
| control char / invalid UTF-8 | **Killed** by bisect (both halves pass; cumulative length). |
| 404 = eviction | Weakened (one post-restart burst; name-not-found shape). |
| idle-sweep / ComfyUI clustering | Not supported (failures are per-turn checkpoints on over-length chunks). |

## Not done (deferred, per scope)
- **No fix.** The cause is known (over-context chunk text + truncate-doesn't-help + Chroma-first-raises + manual-only recovery). Fix options exist (e.g. pre-embed length cap/sub-chunking, send `truncate` differently, reorder FTS-before-Chroma, auto-wire recovery) but are **deliberately not designed or applied here** — bringing it back for review.
- **No recovery run** on the orphaned `chunked=0` conversations (still on disk: `6428649f`, `0b6acc0e`, `74641c53`, `92f127b9`, `bcfded18`).

*Reproduction was a throwaway REPL (heredoc); nothing in `tir/` changed beyond the Step-1 log line. No commit.*
