# Research Continuation Design v1

## Summary

Added a design for manually continuing prior research artifacts without treating provisional notes as final truth.

## Files Changed

- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `ROADMAP.md`
- `DECISIONS.md`
- `changelog/2026-05-13-research-continuation-design.md`

## Behavior Changed

- Documentation only.
- Research continuation is defined as a manual extension that creates a new provisional note rather than overwriting or revising the prior note.
- `ROADMAP.md` now marks Research Continuation Design v1 complete and keeps implementation as a future item.
- `DECISIONS.md` records that research continuation creates new notes and preserves prior artifacts.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No runtime code or CLI flags were implemented.
- No database schema, artifact ingestion/indexing, retrieval ranking, web search, scheduler, autonomous research, open-loop creation, review-item creation, or promotion behavior changed.

## Follow-Up Work

- Implement `--continue-artifact` dry-run support.
- Implement safe `--continue-file` fallback.
- Add continuation write and explicit registration/indexing support.
- Design disambiguated title/search continuation.
- Design explicit open-loop/review-item creation flags.
- Design working-theory promotion/supersession rules.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved research notes as provisional working research.
- Preserved source framing, lineage, and non-promotion boundaries.
- Did not mutate guidance, self-understanding, operational guidance, `soul.md`, runtime prompts, or project decisions beyond the approved decision record.
