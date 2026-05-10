# Guidance Scoping Design

## Summary

Added a design-only document for future behavioral guidance scoping by user, channel, context, source type, applicability, and supersession.

## Files Changed

- `docs/GUIDANCE_SCOPING_DESIGN.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `changelog/2026-05-09-guidance-scoping-design.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No database schema changes were made.
- No runtime filtering or context loading changes were made.
- Proposal services do not yet produce or validate scope fields.
- Apply-to-file behavior does not yet emit scope blocks.
- Existing unscoped guidance remains interpreted as global/default.

## Follow-Up Work

- Add proposed scope metadata to AI-generated behavioral guidance proposals.
- Add admin review/edit support for proposal scope.
- Add deterministic scope blocks to applied Markdown guidance entries.
- Add scoped runtime extraction and filtering with debug visibility.
- Add conflict, supersession, removal, and revision mechanics for scoped guidance.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Preserves raw experience as the evidence base for future guidance.
- Keeps behavioral guidance AI-proposed, admin-reviewed, explicit, and traceable.
- Preserves the distinction between Project Anam as substrate and the unnamed AI entity.
- Does not change schema, runtime context, guidance files, or memory architecture.
