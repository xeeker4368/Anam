# PLAN — Stop the test suite writing into the production store. PLAN ONLY.

**Date:** 2026-08-16 · **Mode:** plan only. **No code, no commit.** Every claim below was
measured against an isolated copy of the tree; the production store was not written to at any
point during this investigation (verified: chroma 305 / fts 255 / chat_debug 515 lines, before
and after).

**Task source:** `ACTIVE_TASK.md` — close the `CHROMA_DIR` leak found while implementing
`PLAN-2026-08-15-artifact-backfill.md`.

---

## NORTH_STAR check

Test runs are silently injecting records that were never anyone's experience into the entity's
memory store. That is a direct Invariant 4 violation (provenance is sacred; never silently
mutate the store) — arguably the purest one available, since the polluting records are fictional
by construction. The fix is a path-resolution correction plus a guard; it grants no capability,
seeds no content, and is a no-op for the running system. **Aligned.**

---

## 0. Headline findings — two corrections to the task brief

### (a) The task's proposed fix (a) does not work. Measured, not argued.

`ACTIVE_TASK.md` proposes resolving the path "inside the function body
(`chroma_path = chroma_path or CHROMA_DIR`, reading the module global at call time)" and asks
which option makes `tir.config.CHROMA_DIR` patching work as the 19 existing fixtures assume.
**Answer: neither option as written.**

`tir/memory/chroma.py:20` does `from tir.config import CHROMA_DIR`, which creates a *separate
binding* in the chroma module's namespace. Patching `tir.config.CHROMA_DIR` never touches it:

```
config.CHROMA_DIR   -> /tmp/ISOLATED          (patched)
chroma.CHROMA_DIR   -> …/data/prod/chromadb   <-- unchanged
upsert_chunk default-> …/data/prod/chromadb   <-- unchanged
after importlib.reload(chroma): both -> /tmp/ISOLATED
```

Moving the constant out of the default argument and into the body changes *when* it is read but
not *what* it reads — still `tir.memory.chroma.CHROMA_DIR`, still requiring a reload. The variant
that actually works is importing the **module**, not the value:

```python
from tir import config
...
chroma_path = chroma_path or config.CHROMA_DIR   # verified: honours patch("tir.config.CHROMA_DIR"), no reload
```

Call this **(a′)**. It is the only option that makes the 19 existing fixtures' assumption true.

### (b) The real mechanism is first-import-wins, not merely default-argument binding.

The default argument is evaluated when `tir.memory.chroma` is **first imported**, and whether
that happens inside or outside a fixture's patch window decides everything:

| run | when chroma is first imported | leak |
|---|---|---|
| `pytest tests/test_image_generation.py` alone | inside the fixture body (`import tir.memory.chroma as chroma_mod`), i.e. **inside** the `monkeypatch` window → default binds to `tmp_path` | **none** |
| full suite | pytest imports every test module at collection time first; 8 `tir` modules (`retrieval`, `routes`, `chunking`, `artifact_indexing`, `audit`, `journal_indexing`, `research_indexing`, `ops/status`) import chroma at top level → default binds to the **real** path before any fixture runs | **2 chunks** |

**Consequence for whoever verifies this:** running the suspect file on its own does **not**
reproduce the leak. Only a full-suite run does. I lost time to this, and any future check that
"the leak is gone" must be a full-suite run against an isolated tree, never a single file.

(It is also mildly Heisenbuggy: adding an instrumenting `conftest.py` that imports chroma early
makes the single-file run leak too, because the conftest import moves the first-import outside
the patch window.)

---

## 1. Q1 — Which fix. **(a′), plus a cache fix.**

- **(a′) `from tir import config`, resolve at call time** — applies to every function in
  `chroma.py` carrying `chroma_path`: `_get_collection` (41), `upsert_chunk` (155),
  `delete_chunk_records_by_index` (194), `delete_chunks_by_prefix` (220), `query_similar` (251),
  `get_collection_count` (307), `empty_collection` (313).
  **Blast radius:** production callers all rely on the default and `tir.config.CHROMA_DIR` is
  never mutated at runtime, so behaviour is byte-identical in production — the only change is
  *when* the string is read. Everything else in the module (`EMBED_MODEL`, `OLLAMA_HOST`,
  `EXPECTED_EMBEDDING_DIM`) keeps its current import style unless the reviewer widens scope
  (see §Open items 4).
- **(b) reload in fixtures** — rejected as the primary fix. It leaves the trap armed for the next
  fixture, and it does not make the 19 existing fixtures correct; they would each need editing.
