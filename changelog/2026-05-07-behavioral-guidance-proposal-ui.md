# Behavioral Guidance Proposal API and UI Review Surface v1

## Summary

Added read/list and review-status API endpoints plus a System panel review surface for existing behavioral guidance proposals.

## Files Changed

- `tir/api/routes.py`
- `tests/test_api_behavioral_guidance.py`
- `frontend/src/App.jsx`
- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-07-behavioral-guidance-proposal-ui.md`

## Behavior Changed

- Added `GET /api/behavioral-guidance/proposals`.
- Added `PATCH /api/behavioral-guidance/proposals/{proposal_id}` for review status only.
- The API intentionally exposes only `proposed`, `approved`, `rejected`, and `archived`.
- `applied` is not exposed because applying implies deferred file mutation.
- The System panel now includes a collapsible Behavioral Guidance Proposals section.
- Operators can filter proposals and approve, reject, archive, or reopen them.
- Rejection requires an inline review reason.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_behavioral_guidance.py -v`
- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance.py -v`
- `npm --prefix frontend run lint` (passes with existing React hook dependency warnings)
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Admin enforcement is still `reviewed_by_role` text validation until full user/session role enforcement exists.
- The UI cannot create, edit, delete, or apply proposals.
- `BEHAVIORAL_GUIDANCE.md` is not modified or loaded into runtime context.

## Follow-up Work

- Add verified admin-user enforcement.
- Add explicit apply-to-file workflow only after a separate approval.
- Add AI-generated proposal creation through a future review/dream pass.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Does not modify `soul.md`.
- Keeps behavioral guidance proposal creation out of the UI.
- Does not add model tools, automation, prompt loading, or self-modification behavior.
