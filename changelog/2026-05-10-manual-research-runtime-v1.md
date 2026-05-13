# Manual Research Cycle Runtime v1

## Summary

Added a CLI-only manual research runtime path that generates provisional structured Markdown research notes. Dry-run is the default; `--write` creates exactly one file under `workspace/research/`.

## Files Changed

- `tir/research/__init__.py`
- `tir/research/manual.py`
- `tir/admin.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_manual_research.py`
- `tests/test_admin.py`
- `changelog/2026-05-10-manual-research-runtime-v1.md`

## Behavior Changed

Added:

- `.pyanam/bin/python -m tir.admin research-run`
- `--question`
- `--scope`
- optional `--title`
- optional `--model`
- dry-run default
- `--write` file creation under `workspace/research/YYYY-MM-DD-<slug>.md`

The generated note includes the required provisional metadata and research sections.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_manual_research.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest` failed with 9 unrelated failures in existing artifact validation, Moltbook selection continuity, and URL prefetch tests; the new manual research tests passed.
- `git diff --check`

## Known Limitations

- No artifact registration is implemented.
- No indexing is implemented.
- No web search is implemented.
- No scheduler or autonomous recurrence is implemented.
- No open-loop or review-item creation is implemented.
- Model-only drafts are not externally verified.

## Follow-Up Work

- Add artifact registration/indexing behind explicit approval.
- Add research retrieval source framing.
- Design bounded web source collection before adding `--use-web`.
- Design optional open-loop/review-item creation.
- Design a future working-theory proposal path.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Keeps research conclusions provisional.
- Does not mutate behavioral guidance, self-understanding, operational guidance, project decisions, or `soul.md`.
- Does not change schema, artifact indexing, runtime prompt guidance, or memory architecture.
