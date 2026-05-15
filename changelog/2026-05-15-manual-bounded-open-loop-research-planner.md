# Manual Bounded Open-Loop Research Planner

Added the first manual planner layer for bounded research over existing research
open loops.

- Added read-only eligibility evaluation for research open loops.
- Added deterministic next-loop selection and skipped-reason reporting.
- Added `research-open-loop-next --dry-run` with bounded summary output.
- Added planner and admin tests for eligibility, ranking, daily limits, local-day
  reset behavior, skipped reasons, and dry-run no-mutation behavior.

Deferred write-mode research execution, scheduler/autonomy, global daily cap
enforcement, Chroma indexing, web/Moltbook collection, synthesis, working
theories, review items, behavioral guidance runtime loading, and UI changes.
