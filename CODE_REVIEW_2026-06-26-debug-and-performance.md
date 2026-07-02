# Full Debug + Performance Review — Project Anam

**Date:** 2026-06-26 · **Mode:** REVIEW ONLY — ran, reviewed, documented. **No code changed.** This document is the deliverable.
**Scope:** entire `tir/` backend, `skills/`, and `frontend/src/`. Four parallel deep-dive reviews (chat hot path, data layer, startup/background jobs, frontend + runtime-bug sweep) plus direct measurement; key claims verified against source with line numbers.
**Relationship to prior docs:** complements `CODE_REVIEW_2026-06-24.md` (general bugs/cleanup) and `CODE_REVIEW_2026-06-26-retrieval-replay-vector.md` (memory replay). This one focuses on **(1) why the program runs slow** and **(2) runtime/crash-class debug findings**. Already-catalogued style/dead-code items are not repeated.

## NORTH_STAR check
Read-only audit. Aligned with the legible/inspectable-substrate principle; no invariant touched.

## What was run / verified
- **Import smoke:** `tir.api.routes, tir.engine.*, tir.memory.*` all import cleanly.
- **Test suite:** `pytest -q` → **892 passed** in ~15s. Slowest test 0.61s (no pathological test).
- **Confirmed directly in source:** chat endpoint is sync `def stream_chat` (`routes.py:425`); Ollama stream response is never closed (`ollama.py:70-83`); agent loop buffers the whole reply then replays tokens (`agent_loop.py:298-300`); 1 `time.sleep` (ComfyUI poll); ~41 `get_connection`/connect sites in `db.py`; 12 synchronous `requests` network call sites.

---

# PART 1 — Why the program runs slow (performance)

## 1.0 Anatomy of one chat turn (where the wall-clock goes)

`/api/chat/stream` (`routes.py:425`), in order: resolve user + conversation (2 DB conns) → **idle-close sweep (may run final chunking + embeddings for up to 3 *other* conversations synchronously)** → save user msg (DB) → retrieval (**1 Ollama embedding** + Chroma query + FTS) → build system prompt (reads `soul.md` + `OPERATIONAL_GUIDANCE.md` from disk) → load **full** conversation history + several O(n) passes → optional synchronous URL prefetch → **agent loop: 1–5 Ollama generations, fully buffered** → save assistant msg + **checkpoint embedding (2nd Ollama embed)** → write debug trace → **only now flush buffered tokens to the client**. The whole turn runs in **one threadpool thread** (sync endpoint).

The dominant costs are the model generation itself, **two synchronous embedding round-trips**, the **fully-buffered streaming** (no time-to-first-token), and **per-call DB connection churn**.

## 1.1 HIGH severity

### P1 — Streaming is fully buffered: the user waits for the *entire* generation before the first token
Two layers compound:
- **Agent loop is non-incremental** (`agent_loop.py:146-183` consumes the full Ollama stream into `accumulated_content`, then `agent_loop.py:298-300` replays `for content in accumulated_content: yield token`). Even though `ollama.py` sets `stream=True`, tokens are not forwarded as they arrive.
- **Routes drains then buffers** (`routes.py:834-890`) and only flushes after generation + assistant-save + checkpoint embedding + debug-trace write complete (`routes.py:1046-1051`).

**Impact:** perceived latency (time-to-first-token) ≈ time-to-**last**-token. With `gemma`-class models at `num_ctx=32768` this is the single biggest felt-latency item — seconds to tens of seconds of blank wait. **Note:** the buffering is a deliberate persist-on-disconnect design (`routes.py:825-833`); the cost is real regardless. A token-streaming design that still guarantees persistence (stream live + save in a disconnect-safe `finally`) would recover TTFT.

### P2 — Two uncached embedding round-trips per turn (blocking Ollama HTTP)
- Query embedding: `retrieve()` → `query_similar()` → `embed_text()` (`chroma.py:247`, `retrieval.py:311`) on every non-skipped turn.
- Checkpoint embedding: `checkpoint_conversation()` → `_store_chunk()` → `upsert_chunk()` → `embed_text()` of the **growing tail chunk** (`chunking.py:291,170`) after every persisted turn.

No caching anywhere; each is a blocking POST (30s timeout, `chroma.py:90-94`). The checkpoint embed re-embeds the entire current tail chunk each turn, growing until the 5-turn boundary resets it. **Impact:** 2 serial model round-trips added to every turn (one before generation, one after).

