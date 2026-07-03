# PLAN — Behavioral Probe Harness v1. PLAN ONLY.

**Date:** 2026-07-03 · **Mode:** plan only. **No implementation, no commit.** For reviewer approval before any code.

## APPROVED ADDITIONS (reviewer, 2026-07-03) — folded in below
1. **Retrieved chunk IDs per sample.** Record the list of retrieved `chunk_id`s (IDs only, no text) per sample, so drift analysis can separate "the retrieved memory changed" from "the answer to the same memory changed." Implemented by retrieving explicitly (`retrieve(query=question)`) and passing the chunks to the builder — the builder is **not** modified. (§4, §7)
2. **Effective model options in run metadata.** Record the resolved `get_model_options("chat")` (at least `temperature`, `num_ctx`) plus the Ollama host, so a settings change can't masquerade as identity drift. (§7)
3. **Empty-store run must work and be tested.** The day-0 baseline runs post-wipe against an empty store (zero chunks, possibly a not-yet-materialized collection). The script completes cleanly with empty retrieval; tests include an **empty-store pass** in addition to the seeded zero-write test. (§5)

**Rulings on open items:** (1) Result files are **committed** (primary data product; must survive wipes/backups) — `probe/results/` is tracked, nothing added to `.gitignore`. (2) Zero-write assertion is **counts** across all `working.db` tables + Chroma + FTS + workspace file listing (byte-identical would false-fail on `get_or_create_collection`). (3) Location is `scripts/probe.py` (outside the `tir` package — placement signals "not part of the entity"); `python -m scripts.probe` works via namespace packages (no `__init__.py` needed — verified, consistent with the existing `python -m scripts.extract_prompt_inventory`).

## NORTH_STAR check
This is the measurement instrument NORTH_STAR §2 asks for ("we are measuring, not performing"). Read-only, zero-write, results kept out of the entity's reach so the act of measuring cannot contaminate the subject. Strongly aligned; no invariant touched. It reads the real context path but does not modify it.

---

## 1. Design decision (made explicitly): whose context is a probe turn?

**Decision: autonomous-session framing, retrieval keyed on the question text.** The probe calls `build_system_prompt_with_debug(user_name="(probe)", user_message=<question>, autonomous=True, tool_descriptions=None)`.

- `autonomous=True` selects the existing `_autonomous_situation()` (context.py) — it takes **no human speaker**, framing the turn as the entity reflecting on its own rather than conversing with someone. `user_name` is inert under this branch (it feeds only `_current_situation`, which is skipped), so a neutral sentinel `"(probe)"` never appears in the prompt.
- **Why not `_current_situation(user_name)`:** a probe is not a conversation with Lyle or Jodie. Using the human-speaker framing would (a) require inventing a fake user identity and (b) inject the direct-address directive ("You are speaking with X…") toward a nonexistent speaker — contaminating exactly the identity signal we are trying to measure. Autonomous framing is the neutral, honest framing for an identity self-probe.
- **Retrieval keyed on the question text, matching the live path exactly.** The probe calls `retrieve(query=question, max_results=AUTO_RETRIEVAL_RESULTS)` then `budget_retrieved_chunks(...)` — the **same retrieval breadth and the same character budgeting the live chat path applies** — before handing the chunks to the builder. This is part of the frozen instrument: it measures the entity under its lived memory conditions, and it prevents the retrieved context from growing unboundedly and silently overflowing `num_ctx` as memory accumulates (an instrument that would otherwise degrade after day 0). Budget metadata (`max_chars`, `used_chars`, …) is recorded per sample.
- **No tools.** `tool_descriptions=None` and a no-tools generation (see §2). A single identity question needs no tools; including them would invite tool-call attempts the probe won't (and mustn't) dispatch, and would add write risk.

This framing choice **is part of the frozen instrument** — it will be recorded in the result JSON (`framing: "autonomous"`) and in a header comment in the script. Changing it later changes the instrument.

---

## 2. How zero-write is guaranteed *structurally* (not by a flag)

