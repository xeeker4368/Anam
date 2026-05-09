# Behavioral Guidance Proposal UI Action Cleanup

## Summary

Updated the Behavioral Guidance Proposals review UI so each proposal shows only valid review actions for its current status.

## Files Changed

- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`

## Behavior Changed

- Proposed proposals show Approve, Reject, and Archive.
- Approved, rejected, and archived proposals show Reopen only.
- The rejection reason textarea appears only when rejecting a proposed item.
- Rejection still requires a non-empty reason.
- Existing review decision reasons remain read-only in proposal details.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Approve/archive do not currently collect optional review reasons in the UI.
- This is a frontend-only action cleanup and does not add backend role/session enforcement.

## Follow-Up Work

- Add explicit optional reason affordances for approve/archive only if operators need that workflow.
- Revisit action display when apply-to-file behavior is implemented.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not assign a fixed personality.
- Keeps behavioral guidance review admin-controlled.
- Does not modify `BEHAVIORAL_GUIDANCE.md` or runtime prompt loading.
