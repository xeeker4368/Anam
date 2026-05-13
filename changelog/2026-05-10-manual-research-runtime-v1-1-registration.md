# Manual Research Runtime v1.1 Registration

## Summary

Added explicit manual research artifact registration and indexing behind `--write --register-artifact`.

## Files Changed

- `tir/research/manual.py`
- `tir/memory/research_indexing.py`
- `tir/admin.py`
- `tests/test_manual_research.py`
- `tests/test_admin.py`
- `docs/PROMPT_INVENTORY.md`
- `changelog/2026-05-10-manual-research-runtime-v1-1-registration.md`

## Behavior Changed

- `research-run` dry-run remains unchanged.
- `research-run --write` remains file-only.
- `research-run --register-artifact` without `--write` fails clearly.
- `research-run --write --register-artifact` writes the research note, registers an `artifact_type=research_note` artifact, and indexes the note as `source_type=research`.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_manual_research.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Registration/indexing is available only when explicitly requested.
- No web search is implemented.
- No scheduler or autonomous recurrence is implemented.
- No open-loop or review-item creation is implemented.
- No research supersession or revision workflow is implemented.
- File, artifact registration, and indexing are not one database transaction.

## Follow-Up Work

- Add research retrieval source-framing cleanup if needed.
- Design optional open-loop/review-item creation separately.
- Design bounded web source collection before adding `--use-web`.
- Design research revision/supersession behavior.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Keeps research conclusions provisional.
- Does not mutate behavioral guidance, self-understanding, operational guidance, project decisions, or `soul.md`.
- Does not change schema or runtime prompt guidance.
