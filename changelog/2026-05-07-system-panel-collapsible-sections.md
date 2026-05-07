# Collapsible System Panel Sections

## Summary

Made the major System panel sections collapsible so operator status areas remain easier to scan as the panel grows.

## Files Changed

- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-07-system-panel-collapsible-sections.md`

## Behavior Changed

- Health, Memory, Capabilities, and Review Queue sections now have clickable headers.
- Health is expanded by default.
- Memory and Capabilities are collapsed by default.
- Review Queue is expanded by default when open items are present and otherwise collapsed.
- Section headers show compact summaries such as health status, memory counts, capability count, and open review count.

## Tests/Checks Run

- `npm --prefix frontend run lint` (passes with existing React hook dependency warnings)
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Collapse state is local to the component and is not persisted across reloads.
- Review Queue default expansion updates only when the open-item boundary changes.

## Follow-up Work

- Add persisted operator panel preferences if repeated usage shows that section state should survive reloads.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Does not change backend behavior, APIs, tools, memory architecture, or review queue logic.
- Keeps operator controls explicit and inspectable.