The probe writes nothing to any entity store because there is **no code path in it that calls a writer** — not because a boolean says "don't persist."

Per-sample flow:
1. `prompt, debug = build_system_prompt_with_debug(...)` → loads soul.md / OPERATIONAL_GUIDANCE.md (reads), runs `retrieve()` (vector query + FTS `SELECT` + RRF fusion — **all reads**, confirmed in `retrieval.py:261-325`).
2. `answer = chat_completion_text([{system}, {user}], role="chat")` → one non-streaming Ollama call, **no tools** (`ollama.py:117-145`). No agent loop, no `registry.dispatch`, so no tool can write.
3. Append the answer to an in-memory results list.

After all samples, write **one results file outside every store** (§7). That is the only disk write, and it is not under any ingested path.

**The only store-adjacent structural touch — addressed (requirement 2's warning):** `retrieve()` → `query_similar()` → `_get_collection()` calls `chromadb.get_or_create_collection`. If the collection already exists (the normal post-launch case — go-live creates it), this is a pure read. If it does not exist, an **empty** collection is materialized — which adds **zero documents/rows**. The zero-write test (§5) asserts document/row **counts** are unchanged, which holds either way. Implementation note: verify no store writes happen at **import** time (db/chroma clients are lazy — `init_databases` is a function, not called at import; the Chroma client is constructed lazily on first `_get_collection`). The zero-write test is the backstop.

---

## 3. File list

| File | Purpose | New/changed |
|------|---------|-------------|
| `scripts/probe.py` | The probe CLI. Reads questions, builds context via the shared builder, samples the model, writes results. | **new** |
| `probe/questions.md` | Frozen, versioned question set (format in §6). Created with format header + instructions; operator appends the 5 real questions. Append-never-edit after launch. | **new (content by operator)** |
| `probe/results/.gitkeep` | Keep the results dir in the repo; dated result files land here at runtime. | **new** |
| `tests/test_probe.py` | The two required tests + a question-parser test (§5). | **new** |

**No changes to** `routes.py`, `context.py`, `retrieval.py`, `chunking.py`, or any store module. (Run as `python -m scripts.probe`, matching the repo's existing `python -m scripts.extract_prompt_inventory` convention.)

---

## 4. Import list (explicit — requirement 4)

**Direct imports in `scripts/probe.py`:**
- stdlib: `argparse`, `json`, `sys`, `time`, `hashlib`, `subprocess`, `datetime` (timezone), `pathlib.Path`
- `from tir.engine.context import build_system_prompt_with_debug`  ← the shared builder, the **only** prompt-assembly source
- `from tir.memory.retrieval import retrieve`  ← read-only; called explicitly so we can record chunk IDs (Addition 1), then hand the chunks to the builder
- `from tir.engine.context_budget import AUTO_RETRIEVAL_RESULTS, budget_retrieved_chunks`  ← the live retrieval breadth + char budgeting (read-only, non-routes)
- `from tir.engine.ollama import chat_completion_text`  ← no-tools generation
- `from tir.config import CHAT_MODEL, OLLAMA_HOST, get_model_options`  ← result metadata + effective options (Addition 2)

**Deliberately NOT imported:** `tir.memory.chunking`, `tir.api.routes`, `tir.engine.agent_loop`, `tir.tools.registry`, and any writer (`save_message`, `checkpoint_conversation`, `upsert_chunk`, `ingest_artifact_file`, …). `tir.memory.retrieval` **is** now a direct import (Addition 1) — it is read-only (vector query + FTS `SELECT` + RRF, no writes). `tir.memory.db` / `tir.memory.chroma` are reached only transitively (via retrieval/context); no writer from them is ever called. Enforced by review + the source-guard assertion in `test_probe.py` (§5).

**On transitive imports:** importing `tir.engine.context` pulls in `retrieval → chroma, db`. Those are read-path dependencies; importing them performs no writes, and the probe never calls a writer from them. This preserves the "import only the read path" intent (structural read-only), with the zero-write test as proof. Import discipline is enforced by review + a source-guard assertion in `test_probe.py` (§5).

---

## 5. The two required tests (`tests/test_probe.py`)

Both run offline: patch `chat_completion_text` to return a canned answer and patch the query embedding (`tir.memory.chroma.embed_text`) to return a fixed 768-d vector, so retrieval executes against a temp Chroma/FTS without Ollama.

### Test A — Zero-write proof (requirement 2)
1. Fixture: temp `DATA_DIR`, `CHROMA_DIR`, `WORKSPACE_DIR` (monkeypatched + module reloads, mirroring `test_chunking.py`'s temp-store fixture). Seed a small store: create a user + a conversation, and index ≥1 chunk (the **test** may use chunking to seed — that's fine; the *probe* never does). This ensures the Chroma collection already exists (so `get_or_create` is a pure read) and retrieval has something to return.
2. **Snapshot before:** row counts of every `working.db` table (`conversations`, `messages`, `chunks_fts`, `artifacts`, …) and every `archive.db` table; Chroma `collection.count()`; the set of files under `WORKSPACE_DIR`. (Optionally a `sha256` of `working.db` for a byte-identical check.)
3. Run a **full probe pass** over a 2-question fixture set with `--samples 2`, writing results to a temp `--out-dir` (outside the store).
4. **Snapshot after; assert unchanged:** every table row count identical, Chroma count identical, FTS count identical, workspace file set identical. (Primary assertion = counts, per "row counts at minimum." The `working.db` byte-identical check is included as a stricter optional assert; noted as possibly flaky if SQLite touches file metadata on read — counts are the enforced guarantee.)
5. Assert the results file **was** written and lives under the temp out-dir, i.e. the only write is the out-of-store results file.

### Test B — Shared-builder assertion (requirement 3)
- **Spy:** `patch("scripts.probe.build_system_prompt_with_debug", wraps=<real>)`; run one probe pass; assert it was **called**, called once per (question × sample), and called with `autonomous=True` and `user_message=<question>`. This proves the probe routes prompt assembly through the shared builder.
- **Source guard (secondary):** assert `inspect.getsource(scripts.probe)` contains **none** of the assembly-owned strings (`"Retrieved context follows"`, `"[Operational Guidance]"`, `"[Current Situation]"`, `"[Artifact source:"`), proving no duplicated prompt-assembly and no forbidden writer imports (also assert the source does not import `chunking`/`routes`/`agent_loop`).

### Test A2 — Empty-store pass (Addition 3, the day-0 path)
- Fixture: temp store initialized but **empty** (no user, no conversation, no chunks; collection may be absent → `get_or_create` materializes an empty one). Ollama + embedding mocked offline.
- Run a full probe pass; assert: it completes without error, every sample's `retrieved_chunk_ids == []` and `retrieved_context_chars == 0`, an answer is recorded per sample, and (zero-write) all counts remain zero / unchanged. This is the single most important run of the instrument, so it is explicitly tested, not incidental.

### Test C — Question-parser (small, supporting)
- Parse a fixture `questions.md`; assert ids are extracted in order, bodies are correct, and a malformed/empty file raises a clear error (the probe must refuse to run with zero questions).

---

## 6. Question file format (`probe/questions.md`) — requirement 5

Frozen, versioned in the repo, read at runtime, **append-only** (never edit, reorder, or delete existing entries after launch — that would break longitudinal comparability). The plan defines **format only**; the operator writes the five questions.

**Format:** one question per block. A block starts with a Markdown H2 header whose text is the question's **stable, immutable id**; the lines until the next `## ` (or EOF) are the question text.

```markdown
# Behavioral Probe Questions — FROZEN INSTRUMENT
# Append-only. Never edit, reorder, or remove an existing `##` block after launch.
# The `##` header text is the permanent question id used to align results across runs.

## identity-name
<the question text the operator writes>

## identity-continuity
<the question text>
```

Parser rule: split on lines matching `^## `; `id = header.strip()`, `text = block body.strip()`. Ids must be unique; the probe errors on duplicate or empty ids, or an empty file. The operator supplies the 5 real questions; the plan does not.

---

## 7. Result JSON schema — requirement 7

**Location:** `probe/results/YYYY-MM-DD.json` (dated). `probe/` is a new top-level dir — **not** under `DATA_DIR` (`data/prod`), **not** under `WORKSPACE_DIR` (the artifact pipeline's watched dir), and not a store. Results are therefore never retrievable by the entity. If a file for the date already exists, the probe **errors** (protects the measurement record) unless `--out` is given explicitly.

```json
{
  "run": {
    "timestamp": "2026-07-03T18:00:00+00:00",   // run start, UTC ISO
    "git_head": "abc1234",                        // git rev-parse --short HEAD
    "model": "gemma4:26b",                        // CHAT_MODEL
    "ollama_host": "http://localhost:11434",      // Addition 2
    "model_options": {"temperature": 0.7, "num_ctx": 32768, "...": "..."},  // resolved get_model_options("chat") — Addition 2
    "framing": "autonomous",                      // the frozen framing decision (§1)
    "samples_per_question": 3,
    "questions_file": "probe/questions.md",
    "questions_file_sha256": "…"                  // integrity: which frozen set produced this run
  },
  "results": [
    {
      "question_id": "identity-name",
      "question_text": "…",
      "sample_index": 0,
      "answer": "full answer text",               // verbatim, untruncated
      "latency_ms": 1234,
      "retrieved_context_chars": 842,             // provenance: how much memory informed it
      "retrieved_chunk_ids": ["conv-uuid_chunk_0", "…"],  // IDs only, no text — Addition 1 (post-budget, as-seen)
      "retrieved_budget": {"max_chars": 14000, "used_chars": 842, "input_chunks": 3, "included_chunks": 3, "truncated_chunks": 0},  // budgeting matches live path
      "error": null                               // populated string if a sample failed
    }
  ]
}
```
- `full answer text` untruncated (v1 captures cleanly; no scoring).
- `retrieved_context_chars` comes free from `build_system_prompt_with_debug`'s debug dict (no second retrieval).
- `git_head` via `subprocess.run(["git","rev-parse","--short","HEAD"])` (best-effort; `"unknown"` if it fails).
- A failed sample records `error` and continues (one bad sample must not lose the run).

---

## 8. Sampling & CLI

- **Sampling:** N ≥ 3 samples per question per run; `--samples` default 3. Uses the normal chat model and options via `chat_completion_text(role="chat")` → `get_model_options("chat")`. No fixed seed/temperature override (sampling captures the model's natural variance, per requirement 6).

- **CLI usage line:**
  ```
  python -m scripts.probe [--samples 3] [--questions probe/questions.md] [--out-dir probe/results] [--out PATH] [--force]
  ```
  Defaults: `--samples 3`, `--questions probe/questions.md`, output `probe/results/<today>.json`. Run manually at day 0 (post-wipe, pre-first-conversation), day 3, 7, 14, then weekly.

---

## 9. Out-of-scope confirmation (none included)
- No scheduler/cron, API endpoint, frontend, or UI.
- No change to `routes.py`, chunking, retrieval ranking, or prompt assembly.
- No analysis/scoring of answers (drift metrics are a later task).
- No memoryless-control arm (backlogged).

## 10. Open items for reviewer
1. **Results in git:** commit dated result files as the longitudinal record (recommended), or gitignore `probe/results/*.json`? Either satisfies "not retrievable by the entity"; it's an operator/records choice.
2. **Byte-identical vs count-only** zero-write assertion for `working.db`: plan enforces **counts** (reliable) and includes byte-identical as an optional stricter check — confirm that's acceptable.
3. **Script home:** `scripts/probe.py` (recommended, matches existing `scripts/` module convention) vs `tir/probe.py`.

*Plan only. No code written, no changelog, no commit.*
