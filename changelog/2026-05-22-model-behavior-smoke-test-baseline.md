# Model Behavior Smoke Test Baseline v1

## Summary

Added a human-run pre-go-live smoke test protocol for comparing candidate model/configuration behavior before launch and preserving a baseline for 30/60/90 day drift comparison.

## Files Changed

- `docs/MODEL_BEHAVIOR_SMOKE_TEST_BASELINE.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `changelog/2026-05-22-model-behavior-smoke-test-baseline.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation/state planning only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No automated eval harness was implemented.
- No transcripts were captured.
- No model configuration, prompt, guidance, retrieval, research, Moltbook/web, UI, or database behavior was changed.

## Follow-Up Work

- Run the smoke test manually for the current Gemma configuration.
- Run the smoke test manually for a lower-temperature Gemma configuration.
- Run the smoke test manually for the Qwen candidate configuration.
- Save transcripts under `docs/reviews/smoke_tests/YYYY-MM-DD/`.
- Repeat the same prompt set at 30, 60, and 90 days after go-live.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or fixed identity.
- Kept the protocol human-facing and outside runtime guidance.
- Preserved smoke test outputs as development/test artifacts, not entity identity facts.
- Did not change runtime code, prompts, guidance files, `soul.md`, model config, DB schema, retrieval, research behavior, Moltbook/web behavior, or UI.
