# 2026-07-03 — Behavioral Probe Harness v1

## Summary

A standalone, read-only CLI (`scripts/probe.py`) that asks the entity a frozen set
of identity questions through the **real** context-assembly path, samples the chat
model N times per question, and records the answers in a dated JSON file **outside
every entity store**. It is the project's measurement instrument per NORTH_STAR §2,
run manually at day 0 (post-wipe), day 3, 7, 14, then weekly. Implements
`PLAN-2026-07-03-behavioral-probe-harness-v1.md` (approved with three additions,
all folded in). No commit.

## Zero-write is structural, not a flag

The probe only calls readers — `retrieve()` (vector query + FTS `SELECT` + RRF, no
writes), the shared `build_system_prompt_with_debug`, and
`chat_completion_text(role="chat")` **without tools** (no agent loop, no
`registry.dispatch`, so no tool can write). It imports no writer, no chunking, no
routes, no agent loop. There is no "no-persist mode" boolean to get wrong —
persistence is impossible by construction. A results file is written only to
`probe/results/`, outside `DATA_DIR` and the workspace (verified, and enforced at
runtime by a defense-in-depth output-path guard).

## Revision (2026-07-03, post-review) — budgeting matches the live path

Per reviewer, the probe now applies the **same retrieved-context budgeting the
live chat path applies**, so the instrument measures the entity under its lived
memory conditions and cannot silently overflow `num_ctx` as memory grows.
`budget_retrieved_chunks` is defined in `tir.engine.context_budget` (a non-routes,
read-only module — resolution (a)), imported and applied between `retrieve()` and
the builder:

```python
raw_chunks = retrieve(query=question, max_results=AUTO_RETRIEVAL_RESULTS)
chunks, budget = budget_retrieved_chunks(raw_chunks)   # same call the live path makes
```

The budget (`max_chars`, `used_chars`, `input_chunks`, `included_chunks`,
`truncated_chunks`) is recorded per sample in `retrieved_budget`; `retrieved_chunk_ids`
are the **post-budget, as-seen** IDs.

**Flagged for the reviewer (revert if you want budgeting-only):** to make the probe
match the live path *exactly* — and per the same "lived memory conditions" reason —
I also aligned the retrieval breadth to the live value: `retrieve(...,
max_results=AUTO_RETRIEVAL_RESULTS)` (=8), where the probe previously used
`retrieve()`'s default (`RETRIEVAL_RESULTS`=20). Both `AUTO_RETRIEVAL_RESULTS` and
`budget_retrieved_chunks` come from the same `context_budget` module. This is not the
literal one-line budgeting change; it is a second, intentional alignment toward
"matches live exactly," called out explicitly so it isn't a silent scope change. Not
matched: `artifact_intent` (kept default `False` — replicating routes' artifact-intent
detection would copy routes logic; `False` is correct for identity questions) and
`active_conversation_id` (the probe has no active conversation — correct).

## Frozen instrument decision (recorded in every results file)

A probe turn uses **autonomous-session framing** (`autonomous=True` →
`_autonomous_situation()`, no human speaker), with retrieval keyed on the question
text. A probe is not a conversation with Lyle or Jodie; the human-speaker framing
would inject a direct-address directive toward a nonexistent speaker and
contaminate the identity signal. `framing: "autonomous"` is recorded in each run's
metadata and documented in the script; changing it changes the instrument.

## Approved additions (all included)

1. **Retrieved chunk IDs per sample** — each sample records `retrieved_chunk_ids`
   (IDs only, no text) so drift analysis can tell "the retrieved memory changed"
   from "the answer to the same memory changed." Implemented by calling `retrieve()`
   explicitly and passing the chunks to the builder — the builder is **not**
   modified.
2. **Effective model options in run metadata** — `model`, `ollama_host`, and the
   resolved `get_model_options("chat")` (temperature, num_ctx, …) are recorded, so a
   settings change can't masquerade as identity drift.
3. **Empty-store run works and is tested** — the day-0 path (post-wipe, zero chunks)
   completes cleanly with empty retrieval; covered by a dedicated test.

## Files

- `scripts/probe.py` — the probe CLI (new). Outside the `tir` package by design.
- `probe/questions.md` — frozen question file (new). Format: append-only `## <id>`
  blocks. **Ships with three clearly-marked EXAMPLE questions the operator must
  finalize before the day-0 frozen run**; after day 0 it is append-only.
- `probe/results/.gitkeep` — keeps the (committed) results directory.
- `tests/test_probe.py` — the two required proofs + empty-store + parser tests (new).