- **Second, independent defect: the collection cache ignores its argument.**
  `_get_collection` returns the cached `_collection` whenever it is non-`None`, so `chroma_path`
  is silently discarded after the first call. Today fixtures paper over this with
  `reset_client()`; a fixture that forgets writes into *another test's* collection. Recommended
  sub-fix: remember the bound path and rebind when a different one is requested. Production uses
  exactly one path, so this too is a production no-op.

**No test files need to change.** `test_image_generation.py`'s fixture already patches
`tir.config.CHROMA_DIR` and already calls `reset_client()`; under (a′) its writes land in
`tmp_path` automatically. That is the argument for (a′) over (b) in one line: it fixes 19
fixtures by fixing one module.

## 2. Q2 — The guard. **New `tests/conftest.py`, fail-loud.**

There is currently no project `conftest.py` anywhere (only inside site-packages). `pytest.ini`
sets `testpaths = tests`, so `tests/conftest.py` is auto-loaded before any test module — the
right hook point.

Options considered:

| option | behaviour | cost |
|---|---|---|
| **fail-loud (recommended)** | session-scoped autouse fixture wraps `chromadb.PersistentClient`; raises if the resolved path is the real `CHROMA_DIR` | one new file; surfaces the bug instead of hiding it |
| redirect | session fixture points `CHROMA_DIR` at a session tmp dir | cheap, but converts a loud bug into a silent one — rejected on the same grounds as the original defect |
| both | redirect + assert | belt and braces; more machinery than a two-write leak warrants |

`chromadb.PersistentClient` is constructed in exactly two places (`chroma.py:45` and
`chroma.py:323`), so wrapping the constructor covers both. The guard does not disturb
`test_chroma.py` or `test_artifact_backfill.py`, which replace `_get_collection` outright and
never construct a client. Same guard shape should cover the `chat_debug.jsonl` path (§3).

**Sequencing matters:** land (a′) first, then the guard. Guard-first turns the two known leak
sites into hard failures before the fix that resolves them exists.

## 3. Q3 — Full leak inventory. **Measured. Exactly two surfaces.**

Method: copied `tir/ tests/ config/ skills/ probe/ scripts/ pytest.ini run_server.py` plus the
governance `.md` files into a scratch tree with an **empty** `data/prod`, confirmed
`PROJECT_ROOT` resolved into the copy, and ran the full suite there. Anything appearing under
`data/prod` is by definition a leak. Production was never a target.

Full-suite result (reproduced twice, 937 passed / 1 failed — the single failure is
`test_prompt_inventory`, an artifact of not copying `docs/`, not a real failure):

| surface | leaked per run | detail |
|---|---|---|
| `data/prod/chromadb/` | **2 documents** | `artifact_<uuid>_event`, `title=fake-output.png` |
| `data/prod/chat_debug.jsonl` | **7 lines** | all `conversation_id="conv-1"` |
| `data/prod/working.db`, `archive.db` | **0** | SQLite isolation works — `reload(db_mod)` re-executes the `from tir.config import` line |
| `workspace/`, `backups/` | **0** | nothing written |

Attribution by stack-trace instrumentation (throwaway conftest in the scratch copy only) — the
two Chroma writes come from exactly the two tests predicted statically:

- `tests/test_image_generation.py::test_missing_dimensions_and_seed_resolve_to_concrete_integers`
- `tests/test_image_generation.py::test_explicit_dimensions_and_seed_are_preserved`

via `generate_image → ingest_artifact_file → index_artifact_file → _store_artifact_chunk →
upsert_chunk (chroma.py:183) → _get_collection (chroma.py:45) → PersistentClient(real path)`.

Bisection also found a minimal reproducer that makes the order-dependence concrete:
`pytest tests/test_manual_research.py tests/test_image_generation.py` leaks 2; either file alone
leaks 0. `test_manual_research.py` imports `tir.memory.db` / `tir.artifacts.*` at module level,
which pulls chroma in before any fixture patches config.

**Second surface, same bug class, not in the task brief:** `tir/ops/chat_debug_trace.py:12`
binds `CHAT_DEBUG_TRACE_PATH = DATA_DIR / "chat_debug.jsonl"` at import, and
`write_chat_debug_trace` falls back to it. Patching `tir.config.DATA_DIR` does not change it.
This is why the production `chat_debug.jsonl` contains `conv-1` records — and it is why the
"solar eclipse / lattice" trace analysis had test fixtures mixed into real data. Same one-line
fix shape as (a′).

## 4. Q4 — The silent-failure path. **Real, but a separate item. Do not fold it in.**

