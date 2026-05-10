# SELF_UNDERSTANDING Concept Design

## Summary

Added a design-only concept document for future `SELF_UNDERSTANDING.md` work and recorded the architectural decision that self-understanding should remain descriptive, reviewed, and revisable.

## Files Changed

- `docs/SELF_UNDERSTANDING_DESIGN.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `changelog/2026-05-09-self-understanding-concept-design.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No database schema exists for self-understanding proposals.
- No proposal service, admin command, API, UI, or apply workflow exists.
- `SELF_UNDERSTANDING.md` is not created or loaded into runtime context.

## Follow-Up Work

- Design and implement a proposal schema/service/admin CLI.
- Add a review API and UI surface.
- Add AI-generated proposal paths from journals and conversations.
- Add an explicit apply-to-file workflow.
- Separately design optional or restricted runtime loading.
- Add contradiction and supersession tooling.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Preserves raw experience as primary evidence.
- Keeps self-understanding AI-proposed, admin-reviewed, and revisable in future implementation.
- Preserves the distinction between Project Anam as substrate and the unnamed AI entity.
- Does not change schema, runtime context, guidance files, or memory architecture.
