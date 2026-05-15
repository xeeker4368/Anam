# Course-Correction State Sync

## Summary

Updated project state after the low-risk pre-go-live course-correction batch.

## Files Changed

- `ACTIVE_TASK.md`
- `PROJECT_STATE.md`
- `ROADMAP.md`

## Behavior Changed

- No runtime behavior changed.
- The active task now points to Research Open-Loop / Review-Item Design v1.
- The roadmap records completed low-risk prompt/source-framing course-correction work and preserves the remaining pre-go-live plan.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- This patch does not implement research open-loop/review-item creation.
- This patch does not implement web source collection, working theories, household multi-user, media/image artifacts, Moltbook changes, canary observation, UI polish, or go-live reset/hardening.

## Follow-Up Work

- Start Research Open-Loop / Review-Item Design v1.
- Continue the remaining pre-go-live tracks as separate approved patches.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not assign personality or identity.
- Did not edit `soul.md`.
- Did not re-enable behavioral guidance runtime loading.
- Preserved research as provisional and explicitly deferred promotion paths.
