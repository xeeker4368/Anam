# Bounded / Scheduled Research Design

## Summary

Added a design-only plan for manual bounded research against existing research open loops and future scheduled research.

## Files Changed

- `docs/BOUNDED_SCHEDULED_RESEARCH_DESIGN.md`
- `docs/RESEARCH_OPEN_LOOP_DESIGN.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `changelog/2026-05-15-bounded-scheduled-research-design.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation and state sync only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No bounded research planner is implemented yet.
- No scheduler, web source collection, Moltbook source collection, review-item creation, or working-theory path is implemented.

## Follow-Up Work

- Implement Manual Bounded Open-Loop Research Planner v1.
- Later implement one-loop research execution, optional registration, cap accounting, source collection, and synthesis paths through separate approved patches.

## Project Anam Alignment Check

- Does not assign the entity a name or personality.
- Keeps research provisional and source-linked.
- Keeps Behavioral Guidance runtime loading dormant.
- Does not promote research to truth, guidance, self-understanding, working theories, or project decisions.
