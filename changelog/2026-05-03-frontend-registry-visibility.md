# Frontend Registry Visibility

## Summary

Added minimal Web UI visibility for artifact and open-loop registry records using the existing read-only API routes.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/RegistryPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-03-frontend-registry-visibility.md`

## Behavior Changed

- The frontend now fetches artifact metadata from `GET /api/artifacts`.
- The frontend now fetches open-loop metadata from `GET /api/open-loops`.
- Desktop users can switch the right panel between Debug and Registry views.
- Mobile users have a Registry tab beside Convos, Chat, and Debug.
- Registry cards display compact metadata for artifacts and open loops.
- Loading and error states are shown for registry fetches.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `.pyanam/bin/python -m pytest tests/test_api_registry_visibility.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- Registry visibility is read-only.
- No create, edit, delete, close, or archive controls were added.
- Artifact file contents are not read or displayed.
- No UI tests were added because the project does not currently have a frontend test framework.
- Existing React hook dependency lint warnings remain.

## Follow-Up Work

- Add richer filtering when a dedicated registry inspection UI is approved.
- Add artifact/open-loop detail views only after read-only list visibility proves useful.
- Add frontend tests later if a frontend test framework is introduced.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md` or operational guidance.
- Did not change memory retrieval or indexing behavior.
- Did not expose workspace file contents.
- Preserved artifacts and open loops as inspectable substrate records without adding tools or autonomy.
