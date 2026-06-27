# 2026-06-25 — Chat renders artifact cards from real tool results (Card from real data, Commit 1)

## Summary

"Chat Media Tool Result Rendering v1." The chat UI now renders a generated-image
artifact **card** built strictly from the structured `image_generate` tool
result — never from the model's message text. This is the first half of killing
the confabulation vector (the model authoring copyable `[Artifact source: ...]`
prose). It does **not** change what the model sees as the tool result — that is
Commit 2 (planned separately).

## Prerequisite finding (carried into this commit)

The `tool_result` stream event reaching the frontend today carried only
`name`, `ok`, and `result` (the rendered JSON **string**). `artifact_id` /
`preview_url` existed only *inside* that string; there was **no structured
top-level carrier**, and `selection` rode only in the persisted trace, not the
stream event. So this commit had to plumb a structured carrier through —
explicitly part of the work, not an afterthought. Decoupling the card from the
`result` string also makes Commit 2 (reducing `result`) safe.

## What changed

**Backend — structured selection carrier (reuses the existing `selection_metadata` pattern, no new abstraction):**
- `tir/engine/tool_trace_context.py` — added `GENERATED_IMAGE_SELECTION_KIND` and
  `build_generated_image_selection(result)`. Returns `{kind, tool_name,
  artifact_id, preview_url, title, media_kind}` **only** for a real, successful
  artifact record (`ok is True` and `artifact_created` and an `artifact_id`);
  otherwise `None`. Wired into `selection_metadata_for_tool_result` for
  `image_generate`.
- `tir/engine/agent_loop.py` — the streamed `tool_result` event now includes a
  `selection` field when present (it already computed `selection` for the trace).
- `tir/api/routes.py` — the chat stream forwards `selection` on the `tool_result`
  event to the frontend.

**Frontend — `frontend/src/components/Chat.jsx`:**
- On a `tool_result` event whose `selection.kind === "generated_image"`, the
  card metadata is attached to the assistant message (`msg.artifacts`).
- New `<ArtifactCard>` renders the image. It fetches the preview through
  `apiFetch` → blob URL (a raw `<img src>` can't send the API-secret header that
  `/api/artifacts/{id}/file` requires when configured). `msg.content` continues
  to render as plain text.
- `frontend/src/styles.css` — minimal `.artifact-card` styling.

## Hard design rules (enforced)

- **Card is data-driven only.** It is built solely from the structured
  `tool_result` event. Message text is **never** parsed into a card, so
  model-authored `[Artifact source: ...]` prose can never render as a card.
- **Fail-safe-empty.** No `tool_result` selection, or a failed / no-artifact
  result, or a preview that fails to load → the card renders **nothing**. No
  broken image, no placeholder. Only a real successful artifact produces a visual.

## Behavior changed

- A successful `image_generate` in chat now shows a real image card beside the
  assistant's text.
- Failed generations show no card (and, from the earlier honesty fix, the model
  is told the tool failed).
- The model-visible tool-result text is **unchanged** in this commit.

## Tests / checks run

- New `tests/test_generated_image_selection.py` — builder + dispatcher: success →
  card; failure / no-artifact / missing id / non-dict → `None`; unrelated tool →
  `None`.
- `tests/test_agent_loop.py` — streamed event carries `selection` for a
  successful `image_generate`; carries none for a failed one.
- `tests/test_api_agent_stream.py` — the chat stream forwards `selection`.
- Full suite: **890 passed**.
- `docs/PROMPT_INVENTORY.md` regenerated (line-number shifts only; no new tracked
  strings).
- Frontend `vite build` succeeds (exit 0).

## Known limitations

- **No reload persistence.** The card is driven by the live stream event;
  `fetchMessages` maps only `{id, role, content, timestamp}` and drops
  `tool_trace`, so a hard refresh re-renders the message as plain text with no
  card. The artifact remains in the persisted trace / debug panel and is
  retrievable via `media_get`. Reload hydration from the persisted trace is a
  possible follow-up (kept out to preserve scope).
- **Auth at deploy:** locally on :8000 with no `ANAM_API_SECRET`, the preview
  loads either way; the `apiFetch`-blob path is what keeps it working when a
  secret is configured.

## Follow-up work

- **Commit 2 (planned, not implemented):** reduce the model-visible tool result to
  a minimal confirmation so there is no rich template to copy. Recall path
  verified (see plan doc) — `media_get(artifact_id)` returns title/prompt/seed/
  provenance. Decision pending with Lyle.

## Project Anam alignment check

- Did not assign the entity a name; did not call it Anam or Tír.
- Did not add or assign personality.
- **Serves Invariant 4 (experienced vs created):** the user now sees the *real*
  artifact record, and the model's own prose can never masquerade as one.
- No capability added or enable-gate widened; the image already existed as an
  artifact — this only displays it.
- No memory ingestion, provenance metadata, `authored_by`, chunking, image
  service, ComfyUI, or `context.py:306` change. No migration.
- No new external dependency or paid service.
- Additive; reuses the existing selection-metadata pattern (no new abstraction).
