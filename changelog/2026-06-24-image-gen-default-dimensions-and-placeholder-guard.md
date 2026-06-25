# 2026-06-24 — Fix conversational image generation (default dimensions + fail-loud placeholder guard)

## Summary

Image generation failed from the conversational/agent path while the UI form
worked. The entity's `image_generate` tool call omitted `width`/`height`/`seed`,
those arrived as `None`, and the ComfyUI backend left the corresponding workflow
placeholders unsubstituted — shipping the literal strings `{{width}}`,
`{{height}}`, `{{seed}}` to ComfyUI, which then raised
`invalid literal for int() with base 10: '{{width}}'` / `'{{seed}}'`.

Two changes: (1) resolve `width`/`height`/`seed` to concrete integers at the
source so every path (agent, UI, CLI) substitutes correctly, and (2) add a
fail-loud guard so a malformed workflow can never be POSTed downstream again.

## Root cause

`tir/media/backends/comfyui.py::_load_workflow` built its placeholder
replacement map conditionally — `{{width}}/{{height}}/{{seed}}` were only added
`if request.X is not None`. `{{prompt}}`/`{{negative_prompt}}` were added
unconditionally, which is why only the three numeric fields failed. The
conversational path invokes `image_generate` without those values, so they
defaulted to `None`, the placeholders were never replaced, and the literal
`{{...}}` tokens reached ComfyUI.

The workflow JSON itself was correct — `grep` confirms exactly
`{{prompt}} {{negative_prompt}} {{width}} {{height}} {{seed}}`. This was a
`None`-value problem, not a JSON-syntax problem.

## Tool-schema finding (verified, not assumed)

The agent-callable tool is `image_generate`, defined in
`skills/active/media_artifacts/media_artifacts.py` and registered via the
`@tool` decorator with an `args_schema`. It **does** expose `width`, `height`,
and `seed` to the entity — all three are present in the schema's `properties`
but are **optional** (only `prompt` is `required`; the Python parameters default
to `None`). So dimensions are entity-controllable; the entity simply omits them
in normal chat and they arrive as `None`.

Consequence for the fix: defaults are applied **only when the value is omitted**,
so the entity retains the ability to override width/height/seed (consistent with
"grant capacity, don't seed content"). The schema was not changed.

## Files changed

- `tir/config.py` — added `IMAGE_GENERATION_DEFAULT_WIDTH` and
  `IMAGE_GENERATION_DEFAULT_HEIGHT` (env `ANAM_IMAGE_GENERATION_DEFAULT_WIDTH` /
  `..._HEIGHT`, config keys `default_width` / `default_height`, fallback `512`).
  Previously only `max_width`/`max_height` (2048) existed — there was no default.
- `config/defaults.toml` — added `default_width = 512` and `default_height = 512`
  under `[image_generation]`. Operators may override these in `config/local.toml`.
- `tir/media/image_generation.py` — `import random`; after the existing
  `_validate_dimensions` call, resolve `width`/`height` to the configured defaults
  and `seed` to a random integer (`random.randint(0, 2**32 - 1)`) when omitted.
  Resolved values flow through `_generation_params`, the backend request, the
  dry-run report, and the stored metadata.
- `tir/media/backends/comfyui.py` — `import re`; added
  `_find_unsubstituted_placeholders` and, in `_load_workflow`, a scan of the
  rendered workflow for any surviving `{{...}}` token. If one remains it raises
  `ImageGenerationBackendError(error_type="config_error", ...)` naming the
  placeholder(s) **before** the POST to ComfyUI.
- `tests/test_image_generation.py` — added defaults to the env fixture and four
  tests (see below).

## Behavior changed

- Conversational/agent image generation now succeeds: omitted dimensions resolve
  to 512×512 and an omitted seed resolves to a random value rather than failing.
- Explicit `width`/`height`/`seed` supplied by the entity or UI are still honored.
- `seed`, `width`, and `height` are now always recorded in artifact metadata
  (previously a `None` seed was dropped) — improving reproducibility/provenance.
- A workflow containing any unsubstituted `{{...}}` placeholder now fails fast
  with a `config_error` naming the placeholder, instead of being sent to ComfyUI.

## Tests / checks run

- `python -m pytest tests/test_image_generation.py -q` → 11 passed.
- `python -m pytest -q` (full suite) → 876 passed.
- New tests:
  - omitted `width=None,height=None,seed=None` → backend request and metadata
    carry concrete integers (512/512 + a seed in `[0, 2**32-1]`);
  - explicit `1024/768/99` are preserved;
  - `_load_workflow` raises `config_error` naming `{{unknown}}` for an
    unsubstituted placeholder;
  - `_load_workflow` substitutes all five known placeholders cleanly.

## Known limitations

- 512×512 is the SD 1.5 native default; change `default_width`/`default_height`
  in config if a different default is wanted.
- Seed range is `[0, 2**32 - 1]`; widen if a workflow expects a larger space.

## Follow-up work

- None required. Optionally mirror `default_width`/`default_height` into
  `config/local.example.toml` for operator discoverability.

## Project Anam alignment check

- Did not assign the entity a name; did not call it Anam or Tír.
- Did not add or assign personality.
- No capability was added or its enable-gate widened — image generation was
  already a settled, enabled decision (`enabled = true`, `allow_agent_tool =
  true`); `allow_agent_tool`/enable gate untouched (NORTH_STAR Invariant 6
  respected). This fixes an existing decided capability.
- Raw experience / provenance preserved and improved: the seed is now always
  recorded with the generated artifact (Invariant 4).
- No memory architecture, schema, or database change; no migration required.
- No new external dependency or paid service.
- Workflow JSON, checkpoint, and output quality untouched; backend not refactored
  beyond the fail-loud guard.
- Additive, small-scoped change with explicit config and tests.
