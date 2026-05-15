# Research Open-Loop Design

## Summary

Added a design for research open loops as source-linked unresolved research questions that can preserve research continuity without becoming beliefs, instructions, guidance, self-understanding, project decisions, or working theories.

## Files Changed

- `docs/RESEARCH_OPEN_LOOP_DESIGN.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`

## Behavior Changed

- No runtime behavior changed.
- No database schema changed.
- No retrieval, research, journal, prompt, model, UI, or guidance behavior changed.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- Runtime open-loop creation is not implemented.
- Review-item creation remains deferred.
- Working theories and synthesis records remain separate future design work.
- Open loops are not indexed into ChromaDB by default in this design.

## Follow-Up Work

- Implement Research Open-Loop Runtime v1 with preview-first explicit creation from registered research artifacts.
- Design review-item creation separately.
- Design working theory/synthesis records separately.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not assign personality or identity.
- Did not edit `soul.md`.
- Did not re-enable behavioral guidance runtime loading.
- Preserved research as provisional and source-linked.
- Kept open loops as unresolved questions rather than conclusions or instructions.
