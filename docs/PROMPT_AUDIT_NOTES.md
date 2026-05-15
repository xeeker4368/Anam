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

- `tir/engine/context.py` — `BEHAVIORAL_GUIDANCE_DORMANT_STATUS`
  - Decision: keep
  - Reason: Debug/status marker only; records that behavioral guidance runtime loading is dormant before go-live.

## Reviewed — Changed

- `tir/behavioral_guidance/review.py` — system prompt
  - Decision: loosened
  - Reason: Removed Project Anam/personality/persona-heavy wording while preserving strict JSON task constraints.

- `tir/engine/context.py` — behavioral guidance runtime label
  - Decision: retired
  - Reason: The label was removed from runtime prompt construction when behavioral guidance runtime loading became dormant before go-live.

- `tir/engine/context.py` — current/autonomous situation labels
  - Decision: loosened
  - Reason: Replaced “You are...” phrasing with neutral situation labels.

- `tir/tools/registry.py` — “memory may inform but not replace”
  - Decision: loosened/clarified
  - Reason: Preserves live-source boundary while using clearer source-framing language.

- `tir/engine/context.py` — behavioral guidance runtime label/loading
  - Decision: removed from runtime prompt construction
  - Reason: Behavioral guidance is dormant before go-live; runtime-loaded behavioral guidance was judged too prescriptive for the emergence goal.

- `tir/engine/context.py` — retrieved context header
  - Decision: loosened
  - Reason: Replaced broad self-memory framing with neutral source framing while preserving per-source labels.

- `OPERATIONAL_GUIDANCE.md` — runtime operational guidance
  - Decision: compressed
  - Reason: Reduced runtime prescription and response-style shaping while preserving source/tool/action safety, live-source boundaries, tool honesty, failure honesty, and uncertainty handling.

- `tir/reflection/journal.py` — journal prompt low-signal allowance
  - Decision: loosened
  - Reason: Quiet days and low-signal sections are explicitly valid, reducing pressure to invent significance while preserving journal structure.

- `tir/research/manual.py` — manual research prompt low-signal allowance
  - Decision: loosened
  - Reason: Research notes and continuations may honestly report no useful findings, no open questions, no follow-ups, or no review items while preserving provenance and required artifact structure.
