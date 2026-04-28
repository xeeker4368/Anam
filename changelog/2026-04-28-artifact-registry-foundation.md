# Artifact Registry Foundation

## Summary

Added an internal-only artifact registry for tracking metadata about workspace outputs without storing artifact contents in SQLite or indexing artifacts as memory.

## Files Changed

- `tir/memory/db.py`
- `tir/artifacts/__init__.py`
- `tir/artifacts/service.py`
- `tests/test_db.py`
- `tests/test_artifacts.py`
- `changelog/2026-04-28-artifact-registry-foundation.md`

## Behavior Changed

- Added a working-db-only `artifacts` table and indexes.
- Added internal artifact service operations:
  - `create_artifact(...)`
  - `get_artifact(artifact_id)`
  - `list_artifacts(...)`
  - `update_artifact_status(artifact_id, status)`
- Artifact paths are optional.
- Supplied artifact paths are validated through workspace safety helpers and stored as workspace-relative paths.
- Artifact contents remain in workspace/filesystem or external systems, not SQLite.
- Artifact metadata is not indexed, chunked, stored, or retrieved as memory.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_workspace.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check -- tir/memory/db.py tir/artifacts/__init__.py tir/artifacts/service.py tests/test_db.py tests/test_artifacts.py changelog/2026-04-28-artifact-registry-foundation.md`

## Known Limitations

- No delete operations.
- No broad arbitrary update API.
- No LLM tools, API routes, or UI.
- No artifact content reads.
- No memory indexing/chunking.

## Follow-up Work

- Add artifact creation hooks when workspace tools are later exposed.
- Add artifact event/audit traces before model-driven artifact creation.
- Add optional artifact-memory indexing only through a later explicit ingestion step.

## Project Anam Alignment Check

- Did not expose LLM tools.
- Did not add API routes or UI.
- Did not add memory indexing/chunking.
- Did not read artifact file contents.
- Did not add document ingestion, web search, Moltbook, image generation, autonomy, or self-modification.
- Did not rename `tir/`.
- Did not modify `soul.md`.