**No changes** to `routes.py`, `context.py`, `retrieval.py`, chunking, or any store
module.

## Decisions taken (from the reviewer's rulings)

- **Result files are committed** (`probe/results/` tracked; nothing added to
  `.gitignore`) — they are the primary data product and must survive wipes/backups.
- **Zero-write assertion is counts** (all `working.db` + `archive.db` tables, Chroma
  collection count, FTS rows, workspace file listing) — byte-identical would
  false-fail on `get_or_create_collection`.
- **Location `scripts/probe.py`**, invoked `python -m scripts.probe` — this works via
  namespace packages (**no `scripts/__init__.py` needed**, verified, consistent with
  the existing `python -m scripts.extract_prompt_inventory`). `python scripts/probe.py`
  also works.

## Import list (read path only)

Direct: `argparse/json/hashlib/subprocess/sys/time/datetime/pathlib` (stdlib);
`tir.config` (`CHAT_MODEL`, `OLLAMA_HOST`, `get_model_options`, and `DATA_DIR`/
`WORKSPACE_DIR` inside the output guard); `tir.engine.context`
(`build_system_prompt_with_debug`); `tir.engine.context_budget`
(`AUTO_RETRIEVAL_RESULTS`, `budget_retrieved_chunks` — read-only, non-routes);
`tir.memory.retrieval` (`retrieve`); `tir.engine.ollama` (`chat_completion_text`).
A test parses the source AST and fails
if any writer/agent-loop/routes/chunking module is imported, or if any prompt-
assembly literal is duplicated in the script.

## Result JSON schema

`run`: timestamp (UTC), `git_head` (short hash), `model`, `ollama_host`,
`model_options`, `framing`, `samples_per_question`, `questions_file`,
`questions_file_sha256`. `results[]`: `question_id`, `question_text`,
`sample_index`, `answer` (verbatim), `latency_ms`, `retrieved_context_chars`,
`retrieved_chunk_ids` (post-budget, as-seen), `retrieved_budget` (`max_chars`,
`used_chars`, `input_chunks`, `included_chunks`, `truncated_chunks`), `error` (null
unless the sample failed — a failed sample is recorded and the run continues).

## CLI

```
python -m scripts.probe [--samples 3] [--questions probe/questions.md] \
                        [--out-dir probe/results] [--out PATH] [--force]
```
Default output `probe/results/<UTC-date>.json`; refuses to overwrite an existing
dated file without `--force`, and refuses to write under an entity store.

## Tests / checks run

- `tests/test_probe.py` → 5 passed:
  - seeded pass writes nothing to any store (counts identical before/after) and the
    only write is the out-of-store results file; chunk IDs, model options, and the
    applied budget (`max_chars`/`used_chars`/`input_chunks`) are recorded;
  - empty-store pass completes cleanly, `retrieved_chunk_ids == []`,
    `retrieved_context_chars == 0`, budget recorded (`used_chars == 0`), still zero writes;
  - shared-builder spy confirms `build_system_prompt_with_debug` is called with
    `autonomous=True`;
  - source guard: no duplicated assembly, no writer/routes/chunking/agent-loop imports;
  - question parser + validation (empty file, duplicate id, empty text all raise).
- Full suite: **906 passed** (the reload fixture restores real config on teardown;
  no cross-test pollution).
- `python -m scripts.probe --help` parses; default results path confirmed outside
  `DATA_DIR`/`WORKSPACE_DIR`.
- The instrument was **not** run live here — that is the operator's device test
  (run once against the current store; output is throwaway but proves the live path).

## Known limitations / notes

- `probe/questions.md` ships with example questions; the operator finalizes the
  frozen five before day 0.
- Retrieval now matches the live path: `AUTO_RETRIEVAL_RESULTS` breadth +
  `budget_retrieved_chunks` char budgeting (imported from the non-routes
  `context_budget` module, not copied). `artifact_intent` is not matched (default
  `False`, correct for identity questions).
- No scoring/analysis (later task), no memoryless-control arm (backlogged), no
  scheduler/API/UI — all out of scope for v1.

## Project Anam alignment check

- The measurement instrument NORTH_STAR §2 calls for: read-only, zero-write, results
  kept out of the entity's reach so measuring cannot contaminate the subject.
- Did not name/assign personality to the entity; no `soul.md`/persona change.
- No change to prompt assembly, retrieval ranking, chunking, routes, schema, or any
  store. No migration. No new dependency.
- Uses the shared context builder (no duplicated assembly). Placement outside `tir/`
  signals "not part of the entity."
