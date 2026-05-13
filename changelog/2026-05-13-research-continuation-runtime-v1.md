# Research Continuation Runtime v1

## Summary

Implemented manual research continuation for `research-run`.

## Files Changed

- `tir/research/manual.py`
- `tir/admin.py`
- `tests/test_manual_research.py`
- `tests/test_admin.py`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `docs/PROMPT_INVENTORY.md`
- `changelog/2026-05-13-research-continuation-runtime-v1.md`

## Behavior Changed

- `research-run` now accepts `--continue-artifact <artifact_id>` to continue from a registered active research artifact.
- `research-run` now accepts constrained `--continue-file <path>` for Markdown files under `workspace/research/`.
- Continuation dry-run writes nothing.
- Continuation `--write` creates a new research note and does not mutate the prior note.
- Continuation `--write --register-artifact` registers and indexes the new continuation note through the existing research artifact/indexing path.
- Continuation notes use `manual_research_continuation_v1` and include lineage metadata.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_manual_research.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest` — 622 passed
- `git diff --check` — passed

## Known Limitations

- No title/search continuation.
- No web source collection.
- No scheduler or autonomous research.
- No open-loop or review-item record creation.
- No promotion to truth, behavioral guidance, self-understanding, project decisions, or working theories.
- No retrieval ranking changes or DB schema changes.

## Follow-Up Work

- Design disambiguated title/search continuation.
- Design explicit open-loop/review-item creation flags with dry-run previews.
- Design bounded web source collection.
- Design working-theory promotion/supersession rules.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved prior research notes as provisional source artifacts.
- Created continuation notes as new artifacts rather than mutating prior notes.
- Did not mutate governance/runtime files or promote research to guidance, self-understanding, truth, or project decisions.
