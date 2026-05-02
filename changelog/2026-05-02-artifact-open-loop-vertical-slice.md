# Artifact Open Loop Vertical Slice

## Summary

Added an internal helper that creates a workspace artifact file and optionally creates a linked open loop in one flow.

## Files Changed

- `tir/artifacts/service.py`
- `tir/artifacts/__init__.py`
- `tir/open_loops/service.py`
- `tir/open_loops/__init__.py`
- `tests/test_artifacts.py`
- `changelog/2026-05-02-artifact-open-loop-vertical-slice.md`

## Behavior Changed

- `create_artifact_file_with_open_loop(...)` can now create a workspace file, register it as an artifact, and optionally create an `unfinished_artifact` open loop linked by `related_artifact_id`.
- Open loop creation remains opt-in with `create_open_loop=True`.
- Open-loop validation runs before file/artifact creation for expected validation failures.
- The helper returns a stable `{artifact, file, open_loop}` result shape.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_open_loops.py -v`
- `.pyanam/bin/python -m pytest tests/test_workspace.py tests/test_db.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- A true DB failure during open-loop insertion after artifact/file creation can still leave an artifact without the requested loop. Full rollback or transactional file cleanup is out of scope for this minimal internal slice.
- The helper is internal-only. It is not exposed as an LLM tool, API route, or UI feature.

## Follow-up Work

- Consider transactional cleanup if open-loop insertion failures become operationally likely.
- Later vertical slices can expose safe workflow through API/UI or tools only after explicit approval.

## Project Anam Alignment Check

- Did not add DB schema.
- Did not add API routes.
- Did not add UI.
- Did not add LLM tools.
- Did not add new registries.
- Did not add web search, Moltbook, image generation, autonomy, or self-modification.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not change memory retrieval behavior.
- Did not touch `data/prod` files.
