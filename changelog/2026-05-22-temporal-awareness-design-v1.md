# Temporal Awareness Design v1

## Summary

Added a design-only document for temporal awareness and temporal context framing across memory, retrieval, research notes, journals, open loops, source traces, and future working theories.

## Files Changed

- `docs/TEMPORAL_AWARENESS_DESIGN.md`
- `ROADMAP.md`
- `changelog/2026-05-22-temporal-awareness-design-v1.md`

## Behavior Changed

- No runtime behavior changed.
- No prompts, tests, retrieval scoring, database schema, Chroma behavior, research generation, Moltbook/web behavior, guidance files, `soul.md`, model configuration, or UI behavior changed.
- Roadmap now tracks Temporal Awareness Design v1 as a research/provenance design item.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- Temporal labels are design-only and are not yet generated in retrieved-memory headers or context debug output.
- No go-live marker, project-phase computation, stale/superseded inference, or working-theory integration is implemented.

## Follow-Up Work

- Add runtime temporal labels to retrieved-memory headers and context debug output in a separate approved patch.
- Define any future temporal ranking, salience, aging, or stale-candidate behavior separately and make it debug-visible.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Keeps temporal labels as metadata/context aids, not truth or hidden ranking.
- Preserves raw timestamps, raw experience, old records, and the Project Anam/entity distinction.
