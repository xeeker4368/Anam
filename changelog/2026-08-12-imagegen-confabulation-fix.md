# 2026-08-12 — Image generation: stop tool-call confabulation (Option B, both surfaces)

## Summary

The model sometimes fabricated a tool-result-shaped prose block (fake
`artifact_id`, stored path, SHA256) instead of actually calling `image_generate`,
with zero real tool dispatch. Root cause: real generations were indexed as a full
verbatim provenance block by `_event_text` and injected verbatim into the
model-visible prompt on retrieval; a fresh generation's full tool-result JSON also
re-poisoned same-conversation history. This is ONE fix at two surfaces, shipped
together (Option B). Implements `PLAN-2026-08-12-imagegen-confabulation-fix.md`
(both flagged decisions approved). No commit.

## Surface 1 — slim `_event_text` (`tir/memory/artifact_indexing.py`)

`_event_text` now emits only non-forgeable, semantic/recall content and drops the
forgeable identity fields **for all artifact types** (approved generalization):

- **Kept:** `Artifact: {title} (id: {artifact_id})`, `Prompt`/`Negative prompt`
  (generations), `Description` and `Observed description` (uploads/vision).
- **Dropped from the indexed prose:** `File`, `Stored path`, `Source`, `Origin`,
  `Source role`, `MIME type`, `Size: N bytes`, `SHA256`, generation
  backend/model/workflow/workflow-id, `Generation seed`, `Generation dimensions`,
  `Interpretation source`, `Human confirmed`, and the multi-line block layout.
- The single caller (same file, line ~258) was updated to the slimmed signature.
  `size_bytes`/`sha256` remain accepted params on `index_artifact_file` (fed by
  `ingestion.py`, out of the approved diff scope) but are no longer rendered — a
  deliberate interface-stability choice to keep the diff to the three named files.
- **Forward-only:** only newly indexed artifacts get the slim text; existing
  `artifact_*_event` chunks keep the full block until re-indexed or wiped
  (acceptable — launch includes a wipe). No back-fill.

## Surface 2 — minimal model-visible tool result (Commit 2)

`tir/tools/rendering.py`: added `summarize_generated_image_result(value)` and a
tool-dispatch wrapper `summarize_tool_result_for_model(tool_name, value)`
(media tools only, mirroring `frame_failed_tool_message` /
`selection_metadata_for_tool_result`). For a successful `image_generate` it returns
`image generated; artifact_id=<id>; shown to user in the chat UI`.

`tir/engine/agent_loop.py`: on the success path, `model_content =
summarize_tool_result_for_model(tool_name, envelope.get("value")) or rendered`. Only
the `role:"tool"` message the model reads is reduced. The tool's returned dict, the
streamed `tool_result` event (`result`), the `generated_image` card `selection`, and
the persisted trace all keep the **full** value — so the frontend card (Commit 1) is
untouched, and debug/trace stay complete.

## REQUIRED VERIFICATION (metadata vs prose — written down, not assumed)

**`_artifact_match` (`retrieval.py:121-157`) depends on chunk METADATA, not the
`_event_text` prose.** It reads, in order, `metadata.get("artifact_id")`,
`metadata.get("filename")`, `metadata.get("title")` — and only falls back to parsing
the header text (`_artifact_header_value`, looking for `Artifact ID:` / `File:` /
`Artifact source:`) when a metadata field is absent.

**The `_event_text` slim only changes the indexed chunk TEXT, never the chunk
metadata.** In `index_artifact_file`, the chunk is written with
`metadata=event_metadata` where `event_metadata = {**base_metadata, chunk_index,
chunk_kind}`, and `base_metadata` carries `artifact_id`, `title`, `filename`, `path`,
`origin`, `source_role`, `created_at`, plus merged `media_metadata` (prompt, seed,
width, height, observed_description, …). This dict is built **independently** of the
`text=_event_text(...)` argument (verified in code). Therefore:

- `artifact_id`, `filename`, `title` remain in metadata → `_artifact_match` exact
  matching (id/filename/title) is unaffected by the slim for every chunk the current
  indexer produces. The header-text fallback is now only exercised by legacy /
  hand-authored chunks that lack metadata.
- seed/width/height/prompt/negative_prompt/observed_description remain in chunk
  metadata (via `MEDIA_PROVENANCE_FIELDS`); `SHA256`/byte-size remain on the artifact
  DB row (via `ingestion.base_metadata`) and the file itself. Nothing needed for
  recall or ranking is lost — only the imitable prose is gone.

A regression test (`test_artifact_match_uses_metadata_not_slimmed_text`) asserts
exact id/filename/title matching still works against a slimmed-text chunk.

## Recall path (`media_get`) — unchanged, and gap minimized

`test_media_get_returns_safe_metadata_and_preview_url` still passes;
`get_media_artifact_reference` returns title/path/preview_url/prompt/seed/width from
the artifact row + metadata. Because the slim keeps `prompt + title + artifact_id`
inline, the semantically meaningful recall content stays model-visible even without a
`media_get` call — so there is no practical recall gap; `media_get` covers the
dropped exact detail (seed/dimensions/path) when needed.

## Files changed

- `tir/memory/artifact_indexing.py` — slim `_event_text` + caller.
- `tir/tools/rendering.py` — `summarize_generated_image_result`,
  `summarize_tool_result_for_model`.
- `tir/engine/agent_loop.py` — use the summary for media-tool success `model_content`;
  import the helper.
- `tests/test_rendering.py` (new) — summary minimal/None/dispatch cases.
- `tests/test_retrieval.py` — `_artifact_match` metadata-not-text regression.
- `tests/test_agent_loop.py` — image_generate success: full event/selection, minimal
  model message.
- `tests/test_artifact_ingestion.py` — `_event_text` slim unit test (generation +
  upload) + forgeable-absent assertions.
- `tests/test_image_generation.py`, `test_image_generation_api.py`,
  `test_artifact_upload_api.py` — updated old-prose assertions to the slim shape
  (`Prompt: …`); metadata assertions unchanged (confirming metadata is untouched).
- `docs/PROMPT_INVENTORY.md` — regenerated (line shifts).

## Behavior changed

- New artifact chunks index slim provenance text; retrieval injects the slim block.
- A successful chat image generation now feeds the model a one-line confirmation
  instead of the full JSON block. Frontend card, streamed event, and trace unchanged.
- Retrieval ranking, chunk metadata, tool schema, and `_shape_generated_image_result`
  return value are all unchanged.

## Tests / checks run

- Full suite → **913 passed**. New tests listed above pass; updated old-prose
  assertions pass; metadata assertions still pass (proves metadata untouched).

## Live verification (operator — MANDATORY conditions)

Must run in a **CLEAN conversation thread** with no prior image-gen chatter — a
contaminated thread reproduces the old bug regardless of fix correctness (this
misled June testing). In a fresh thread: request one image, confirm a real
`image_generate` **dispatch** appears in the debug/tool_trace stream, a card
renders, and no fabricated provenance block is emitted. Then in a *separate* clean
thread, ask a topical question that would retrieve a prior generation's event chunk
and confirm no fabricated block. `ANAM_DEBUG_PROMPT=1` will show the retrieved
artifact chunk now carries the slim text (no SHA/path).

## Project Anam alignment check

- Removes a memory-formation pollution path (fabricated provenance replayed as
  fact) — serves Invariant 4 (distinguish what the entity did from what it
  fabricated). No content seeded; no retrieval exclusion.
- No `soul.md`/persona change; no schema/migration; no new dependency. Frontend card
  logic untouched. Scoped to the three approved files (+ their tests).
