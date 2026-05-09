# Prompt Audit Notes

This file records human review decisions for entries found in `docs/PROMPT_INVENTORY.md`.

`docs/PROMPT_INVENTORY.md` is generated. Keep audit decisions here so regeneration does not overwrite review state.

## Reviewed — Keep

- `tir/engine/context.py` — Operational Guidance label
  - Decision: keep
  - Reason: Clear source boundary; not identity-shaping.

- `tir/engine/context.py` — retrieved memory labels
  - Decision: keep
  - Reason: Source framing is useful and aligned with continuity.

- `tir/artifacts/governance_blocklist.py` — governance file rejection message
  - Decision: keep
  - Reason: Clear operator-facing boundary; prevents governance/runtime files from becoming normal artifact memory.

- `tir/reflection/journal.py` — journal-space system prompt
  - Decision: keep for now
  - Reason: Recent output is closer to intended journal voice; observe over time.

- `tir/reflection/journal.py` — journal user prompt/template
  - Decision: keep for now
  - Reason: Provides structure without heavy identity/personality constraints.

- `tir/api/routes.py` — fallback/error response text
  - Decision: keep
  - Reason: Clear operational failure text; not identity-shaping. Prefer plain error/fallback language over stylized entity voice for failure cases.

## Reviewed — Changed

- `tir/behavioral_guidance/review.py` — system prompt
  - Decision: loosened
  - Reason: Removed Project Anam/personality/persona-heavy wording while preserving strict JSON task constraints.

- `tir/engine/context.py` — `BEHAVIORAL_GUIDANCE_LABEL`
  - Decision: loosened
  - Reason: Removed defensive identity/personality wording while preserving source and precedence.

- `tir/engine/context.py` — current/autonomous situation labels
  - Decision: loosened
  - Reason: Replaced “You are...” phrasing with neutral situation labels.

- `tir/tools/registry.py` — “memory may inform but not replace”
  - Decision: loosened/clarified
  - Reason: Preserves live-source boundary while using clearer source-framing language.