### P3 — Idle-close janitor runs heavy synchronous work *inside* the request
`routes.py:504` calls `_sweep_idle_conversations`, which for up to `_MAX_CLOSES_PER_SWEEP=3` conversations runs `close_conversation` → `chunk_conversation_final` (`chunking.py:313-396`) — **re-chunks each conversation from scratch and embeds every chunk group** (one blocking Ollama POST per chunk, 30s timeout each). A single user's send can pay final-chunking + many embedding round-trips for up to 3 *other* conversations **before its own retrieval starts**. The 120s throttle + cap bound frequency, not per-sweep latency; a slow Ollama can add tens of seconds to the triggering user's first byte. (Flagged independently by two reviews.) **Fix direction:** move close work off-thread / time-box it.

### P4 — DB connection-per-call, each opening working.db **and ATTACHing archive.db**
`get_connection()` → `_connect_working()` opens a new connection + `PRAGMA journal_mode=DELETE` + `PRAGMA foreign_keys=ON` + `ATTACH DATABASE archive` on **every** call (`db.py:31-57`), with no pooling. A single chat turn opens ~6–8 connections; the chunking path alone opens 3 per turn (`maybe_chunk_live`: `get_turn_count` + `get_conversation_messages` + `get_user`, `chunking.py:212-234`), firing after every assistant message even when no chunk is created.
- **ATTACH is the expensive part and is paid even though almost no function touches `archive.*`** — only `create_user` (`db.py:469`) and `save_message` (`db.py:760`) use it. Every read pays for an attach it never uses.
- `DELETE` journaling (chosen for cross-DB atomicity, `db.py:11-12`) makes each write fsync-heavier than WAL.

**Impact:** fixed per-call overhead × high call volume, entirely serial. Scales with call volume, not data size — i.e. it's slow *now*. **Fix direction:** connection reuse (thread-local/context-scoped) + a `attach_archive=False` variant for read-only working queries.

### P5 — `delete_chunks_by_prefix` loads **every** chunk ID in the vector store into Python
`chroma.py:200-201`: `collection.get(include=[])["ids"]` pulls all IDs, then filters by prefix in Python — to delete a handful. Called by `delete_research_chunks` (`research_indexing.py:101`) on every research-note re-index. **Impact:** O(total collection size) memory + scan regardless of matches; grows unbounded. Chroma supports metadata `where` filters (artifact_id is in metadata) — a filtered delete avoids loading all IDs.

## 1.2 MED severity

### P6 — Full conversation history reloaded and re-sent every turn (no windowing)
`get_conversation_messages` loads **all** messages (`routes.py:574`), then routes does multiple O(n) passes (`routes.py:576-606`: two `sum`, a char sum, `next` scan, reversed scan) and `build_moltbook_selection_context` JSON-parses every message's `tool_trace` (`tool_trace_context.py:86-119`). The entire `model_messages` array is sent to Ollama with no truncation. **Impact:** scales linearly with conversation length — both Python-side and, dominantly, Ollama `prompt_eval` cost growing each turn toward `num_ctx=32768`.

### P7 — Sync FastAPI endpoint holds a threadpool worker for the whole turn
`stream_chat` is `def` (`routes.py:425`), so it runs in Starlette's bounded threadpool (~40). The entire generator — all DB calls, both embeds, all generation, file writes — holds one thread for the full turn duration. **Impact:** under concurrency, long per-turn durations (P1) saturate the pool and queue new requests; tail latency degrades. Single-turn latency unaffected in isolation.

### P8 — Nightly reflection / journal: per-conversation DB fan-out
`_load_window_messages` is called **once per conversation in `_format_transcript`** (`journal.py:200`) and **again** in `build_reflection_memory_query` (`journal.py:786`), plus a separate per-conversation COUNT/MIN/MAX in `_conversation_activity` (`journal.py:359-375`) — each on its own ATTACH-ing connection. The 7 activity builders each open their own connection (`journal.py:432,484,552,633`). **Impact:** conversations × messages, doubled/tripled; batch path so not user-facing, but heavy on a mature store.

### P9 — Operational reflection duplicate-check is N+1 with a 500-row scan per candidate
`write_operational_review_items` loops candidates and calls `_candidate_is_duplicate` (`operational.py:552`), which calls `list_review_items(limit=500)` **inside the loop** (`operational.py:554`) and rescans in Python. Up to 20 candidates × 500 rows = ~10k materializations per write. **Fix:** fetch existing items once before the loop.

### P10 — ChromaDB `.count()` called twice per query; embeds not batched
`query_similar` calls `collection.count()` twice (`chroma.py:241,245`) — `.count()` scans/locks the collection; doing it twice doubles that per `retrieve()`. Separately, `upsert_chunk` embeds one chunk per Ollama call (`chroma.py:165-166`); `chunk_conversation_final` loops chunk-by-chunk (`chunking.py:366-378`) → one HTTP round-trip per chunk instead of one batched `/api/embed`. **Impact:** count scales with collection size × query volume; embed cost with chunks per conversation.

