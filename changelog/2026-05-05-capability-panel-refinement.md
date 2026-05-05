# Capability Panel Refinement

## Summary

Updated the read-only System panel so capabilities render from the richer central capability schema as grouped compact cards.

## Files Changed

- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-05-capability-panel-refinement.md`

## Behavior Changed

- Capabilities now render from `Object.values(capabilities)` instead of a hardcoded row list.
- Capabilities are grouped into:
  - Active / Available
  - Config Needed / Unavailable
  - Planned / Not Implemented
  - Restricted / Requires Approval
- Each capability card shows status, mode, enabled/disabled, availability, configuration, approval, real-time/source-of-truth, reason, and notes where available.
- No toggle or mutation controls were added.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- The panel is still read-only and does not enforce capability state.
- Grouping is frontend presentation only.
- No manual browser verification was performed yet.

## Follow-Up Work

- Add operator controls only after a separate capability-control design.
- Consider frontend tests if a test framework is introduced later.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience and memory architecture.
- Adds read-only operator clarity without changing APIs, tool behavior, autonomy, or secrets handling.
