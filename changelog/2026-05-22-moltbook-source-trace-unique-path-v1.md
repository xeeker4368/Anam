# Moltbook Source Trace Unique Path v1

## Summary

Moltbook source trace sidecars now use timestamped unique paths so repeated feed/query collection runs do not collide on generic same-day filenames.

## Files Changed

- `tir/research/moltbook_sources.py`
- `tir/research/bounded.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_moltbook_source_collection.py`
- `tests/test_research_bounded.py`
- `changelog/2026-05-22-moltbook-source-trace-unique-path-v1.md`

## Behavior Changed

- Added `source_trace_unique_relative_path(trace, prefix_slug=None)`.
- Standalone `write_source_trace(...)` now defaults to timestamped unique paths.
- Bounded research Moltbook source traces include the open-loop short id, source mode, source slug, and retrieval time.
- Bounded research passes the preflighted trace path into `write_source_trace(...)`, so metadata, preflight, and the written sidecar all use the same path.
- Existing overwrite protection remains in place; exact generated path collisions still fail clearly.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Same-second exact collisions can still fail if the generated path already exists. This preserves no-overwrite safety.
- No cleanup for older generic trace sidecars was added.

## Follow-Up Work

- Consider deterministic suffix retry behavior only if same-second collisions become common.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality or alter behavioral guidance.
- Did not change research semantics, DB schema, Chroma/indexing behavior, UI, scheduler/autonomy, open-loop creation, prompts, guidance, or Moltbook write behavior.
- Preserved source trace provenance and no-overwrite safety.