`index_artifact_file` (`artifact_indexing.py:284-287`) catches every exception and returns
`status="failed"`, which is why seven weeks of leaking went unnoticed: the write either
succeeded into production or failed invisibly, and the test passed either way. Two reasons to
keep it out of this patch:

1. It is a **runtime behaviour change** in the ingest path, not a test-isolation change. Ingest
   deliberately degrades rather than destroys — a Chroma outage should not lose the artifact row
   and the file. Changing that deserves its own reasoning.
2. The guard (§2) removes the need: under the guard, a leaking write raises loudly at the
   `PersistentClient` boundary regardless of who swallows what downstream.

Worth recording precisely, since "silent" overstates it: the outcome *is* persisted, as
`indexing_status` in the artifact row's `metadata_json` (`ingestion.py:258-261`). It is recorded
but never surfaced — no log at WARNING, no diagnostic. Surfacing it is a reasonable follow-up.

---

## EXACT DIFF SCOPE

Two edited files, one new file. **No test-file changes. No change to retrieval, schema, the
backfill, `_event_text`, or the frontend.**

### Edited — `tir/memory/chroma.py`
- Replace `from tir.config import CHROMA_DIR, …` with `from tir import config` for `CHROMA_DIR`
  only; change the seven `chroma_path: str = CHROMA_DIR` signatures to `chroma_path: str | None = None`
  and resolve `chroma_path = chroma_path or config.CHROMA_DIR` in the body.
- Track the bound path alongside `_client`/`_collection`; rebind when a different path is
  requested. `reset_client()` clears it as now.

### Edited — `tir/ops/chat_debug_trace.py`
- Same treatment for `CHAT_DEBUG_TRACE_PATH` → resolve `config.DATA_DIR / "chat_debug.jsonl"` at
  call time inside `write_chat_debug_trace`.

### New — `tests/conftest.py`
- Session-scoped autouse guard wrapping `chromadb.PersistentClient` and the chat-debug path;
  raises with the offending test's nodeid and the resolved path.

### New — `tests/test_store_isolation.py` (small)
- `patch("tir.config.CHROMA_DIR", tmp)` alone (no reload, no `reset_client`) redirects
  `upsert_chunk` — the regression test for (a′).
- `_get_collection` rebinds when called with a different path.
- `patch("tir.config.DATA_DIR", tmp)` alone redirects `write_chat_debug_trace`.
- The guard raises when a test resolves the real `CHROMA_DIR`.

---

## Verification (required, in this order)

1. `pytest` in the real repo → **938 passed** (unchanged baseline; the backfill patch is now
   committed, so this is the post-backfill count).
2. Rebuild the isolated scratch tree, run the full suite there, assert `data/prod` contains
   **nothing** — the same measurement that produced §3, now returning zero on both surfaces.
3. Confirm production behaviour is untouched: start the server, one real chat turn, verify a
   chunk lands in `data/prod/chromadb` and a line in `chat_debug.jsonl` exactly as before.
4. Re-run the isolated suite a second time to confirm the result is stable, not order-luck.

---

## Open items for reviewer

1. **Confirm (a′) over (a)/(b)** — the task's (a) was measured not to work; (a′) is the
   corrected form. Recommended.
2. **Include the `_get_collection` cache rebind?** Recommended — without it, `chroma_path` stays
   a suggestion rather than an instruction, and the next fixture that forgets `reset_client()`
   writes into a previous test's collection. Production no-op.
3. **Include `chat_debug_trace.py`?** Recommended — same bug class, same one-line shape, and it
   is actively contaminating the trace file used for live diagnosis. Say so if you would rather
   keep this patch to Chroma alone.
4. **`OLLAMA_HOST` / `EMBED_MODEL` have the identical defect** (`embed_text`, `chroma.py:67-70`).
   No measured leak — tests that reach embedding either mock it or genuinely want the local
   Ollama — so I have left them alone. Fix now for consistency, or leave? I lean leave.
5. **`index_artifact_file` silent swallow** — separate item, per §4. Confirm.

## Then, separately (still needs its own approval, unchanged from the task brief)

Purge the orphaned `fake-output.png` event chunks. Current count, measured today: **71 event
chunks, 50 orphaned, 34 of them old-shape** — up from 48 when the backfill shipped, growing by 2
per suite run. Sequence after this fix or the store refills. Dry run, backup, before/after
counts, same as the backfill.

## Out of scope

- The relevance-floor / retrieval-ranking work.
- Re-running or extending the artifact backfill.
- Any change to `_event_text`, retrieval, schema, or frontend.
- Deleting anything from the store (the purge above is separate).
- The `index_artifact_file` exception swallow.

*Plan only. No code, no commit.*
