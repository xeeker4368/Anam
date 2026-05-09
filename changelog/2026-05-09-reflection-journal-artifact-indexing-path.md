# Reflection Journal Artifact and Indexing Path

## Summary

Added explicit manual paths for registering reflection journals as durable artifacts and indexing them as retrievable journal memory.

## Files Changed

- `tir/admin.py`
- `tir/artifacts/source_roles.py`
- `tir/engine/context.py`
- `tir/memory/journal_indexing.py`
- `tir/reflection/journal.py`
- `tests/test_admin.py`
- `tests/test_artifact_ingestion.py`
- `tests/test_context.py`
- `tests/test_reflection_journal.py`

## Behavior Changed

- `reflection-journal-day --write` remains file-only by default.
- `reflection-journal-day --write --register-artifact` now writes the journal, registers it as a `journal` artifact, and indexes it as `source_type=journal`.
- Added `reflection-journal-register YYYY-MM-DD` to register and index an existing `workspace/journals/YYYY-MM-DD.md` file without regenerating it.
- Retrieved journal chunks prefer `metadata.journal_date` in the existing journal memory label.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_reflection_journal.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- Registration and indexing are not wrapped in one atomic transaction.
- Existing Chroma chunks cannot be scanned directly for duplicate IDs; duplicate prevention checks artifact path and deterministic FTS chunk IDs.
- Journal registration is CLI-only; no UI/API path was added.
- Journals are indexed in full for v1, without section-level filtering.

## Follow-Up Work

- Decide whether journal artifact registration should later become the default for `--write`.
- Add richer journal source/search controls if retrieved journal memory becomes too self-reinforcing.
- Consider a repair command for partially registered journals if artifact creation succeeds but indexing fails.

## Project Anam Alignment Check

- Does not assign the entity a name or fixed personality.
- Preserves journals as derived reflective experience with explicit source framing.
- Keeps registration manual/admin-triggered and avoids scheduler or autonomous background behavior.
- Does not mutate `BEHAVIORAL_GUIDANCE.md`, `OPERATIONAL_GUIDANCE.md`, or `soul.md`.
- Preserves the distinction between workspace artifacts and self-modification.
