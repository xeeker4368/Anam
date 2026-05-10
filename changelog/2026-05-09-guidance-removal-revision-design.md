# Behavioral Guidance Removal / Revision Design

## Summary

Added a design-only document for future behavioral guidance removal, revision, retirement, and supersession mechanics.

## Files Changed

- `docs/BEHAVIORAL_GUIDANCE_REVISION_DESIGN.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `changelog/2026-05-09-guidance-removal-revision-design.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- Current apply workflow remains addition-only.
- No guidance-entry parser or planner exists yet.
- No dry-run diff/plan behavior exists for removal or revision.
- No runtime loader changes were made.
- No schema or proposal service changes were made.

## Follow-Up Work

- Add guidance-entry parser and planner for active and retired sections.
- Add dry-run diff/plan support for removal and revision proposals.
- Implement removal apply by retiring active guidance.
- Implement revision apply by retiring old guidance and appending revised active guidance.
- Add runtime loader tests proving retired guidance is never loaded as active guidance.
- Add scope-aware supersession handling.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Preserves raw experience and guidance history.
- Keeps behavioral guidance AI-proposed, admin-reviewed, explicit, and traceable.
- Preserves the distinction between Project Anam as substrate and the unnamed AI entity.
- Does not change schema, runtime context, guidance files, or memory architecture.
