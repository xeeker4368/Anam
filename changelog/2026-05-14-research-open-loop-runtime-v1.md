# Research Open-Loop Runtime v1

## Summary

Added deterministic preview/create support for research open loops from existing registered research artifacts.

## Files Changed

- `tir/research/open_loops.py`
- `tir/admin.py`
- `tests/test_research_open_loops.py`
- `tests/test_admin.py`
- `docs/RESEARCH_OPEN_LOOP_DESIGN.md`

## Behavior Changed

- Added `research-open-loops-preview --artifact-id <id>`.
- Added `research-open-loops-create --artifact-id <id>`.
- Open-loop candidates are extracted deterministically from `Open Questions`, `New Open Questions`, and `Possible Follow-Ups`.
- `Suggested Review Items` are not converted into open loops.
- Created loops use the existing `open_loops` table with research-specific `metadata_json`.
- Creation is idempotent for the same artifact/question.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_research_open_loops.py -v`
- `.pyanam/bin/python -m pytest tests/test_open_loops.py -v`
- `.pyanam/bin/python -m pytest tests/test_manual_research.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest` passed, 632 tests.
- `git diff --check` passed.

## Known Limitations

- No `research-run` flags were added.
- No model-assisted extraction was added.
- No review items, working theories, Chroma indexing, retrieval changes, web source collection, scheduler, or autonomy were added.

## Follow-Up Work

- Consider `research-run --preview-open-loops` and `research-run --write --register-artifact --create-open-loops` after standalone commands prove useful.
- Design review-item creation separately.
- Design working theory/synthesis records separately.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not assign personality or identity.
- Did not edit `soul.md`.
- Did not re-enable behavioral guidance runtime loading.
- Preserved research open loops as unresolved questions, not conclusions or instructions.
