# Review Queue UI v1

## Summary

Added a simple operator-facing Review Queue section to the System panel.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-07-review-queue-ui.md`

## Behavior Changed

- The System panel now loads review queue items from `GET /api/review`.
- Operators can filter review items by status, category, and priority.
- Operators can manually create review items through `POST /api/review`.
- Operators can update item status through `PATCH /api/review/{item_id}`.
- The UI exposes no delete, title edit, description edit, model tool, scheduler, or automation controls.

## Tests/Checks Run

- `npm --prefix frontend run lint` (passes with existing React hook dependency warnings)
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- The UI only supports manual item creation and status changes.
- There is no delete action, detail editor, assignment workflow, pagination control, or model-facing queue integration.

## Follow-up Work

- Add richer filtering or pagination if the queue grows.
- Add read-only System panel summaries once operational usage clarifies which counts are useful.
- Consider a dedicated review panel only if the System panel becomes too dense.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience and existing memory architecture.
- Keeps review queue use operator-controlled.
- Does not add autonomous behavior, model tool access, scheduler work, or memory indexing.
