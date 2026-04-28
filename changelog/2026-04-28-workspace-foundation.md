# Workspace Foundation

## Summary

Added an internal-only workspace service with safe, bounded file operations under the configured workspace root.

## Files Changed

- `tir/workspace/__init__.py`
- `tir/workspace/service.py`
- `tests/test_workspace.py`
- `changelog/2026-04-28-workspace-foundation.md`

## Behavior Changed

- Added helpers to create the default workspace directory structure when explicitly requested.
- Added safe internal operations for listing, reading, writing, appending, and creating directories inside the configured workspace root.
- Workspace paths reject traversal, absolute paths, and symlink escapes.
- Reads and writes are UTF-8 text-only.
- No API routes, UI, LLM tools, memory indexing, document ingestion, artifact registry, or self-modification behavior were added.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_workspace.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check -- tir/workspace/__init__.py tir/workspace/service.py tests/test_workspace.py changelog/2026-04-28-workspace-foundation.md`

## Known Limitations

- No delete, rename, move, or copy operations.
- No file size limits yet.
- No binary file handling.
- No audit/event logging for workspace operations yet.
- Workspace files are not memory and are not indexed.

## Follow-up Work

- Decide tool semantics and audit traces before exposing workspace operations to the model.
- Add max read/write sizes before LLM tool exposure.
- Add artifact registry separately if workspace outputs should become durable artifact memory.

## Project Anam Alignment Check

- Did not expose workspace operations as LLM tools.
- Did not add API routes or UI.
- Did not connect workspace files to memory.
- Did not index, chunk, store, or retrieve workspace files as memory.
- Did not add web search, Moltbook, image generation, autonomy, voice, vision, artifact registry, or self-modification.
- Did not rename `tir/`.
- Did not modify `soul.md`.
