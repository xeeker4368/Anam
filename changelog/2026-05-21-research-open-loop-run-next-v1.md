# Research Open-Loop Run-Next v1

## Summary

Added `research-open-loop-run-next`, a convenience command that selects the next eligible manual bounded research open loop with the existing planner and runs it through the existing bounded research runner.

## Files Changed

- `tir/research/bounded.py`
- `tir/admin.py`
- `tests/test_research_bounded.py`
- `tests/test_admin.py`
- `changelog/2026-05-21-research-open-loop-run-next-v1.md`

## Behavior Changed

- Added `run_next_bounded_research_open_loop(...)` as a thin planner-plus-runner helper.
- Added admin command `research-open-loop-run-next`.
- Supports dry-run, write, and write/register modes.
- Supports the existing explicit Moltbook source trace flags.
- Reuses existing planner ranking, bounded research execution, Moltbook source trace behavior, artifact registration, indexing, and metadata update behavior.
- If no eligible loop exists, the command prints planner-style no-op output and does not call the runner.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- No scheduler or autonomous execution was added.
- No global daily cap enforcement was added.
- The command runs at most one selected open loop.

## Follow-Up Work

- Consider scheduler integration only after a separate autonomy design.
- Consider global cap enforcement in a dedicated bounded research policy patch.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality or alter behavioral guidance.
- Did not change DB schema, Chroma behavior beyond existing research note indexing, UI, scheduler/autonomy, open-loop creation, review items, working theories, or Moltbook write behavior.
- Preserved the manual, explicit bounded research path.
