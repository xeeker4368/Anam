## Summary

Added conditional recent artifact awareness for artifact-related chat prompts. The chat path now injects a bounded, metadata-only list of recent artifacts for the current user when the prompt asks about uploads, files, documents, attachments, or artifacts.

## Files Changed

- `tir/artifacts/service.py`
- `tir/engine/artifact_context.py`
- `tir/api/routes.py`
- `tests/test_artifact_context.py`
- `tests/test_api_agent_stream.py`

## Behavior Changed

- Added `list_recent_artifacts_for_user(...)` with Python-side metadata ownership filtering.
- Added recent artifact intent detection for upload/file/artifact/document/attachment prompts.
- Added compact recent artifact context formatting using source role and origin display helpers.
- `/api/chat/stream` now injects recent artifact metadata as a system message before the current user message only when artifact intent is detected.
- Debug output now includes recent artifact context metadata and character counts:
  - `recent_artifact_context`
  - `prompt_breakdown.recent_artifact_context_chars`
  - `prompt_breakdown.artifact_context_chars`

## Context Format

The injected block is metadata-only and shaped like:

```text
Recent artifacts available as uploaded source material:
- Example.md, type=uploaded_file, role=Uploaded source, origin=User upload, indexing=indexed, status=active, created=..., id=12345678
```

It does not include file contents, raw metadata JSON, hashes, absolute paths, secrets, or authority wording.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifact_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py tests/test_artifacts.py -v`
- `git diff --check`

## Known Limitations

- Injection is intent-based and may miss very vague follow-ups that do not mention uploads, files, artifacts, attachments, or documents.
- User filtering scans a bounded recent artifact list in Python rather than querying JSON metadata in SQLite.
- The context is limited to the latest five visible artifacts and capped to 2,000 characters.

## Follow-Up Work

- Consider conversation-aware upload linkage so recent artifact context can be scoped more precisely to the active conversation.
- Consider a read-only `list_recent_artifacts` tool if explicit artifact listing becomes useful outside passive context.
- Consider a later frontend debug display refinement if nested debug fields are hard to inspect.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Preserved artifact source-role/origin framing.
- Did not inject file contents or promote uploaded artifacts to runtime guidance, identity, or operational truth.
- Did not change DB schema, Chroma, FTS, or memory architecture.
- Did not rename `tir/`.
