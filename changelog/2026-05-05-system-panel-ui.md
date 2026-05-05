# Read-Only System Panel UI

## Summary

Added a read-only frontend System panel for operator visibility into backend health, memory audit status, and capability status.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-05-system-panel-ui.md`

## Behavior Changed

- Added a System option beside Debug and Registry in the desktop right panel.
- Added a System tab in the mobile tab bar.
- The System panel fetches:
  - `GET /api/system/health`
  - `GET /api/system/memory`
  - `GET /api/system/capabilities`
- The panel displays health, memory, and capability status with loading, error, and manual refresh states.
- No mutation controls were added.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- The panel does not auto-refresh.
- The panel is reporting-only and does not expose repair, checkpoint, backup, or restore controls.
- The UI depends on the existing backend status endpoints and does not perform independent service checks.

## Follow-Up Work

- Add explicit operator actions only after separate approval.
- Consider a compact visual health summary once more runtime status surfaces exist.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience and memory architecture.
- Adds read-only operator visibility without mutation endpoints, schema changes, autonomy, or secret exposure.
