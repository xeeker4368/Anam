# PLAN — Image generation: stop tool-call confabulation (Option B). PLAN ONLY.

**Date:** 2026-08-12 · **Mode:** plan only. **No code, no commit.** Verify-then-plan; implementation only after review.
**Decided (not relitigated):** Option B — slim `_event_text`; ship together with Commit 2 (minimal model-visible tool-result). No retrieval exclusion, no frontend card change.

## NORTH_STAR check
Fixes a memory-formation pollution path: real generation provenance is indexed as a full forgeable prose block, retrieved, and imitated as fake tool output. Slimming the indexed/model-visible surface protects Invariant 4 (the entity must distinguish what it *did* from what it *fabricated*) without seeding content or excluding memory. Aligned.

---

## OPEN QUESTION 1 — Does current code still match the June diagnosis? **YES (verified in code, not docs).**

- **`_event_text` still emits the full block.** `tir/memory/artifact_indexing.py:74-154` builds, verbatim: `Artifact source`, **`Artifact ID`**, `File`, **`Stored path`**, `Source`, `Origin`, `Source role`, `MIME type`, **`Size: N bytes`**, **`SHA256`**, then (generation) `Generation prompt`, `Negative prompt`, backend/model/workflow, **`Generation seed`**, `Generation dimensions`. Unchanged since June.
- **It is dual-indexed.** `_store_artifact_chunk` writes both Chroma (`upsert_chunk`) and FTS (`upsert_chunk_fts`) — chunk id `artifact_{artifact_id}_event`. (Confirmed live during the 2026-08-12 orphan recovery: `0b6acc0e` carries an `artifact_..._event` chunk.)
- **`context.py` still injects it verbatim.** `tir/engine/context.py:333-350` (`artifact_document` branch): appends `f"[Artifact source: {title}, role: {source_role}, origin: {origin}, file: {filename}]\n{text}"` where `{text}` is the **entire event-block body**. So the full SHA/path/seed block reaches the model-visible prompt on any topical retrieval match. Diagnosis accurate.

## OPEN QUESTION 2 — Was a partial fix started/abandoned? **NO. "Scoped, not built" still holds.**

- `git log --since=2026-06-27 -- tir/memory/artifact_indexing.py` → **no commits.**
- `git log --since=2026-06-27 -- skills/active/media_artifacts/` → **no commits.**
- `git status` → **no uncommitted changes** to either. Clean slate; no half-fix to reconcile.

## OPEN QUESTION 3 — Does `media_get` recall still work, and is there a recall gap? **Works; gap is minimal by design.**

- `test_media_get_returns_safe_metadata_and_preview_url` still present (`tests/test_media_artifact_tools.py:281`). `get_media_artifact_reference` returns `title, path, preview_url, prompt, seed, width, height, …` from the artifact DB row + metadata — the recall surface is intact and independent of the event-chunk text.
- **The slim keeps `prompt + title + artifact_id` INLINE** in the retrieved chunk, so the *semantically meaningful* recall content ("what the image was of") remains model-visible even if the model never calls `media_get`. Only the forgeable identity fields leave the inline surface. So the June "tested-but-not-verified-live" worry (does the model reliably call `media_get`?) is largely defused: the recall-relevant data isn't behind `media_get` — it stays inline. `media_get` remains the path for the dropped detail (exact seed/dimensions/path), which recall rarely needs.
- **Per-field survival after slimming** (this is the "no recall gap" proof):

| field | slimmed chunk text | chunk metadata (retrievable/rank) | artifact DB row / `media_get` |
|---|---|---|---|
| title | **kept** | yes | yes |
| artifact_id | **kept** | yes (`base_metadata`) | yes |
| prompt (generation) | **kept** | yes (`MEDIA_PROVENANCE_FIELDS`) | yes |
| seed / width / height | dropped | **yes** (`MEDIA_PROVENANCE_FIELDS`) | yes (`media_get`) |
| filename / stored path | dropped | **yes** (`base_metadata`) | yes |
| SHA256 / byte size | dropped | no | **yes, artifact DB row** (`ingestion.base_metadata`), not surfaced by `media_get` |

Nothing needed for recall is lost; SHA/size persist on the durable artifact row (and the file itself) if ever required.