### P11 — FTS5 BM25: OR-of-every-token (incl. stopwords) + post-filter on UNINDEXED column
`_sanitize_fts5_query` ORs **all** tokens including stopwords (`retrieval.py:51-87`), inflating the candidate set; `search_bm25` then post-filters `conversation_id` which is `UNINDEXED` (`db.py:889-919,440-450`). **Impact:** scales with index size; broad OR queries pull large candidate sets that feed RRF fusion. **Fix:** drop stopwords / AND significant terms.

### P12 — `/api/health` polled every 30s per tab, unconditionally
Frontend `setInterval(fetchHealth, 30000)` (`App.jsx:377`) runs regardless of tab visibility or whether the Status panel is open; server-side `/api/health` does a **5s-timeout Ollama HTTP call + 2 SQLite COUNT(*)** per poll (`routes.py:1647-1682`), competing with the streaming threadpool. **Fix:** gate on `document.visibilityState` / panel-open.

### P13 — Audit runs COUNT then the identical SELECT (full set-ops twice)
`audit.py` runs a `COUNT(*)` over a subquery then the same subquery for IDs — four pairs (`audit.py:30/38, 50/58, 79/84, 95/106`); two are full `EXCEPT` over `messages` × `archive.messages` with no LIMIT, computed twice; one is a double FTS-join aggregation. Admin-path, but grows with message count.

## 1.3 LOW severity (perf)

- **P14** — `soul.md` + `OPERATIONAL_GUIDANCE.md` read from disk every turn (`context.py:35-52`); trivially cacheable (immutable per process). 
- **P15** — `jsonschema.validate` runs against the raw schema dict on **every** tool dispatch (`registry.py:510`) — no compiled validator cached. Repeated work on the tool path.
- **P16** — Journal date queries: full `artifacts WHERE type='journal'` scan + per-row `json.loads` to match date in Python (`journal_context.py:146-164`, `journal.py:246` similar 500-row Python filter).
- **P17** — Startup skill discovery is synchronous and unbounded: reads/parses every `SKILL.md` and `exec_module`s every skill `.py` before the server accepts traffic (`registry.py:303-415`); one heavy import stalls boot.
- **P18** — `moltbook_sources.collect_*` rebuilds the entire SkillRegistry from disk if no registry is passed (`moltbook_sources.py:504`; `bounded.py:967` defaults to None) — full skill re-import inside a research run.
- **P19** — Double file reads on write paths: research/journal register re-reads the just-written file to index it instead of reusing the in-memory string (`manual.py:673`, `journal.py:1028`).
- **P20** — `upsert_chunk_fts` does DELETE-then-INSERT per chunk with `chunk_id` UNINDEXED → the existence-DELETE scans the FTS content table, per chunk, per connection (`db.py:875-886`).
- **P21** — First chat request pays deferred Chroma client open + `collection.count()` (`chroma.py:41-53`) since it's lazy, not done at startup.

---

# PART 2 — Debug / runtime-correctness findings

## 2.1 HIGH severity

### D1 — Streaming Ollama response is never closed → socket/connection leak every chat turn
`ollama.py:70-83`: `resp = requests.post(..., stream=True)` then `for line in resp.iter_lines(): yield chunk` — **no `with`, no `try/finally`, no `resp.close()`**. The sole consumer (`agent_loop.py:146-183`) breaks on `done` without draining the body, and if the outer generator is abandoned (client disconnect / exception unwind) the response is never closed. Either way the keep-alive connection isn't returned to the pool. **Verified directly.** Under sustained chat traffic this accumulates sockets / exhausts the urllib3 pool. **Fix:** `with requests.post(...) as resp:` or `try/finally: resp.close()`. (This is the highest-value debug fix — a real recurring leak on the hot path.)

### D2 — Per-token frontend re-render + smooth-scroll storm
`Chat.jsx:619-622` (`token` handler) runs `setMessages(prev => prev.map(...))` per token → full list re-render, and the `useEffect([messages])` auto-scroll (`Chat.jsx:420-422`) fires `scrollIntoView({behavior:'smooth'})` once per token. Because the **server now flushes all tokens in a burst** (P1), the client gets many `token` lines in one/few `reader.read()` chunks → N renders + N queued smooth-scrolls back-to-back → jank. **Fix:** parse all lines in a chunk and apply one concatenated update; use `behavior:'auto'` during streaming.

## 2.2 MED severity

### D3 — Module-level mutable state mutated from concurrent request threads without a lock
`routes.py:215` `_active_generations: set`, `:222` `_last_idle_sweep_monotonic`. Since `stream_chat` is sync, requests run concurrently on threadpool threads. The throttle in `_sweep_idle_conversations` (`routes.py:231-235`) is a non-atomic read-check-then-write: two concurrent streams can both pass it and both run the close sweep on potentially the **same** candidate → duplicate final-chunking/embeddings and racing `end_conversation` writes (SQLite serializes with possible `database is locked` at `timeout=10`, DELETE journaling). Set add/discard are GIL-atomic, but the compare-and-set is not. **Fix:** a `threading.Lock` around the throttle check + sweep.

