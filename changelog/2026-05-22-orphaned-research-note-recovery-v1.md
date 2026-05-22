# Orphaned Research Note Recovery v1

## Summary

Added a conservative recovery path for research notes that were written under `workspace/research/` but failed during artifact registration or indexing.

The recovery path is inspectable and idempotent. It can register an existing research note file, repair missing or partial deterministic research chunks, and no-op when artifact registration and indexing are already complete.

## Files Changed

- `tir/research/manual.py`
- `tir/memory/research_indexing.py`
- `tir/admin.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_manual_research.py`
- `tests/test_research_bounded.py`
- `tests/test_admin.py`
- `changelog/2026-05-22-orphaned-research-note-recovery-v1.md`

## Behavior Changed

- `register_manual_research_artifact(...)` is idempotent where safe.
- Added `research-note-register-existing --path ... --dry-run|--write`.
- Existing research files with no artifact can be registered and indexed.
- Existing research artifacts with missing chunks can be indexed.
- Existing research artifacts with complete chunks return no-op success.
- Existing research artifacts with partial chunks are repaired by deleting deterministic research chunks for the path and reindexing.
- Recovery does not update open-loop metadata.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_manual_research.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Recovery does not advance bounded open-loop daily counters or last-researched metadata.
- Recovery reconstructs only deterministic research artifact metadata available from the Markdown header.
- Recovery does not change research note format, DB schema, or Chroma schema.

## Follow-Up Work

- Consider a separate bounded-specific metadata completion command only if it can safely verify the whole durable bounded research path.
- Consider adding deeper Chroma/FTS parity diagnostics for research chunks in a later integrity audit.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign a fixed personality.
- Preserved raw research notes as source artifacts.
- Kept derived indexing repair source-linked and deterministic.
- Avoided silent open-loop metadata advancement.
- Did not change DB schema, Chroma schema, prompts, guidance files, UI, model config, Moltbook behavior, or web behavior.
