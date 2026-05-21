# Moltbook Source Preview Runtime v1

## Summary

Added a standalone read-only Moltbook source preview command that produces compact provenance/source trace JSON for search and feed previews.

## Files Changed

- `tir/research/moltbook_sources.py`
- `tir/admin.py`
- `tests/test_moltbook_source_collection.py`
- `tests/test_admin.py`
- `changelog/2026-05-21-moltbook-source-preview-runtime-v1.md`

## Behavior Changed

- Added `python -m tir.admin moltbook-source-preview --query "..." --limit 10`.
- Added `python -m tir.admin moltbook-source-preview --feed --limit 10`.
- Added optional `--write-trace` sidecar output under `workspace/research/source-traces/`.
- Output is compact source trace JSON and omits spam by default.
- No bounded research, research note, open-loop, artifact registration, DB schema, Chroma indexing, scheduler, prompt, guidance, or UI behavior changed.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest`

## Known Limitations

- Comments are not collected in v1.
- Full post body reads are not supported in v1.
- Only query search and global feed preview are supported.
- Source traces are not registered as artifacts and are not indexed.

## Follow-Up Work

- Consider explicit selected post reads in a later patch.
- Consider comments with a small opt-in limit in a later patch.
- Integrate compact Moltbook source collection into bounded research only after preview behavior is validated.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved raw source/provenance boundaries.
- Kept Moltbook read-only.
- Preserved the distinction between source text and interpretation.
- Did not index raw Moltbook traces into ChromaDB.
- Did not change self-modification, scheduler, prompt runtime, guidance, or bounded research behavior.