## OPEN QUESTION 4 — Other consumers of the full block shape? **One real parser; it is metadata-first, so the slim is safe. Enumerated below.**

- **`_event_text` has exactly one caller** — `artifact_indexing.py:258` (same file). Single-purpose for *writing* the chunk.
- **Hidden reader: `retrieval.py:112 _artifact_header_value(text, label)`** parses `Artifact ID` / `File` / `Artifact source` **out of the block text** in `_artifact_match` (`retrieval.py:128-155`, the opt-in artifact-ranking booster). **BUT every use is a metadata-first fallback:** `metadata.get("artifact_id") or _artifact_header_value(text, "Artifact ID")`, same for `filename`/`title`. Current-indexer chunks always carry `artifact_id`, `filename`, `title` in metadata (`base_metadata`), so the text-parse branch is only reached for chunks with no metadata (legacy/hand-authored). Therefore:
  - `Artifact ID` — **kept** in slim anyway (title+id+prompt); fallback still works.
  - `Artifact source` (title) — **kept** in slim; fallback still works.
  - `File` (filename) — dropped from text, but `metadata["filename"]` is always present → `_artifact_match` filename matching is unaffected for real chunks.
  - **Conclusion:** slimming does not break `_artifact_match` for any chunk the current indexer produces. The plan will add a test asserting `_artifact_match` still detects id/filename/title hits from a slimmed chunk (via metadata).
- **No other consumer** reads block-body fields (grep for `SHA256`/`Stored path`/`Generation seed`/`_artifact_header_value` across `tir/`, `tests/`, `skills/` returns only the above).

---

## EXACT DIFF SCOPE

### Surface 1 — `_event_text` slim (`tir/memory/artifact_indexing.py`)

**Design precision the plan must resolve (NOT a relitigation of Option B — a scoping question within it):** `_event_text` is shared by **all** artifact types (uploads, screenshots, generated images via `index_artifact_file`), not just generation. The decided keep-set `title + artifact_id + prompt` is generation-shaped; `prompt` is empty for uploads, whose semantic recall content is `description` / `observed_description` (e.g. a vision caption). Applying `keep only {title, id, prompt}` literally would gut upload/vision retrievability.

**Faithful generalization of the decision (recommended):** drop the **forgeable identity fields for all artifact types** — `Stored path`, `SHA256`, `Size: N bytes`, `File`, and the multi-line block layout — and keep the **non-forgeable semantic/recall fields**: `title`, `artifact_id`, and the content descriptor (`prompt` for generations; `description`/`observed_description` for uploads/vision). Proposed slimmed shape (one compact form, not a provenance ledger):
```
Artifact: {title} (id: {artifact_id})
Prompt: {prompt}                      # generation only, when present
Description: {description}            # non-generation, when present
Observed description ({uncertainty}; visual interpretation, not verified fact): {observed_description}   # when present
```
Explicitly **removed:** `File`, `Stored path`, `Source`, `Origin`/`Source role` (already in the context.py header + metadata), `MIME type`, `Size`, `SHA256`, `Generation backend/model/workflow/workflow ID`, `Generation seed`, `Generation dimensions`, `Interpretation source`, `Human confirmed`. (All still in chunk metadata and/or `media_get`; see Q3 table.)

*If the reviewer wants the literal generation-only keep-set instead (accepting reduced upload/vision recall), that is a one-line narrowing — flagged for the call, not assumed.*

- **Forward-only:** this changes only **newly indexed** artifacts. Existing `artifact_..._event` chunks keep the full block until re-indexed or wiped. Acceptable because launch includes a wipe; stated so it isn't a surprise if an old block still appears pre-wipe. (No back-fill/migration in scope.)

### Surface 2 — Commit 2: minimal model-visible tool result (ships together)

The problem repeats *within a conversation*: a fresh generation's full tool-result JSON re-poisons history. **Constraint discovered:** in the agent loop (`agent_loop.py:245-278`), both the model-visible text **and** the card come from the **same** `envelope["value"]` (the full `_shape_generated_image_result` dict) — `rendered = render_tool_envelope(envelope)` feeds `model_content`, while `selection_metadata_for_tool_result(tool_name, envelope["value"])` builds the card (needs `artifact_id`, `preview_url`, `artifact_title`, `media_kind`). **So the tool's returned dict must NOT be slimmed** — that would break the card (Commit 1) and the streamed event/trace.