### D4 — `raw_events` debug array is O(n²) per turn
`Chat.jsx:242-340`: every debug event rebuilds `raw_events` with a spread copy AND `publishDebug` re-spreads the whole array to `setDebugData`; `DebugPanel.jsx:267` re-`stringify`s the full array on each change. Bounded per turn (reset at turn start) but a tool-heavy turn does quadratic work + re-renders the panel each event. **Fix:** cap length / don't republish the full array per event.

### D5 — Non-streaming Ollama responses also not explicitly closed
`ollama.py:107-114,138-145` (`chat_completion_json`/`_text`): lower impact than D1 (body is consumed via `.json()`, returning the connection), but on `raise_for_status()` raising (4xx/5xx) the response isn't closed. LOW-within-MED.

### D6 — Lazy Chroma init can raise on the first request thread
`chroma.py:41-53` constructs the PersistentClient lazily on first use rather than at `startup()` (`routes.py:193-200` inits only SQLite + registry). Retrieval and checkpoint are try/wrapped so a chat turn survives, but the first user pays the open latency on their request thread. Latency, not crash.

## 2.3 LOW severity

- **D7** — `current_user_index` falls back to `len(model_messages)` if the just-saved user message isn't returned by `get_conversation_messages` (`routes.py:586-606`); injected system context would then land after the user message. Defensive only; no crash.
- **D8** — ComfyUI poll does blocking `time.sleep` up to `timeout_seconds` on the threadpool thread (`comfyui.py:224-246`); image-gen path, not chat. (Also flagged in the 06-24 review re: total-timeout budget.)
- **D9** — `useIsMobile` resize handler has no debounce and re-renders the whole `App` tree on resize events (`App.jsx:107-115`).

## 2.4 Verified-correct (so they are not re-flagged)
- SQLite `get_connection()` usages are context-managed and close in `finally` (`db.py:50-57`) — no SQLite connection leaks (the cost is churn, P4, not leakage).
- `ArtifactCard` blob lifecycle is correct: `cancelled` flag + `URL.revokeObjectURL` cleanup keyed on `preview_url` (`Chat.jsx:12-33`) — no leak.
- The Option-2 drain `finally` discards `_active_generations` on all paths (`routes.py:881-886`) — disconnect-safe.
- SQLite indexes are broadly thorough; no glaring missing index on simple lookups.
- `_validate_embedding_dimension` is O(1).

---

# PART 3 — Priority summary

| # | Finding | Type | Severity | Scales with |
|---|---------|------|----------|-------------|
| P1 | Fully-buffered streaming (no TTFT) | perf | HIGH | response length |
| P2 | 2 uncached embedding round-trips/turn | perf | HIGH | per turn (checkpoint grows) |
| P3 | Idle sweep: sync embeddings in request | perf | HIGH | up to 3 convs × chunks |
| P4 | DB connection churn + needless ATTACH | perf | HIGH | call volume |
| P5 | `delete_chunks_by_prefix` loads all IDs | perf | HIGH | total vector store |
| D1 | Ollama stream never closed (leak) | bug | HIGH | every turn |
| D2 | Per-token re-render + smooth-scroll storm | bug/perf | HIGH | response length |
| P6 | Full history reloaded + re-sent (no window) | perf | MED | conversation length |
| P7 | Sync endpoint holds threadpool thread | perf | MED | concurrency × turn time |
| D3 | Concurrent idle-sweep throttle race | bug | MED | concurrency |
| P8–P13, D4–D6 | (see above) | mixed | MED | various |

## Recommended order (when changes are approved — separately)
1. **D1** — close the streaming Ollama response (`with`/`try-finally`). Smallest, highest-value: stops a real recurring leak.
2. **P1 + D2** — stream tokens incrementally (recover TTFT) and batch the frontend per-token renders / use `auto` scroll. Biggest *felt* speedup.
3. **P3** — move idle-close (final chunking + embeddings) off the request thread.
4. **P4** — connection reuse + skip ATTACH for read-only working queries.
5. **P2 + P10** — query-embedding cache, single `.count()`, batched embeds.
6. **P5** — metadata-filtered Chroma delete.
7. **D3** — lock the idle-sweep throttle.
8. **P6** — history windowing before sending to the model.
9. Remainder (P8–P21, D4–D9) as cleanup / as data grows.

*Review only. No files other than this document were created or modified. Each item lists its file:line and the reasoning so a fix can be planned and approved separately.*
