# Disable Behavioral Guidance Runtime Loading

## Summary

Behavioral Guidance is dormant before go-live. Runtime prompt construction and reflection journal entity context no longer load active behavioral guidance from `BEHAVIORAL_GUIDANCE.md`, and apply commands now fail clearly instead of writing active guidance.

## Files Changed

- `BEHAVIORAL_GUIDANCE.md`
- `ACTIVE_TASK.md`
- `DECISIONS.md`
- `PROJECT_STATE.md`
- `ROADMAP.md`
- `docs/BEHAVIORAL_GUIDANCE_DORMANT_DECISION.md`
- `docs/BEHAVIORAL_GUIDANCE_REVISION_DESIGN.md`
- `docs/GUIDANCE_SCOPING_DESIGN.md`
- `docs/PROMPT_AUDIT_NOTES.md`
- `docs/PROMPT_INVENTORY.md`
- `tir/admin.py`
- `tir/behavioral_guidance/apply.py`
- `tir/engine/context.py`
- `tir/reflection/journal.py`
- `tests/test_admin.py`
- `tests/test_behavioral_guidance_apply.py`
- `tests/test_context.py`
- `tests/test_prompt_inventory.py`
- `tests/test_reflection_journal.py`

## Behavior Changed

- Runtime chat/system prompts do not include `[Reviewed Behavioral Guidance]`.
- Active-looking `- Guidance:` lines in `BEHAVIORAL_GUIDANCE.md` are ignored by runtime prompt construction.
- Context debug reports behavioral guidance as `dormant_before_go_live` with zero included items and zero characters.
- Reflection journal prompts no longer receive active behavioral guidance as entity context.
- Behavioral guidance apply dry-run/write paths fail with: `Behavioral guidance is dormant before go-live and is not runtime-active.`
- `BEHAVIORAL_GUIDANCE.md` is now a dormant placeholder and contains no active guidance lines.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_reflection_journal.py -v`
- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance_apply.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_behavioral_guidance.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- The proposal/review/list APIs remain present as dormant/admin history surfaces.
- The frontend was not updated in this patch.
- The old apply helper formatting code remains for review context, but public apply entrypoints are dormant.

## Follow-Up Work

- Complete external review triage and decide whether any dormant UI labeling is needed before go-live.
- Design any future replacement or reintroduction only through a separate reviewed decision with explicit scope and safeguards.
- Implement minimal household multi-user support before go-live in a separate patch.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add fixed personality or identity guidance.
- Preserved raw experience and source-boundary framing.
- Did not change DB schema, retrieval ranking, model config, or runtime prompts beyond removing behavioral guidance as active steering.
