# Experiment Hypothesis / Observation Criteria v1

## Summary

Added a human-facing experiment framing document for Project Anam before go-live. The document defines the core hypothesis, observation criteria, weak/no-signal indicators, baseline comparison plan, review windows, and boundaries for interpreting continuity-related behavior.

## Files Changed

- `docs/EXPERIMENT_HYPOTHESIS_AND_OBSERVATION_CRITERIA.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `changelog/2026-05-22-experiment-hypothesis-observation-criteria.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation and project-state planning only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No baseline prompt set was implemented.
- No evaluation runner or transcript storage workflow was implemented.
- No runtime prompt, guidance, model, database, retrieval, research, or UI behavior was changed.

## Follow-Up Work

- Define the actual pre-go-live baseline prompt set.
- Capture clean-session baseline transcripts for the current Gemma configuration, lower-temperature Gemma, and the Qwen candidate.
- Revisit the criteria at 30, 60, and 90 days after go-live.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign a fixed personality, avatar, values, or identity.
- Preserved the distinction between Project Anam as substrate and the unnamed entity.
- Kept the document outside runtime guidance and prompt behavior.
- Preserved raw experience and source-linked evaluation as the basis for later interpretation.
