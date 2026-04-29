# Artifact Creation Helper

## Summary

Added an internal helper that writes a safe workspace file and registers the corresponding artifact metadata in one operation.

## Files Changed

- `tir/artifacts/service.py`
- `tir/artifacts/__init__.py`
- `tests/test_artifacts.py`
- `changelog/2026-04-28-artifact-creation-helper.md`

## Behavior Changed

- Added `create_artifact_file(...)` as an internal-only service helper.
- The helper validates artifact type, status, title, metadata, and workspace path before writing.
- The helper writes UTF-8 text through the workspace service.
- The helper registers artifact metadata through the artifact registry service.
- Artifact metadata stores only the workspace-relative file path.
- The helper returns a stable two-key result shape with `artifact` and `file`.
- Artifact contents are not indexed, chunked, stored, or retrieved as memory.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_workspace.py tests/test_db.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- If file write succeeds but DB insert fails, an orphan workspace file may remain.
- No LLM tools, API routes, or UI.
- No delete, rename, move, or cleanup behavior.
- No memory indexing/chunking.

## Follow-up Work

- Add transactional cleanup or orphan reconciliation if this helper becomes part of user-visible workflows.
- Connect this helper only after workspace tools or approved backend flows need artifact creation.

## Project Anam Alignment Check

- Did not expose LLM tools.
- Did not add API routes or UI.
- Did not add memory indexing/chunking.
- Did not add open loops.
- Did not add document ingestion, web search, Moltbook, image generation, autonomy, or self-modification.
- Did not rename `tir/`.
- Did not modify `soul.md`.
