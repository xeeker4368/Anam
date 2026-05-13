# Manual Research Cycle Design

## Summary

Added a design-only document for a future manual, user-triggered research cycle that produces provisional research artifacts with explicit consumption paths.

## Files Changed

- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `changelog/2026-05-09-manual-research-cycle-design.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No research CLI exists yet.
- No research artifact writer exists yet.
- No research artifact registration or indexing path was implemented.
- Web research is explicitly deferred.
- Open-loop and review-item creation remain future optional behavior.

## Follow-Up Work

- Add CLI dry-run that generates structured Markdown.
- Add `--write` to create files under `workspace/research/`.
- Add `--register-artifact` to register and index with `source_type=research`.
- Add research retrieval source framing.
- Add optional open-loop and review-item creation.
- Design bounded web source collection before adding `--use-web`.
- Design a future working-theory proposal path.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Preserves raw experience and treats research conclusions as provisional.
- Keeps research separate from behavioral guidance, self-understanding, runtime prompt guidance, and project decisions.
- Preserves the distinction between Project Anam as substrate and the unnamed AI entity.
- Does not change schema, runtime context, guidance files, or memory architecture.
