# Go-Live Reset Runbook v1

## Summary

Added a design/runbook document for the future go-live wipe/reset process. The runbook defines the operator procedure, wipe/preserve boundaries, required guardrails, future command shape, post-reset verification checklist, and tests needed for a later destructive implementation patch.

## Files Changed

- `docs/GO_LIVE_RESET_RUNBOOK.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `changelog/2026-05-22-go-live-reset-runbook-v1.md`

## Behavior Changed

No runtime behavior changed. This patch is documentation/state planning only.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No reset command was implemented.
- No data, workspace files, Chroma data, or database rows were deleted.
- Backup verification enforcement and reset audit writing are design-only in this patch.

## Follow-Up Work

- Implement `go-live-reset --dry-run`.
- Implement destructive `go-live-reset` behind explicit backup/verification/confirmation guardrails.
- Implement `go-live-reset --verify-clean`.
- Add tests for dry-run, refusal paths, wipe/preserve behavior, audit output, and clean-state verification.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved the Project Anam/entity distinction.
- Preserved current pre-live runtime data for development/testing.
- Did not change runtime code, DB mutation code, Chroma reset behavior, workspace deletion behavior, prompts, guidance files, `soul.md`, model config, auth, UI, research behavior, or Moltbook/web behavior.
