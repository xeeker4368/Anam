# Read-Only Registry API Visibility

## Summary

Added small read-only API visibility for the existing artifact and open-loop registries.

## Files Changed

- `tir/api/routes.py`
- `tests/test_api_registry_visibility.py`
- `changelog/2026-05-03-read-only-registry-api-visibility.md`

## Behavior Changed

- Added `GET /api/artifacts` for listing artifact metadata.
- Added `GET /api/artifacts/{artifact_id}` for fetching one artifact metadata record.
- Added `GET /api/open-loops` for listing open-loop metadata.
- Added `GET /api/open-loops/{open_loop_id}` for fetching one open-loop metadata record.
- Invalid registry filters return HTTP 400 instead of leaking validation failures as server errors.
- Missing individual artifact/open-loop records return HTTP 404.
- Artifact API responses return metadata only and do not read workspace file contents.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_registry_visibility.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifacts.py tests/test_open_loops.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- Routes are read-only and do not provide create/update/delete behavior.
- Artifact file contents remain unavailable through these endpoints.
- No UI, LLM tool, workspace browser, auth, or ownership scoping was added in this patch.

## Follow-Up Work

- Add UI inspection for artifacts and open loops when the frontend visibility slice is approved.
- Add write routes only after explicit API design approval.
- Add ownership/scoping rules later if Project Anam moves beyond the current local/single-user assumption.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md` or operational guidance.
- Did not change memory retrieval or indexing behavior.
- Preserved artifacts and open loops as inspectable substrate records without making them LLM tools or autonomous behavior.