**Mechanism (recommended): reduce model-visible text only, downstream of the shared value.** Add a per-tool model-summary hook mirroring the existing `frame_failed_tool_message` / `selection_metadata_for_tool_result` dispatch:
- New `summarize_tool_result_for_model(tool_name, value) -> str | None` in `tir/tools/rendering.py`: for `image_generate` success returns e.g. `image generated; artifact_id=<id>; shown to user in the chat UI` (omit preview_url, full prompt, seed, dimensions, SHA, path); returns `None` for everything else.
- In `agent_loop.py` success path: `model_content = summarize_tool_result_for_model(tool_name, envelope["value"]) or rendered`. The streamed `tool_result_event["result"]` (UI/debug), the `selection` (card), and the persisted trace keep the **full** `rendered`/value — only the `role:"tool"` message the model reads is minimal.

This keeps the frontend card untouched (Commit 1 intact), keeps debug/trace complete, and removes the rich template from both the fresh-turn history and (via Surface 1) future retrieval. Files: `tir/tools/rendering.py`, `tir/engine/agent_loop.py`.

*Diff scope is confined to: `artifact_indexing.py` (`_event_text`), `tir/tools/rendering.py` (+1 helper), `tir/engine/agent_loop.py` (1 line at the success-path `model_content`). No change to `_shape_generated_image_result`, the tool schema, retrieval, or `Chat.jsx`.*

---

## Tests (plan)

- **`_event_text` slim:** unit test asserting the new output contains `title`, `artifact_id`, and the content descriptor, and does **not** contain `SHA256`, `Stored path`, `Size`, byte counts. Cover generation (prompt kept) and upload (description/observed_description kept).
- **Consumer safety (Q4):** test that `_artifact_match` still returns exact hits for `artifact_id` / `filename` / `title` given a *slimmed* chunk with metadata (proves the metadata-first path, not the dropped text lines, carries matching).
- **Commit 2:** test that a successful `image_generate` result yields (a) a minimal `model_content` string (no preview_url/SHA/seed) fed to the model, while (b) the `tool_result` event still carries the full `result` and the `generated_image` selection (card unaffected), and (c) a non-media tool's `model_content` is unchanged (falls back to `rendered`).
- **Audit existing tests that assert block content:** `tests/test_artifact_ingestion.py` and `tests/test_retrieval.py` build artifact chunks and assert on their text/headers — update any assertion that expects the dropped lines. Full suite must stay green.

## Live verification (per the testing requirement — MANDATORY conditions)
- **Clean conversation thread only.** No prior image-gen chatter in context — a contaminated thread reproduces the old bug regardless of fix correctness (this misled June testing). Start a fresh conversation, then request one generation.
- Confirm: a real `image_generate` **tool dispatch** occurs (visible in the debug event stream / `tool_trace`), a card renders, and the model does **not** emit a fabricated provenance block. Then, in a *separate* clean thread, ask a topical question that would retrieve a prior generation's event chunk and confirm no fabricated block is produced.
- Use `ANAM_DEBUG_PROMPT=1` to capture the assembled prompt and confirm the retrieved artifact chunk now shows the slimmed block (no SHA/path).

## Out of scope (unchanged)
- No `soul.md` / OPERATIONAL_GUIDANCE nudge. No backup/orphan/other bug-list items. No ComfyUI workflow/checkpoint quality. No retrieval exclusion. No frontend card change. No back-fill of existing chunks.

## Open items for reviewer
1. **Confirm the `_event_text` slim generalizes to all artifact types** (keep semantic content: prompt for generation, description/observed_description for uploads/vision; drop forgeable identity for all) — recommended — vs. the literal generation-only `{title,id,prompt}` keep-set (accepts reduced upload/vision recall).
2. **Confirm the Commit-2 mechanism** (model-visible-only reduction via a per-tool summary hook, tool return value + card left full) — recommended, since slimming the returned dict would break the shipped card.

*Plan only. No code, no commit.*
