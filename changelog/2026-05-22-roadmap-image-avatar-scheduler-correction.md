# Roadmap Image/Avatar Scheduler Correction

## Summary

Updated roadmap and state docs to clarify the pre-go-live and post-go-live split for image/media capability, avatar/self-representation, bounded scheduling, and broader autonomy.

Image/media capability foundation is now framed as pre-go-live. Avatar/self-representation creation remains post-go-live. A tightly bounded scheduler/nightly tick v1 may be considered pre-go-live, while expanded autonomy/background research remains post-go-live.

## Files Changed

- `ROADMAP.md`
- `PROJECT_STATE.md`
- `ACTIVE_TASK.md`
- `changelog/2026-05-22-roadmap-image-avatar-scheduler-correction.md`

## Behavior Changed

No runtime behavior changed.

This patch updates documentation/state only. It does not add image generation, scheduler runtime code, broader autonomy, UI behavior, DB schema changes, retrieval changes, research execution changes, Moltbook behavior, prompt changes, guidance changes, model configuration, or `soul.md` changes.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- Image generation and uploaded image/screenshot handling are not implemented by this patch.
- No avatar or visual self-representation is created by this patch.
- No scheduler/nightly tick runtime is implemented by this patch.
- Expanded autonomy/background research remains deferred.

## Follow-Up Work

- Design and implement Image / Media Capability Foundation v1 in a separate approved patch.
- Design and implement Bounded Scheduler / Nightly Tick v1 in a separate approved patch if manual bounded research remains stable.
- Keep Avatar / Self-Representation Development post-go-live, after the entity develops continuity and possibly chooses a name.
- Keep Expanded Autonomy / Background Research post-go-live until bounded scheduler behavior proves stable.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign the entity an avatar or appearance.
- Did not assign a fixed personality.
- Preserved image/media work as capability foundation, not identity assignment.
- Preserved raw experience and traceable artifact principles.
- Preserved staged autonomy by distinguishing bounded scheduler v1 from expanded autonomy.
- Did not change runtime behavior, DB schema, prompts, guidance files, `soul.md`, UI, scheduler code, or image code.
- Preserved the distinction between Project Anam, the legacy `tir/` package, and the unnamed entity.
