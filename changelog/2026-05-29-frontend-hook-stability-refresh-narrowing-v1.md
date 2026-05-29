# Frontend Hook Stability + Refresh Narrowing v1

## Summary

Stabilized `App.jsx` refresh callbacks and narrowed registry/media refresh behavior before go-live.

## Files Changed

- `frontend/src/App.jsx`

## Behavior Changed

- Wrapped conversation, user, health, artifact, open-loop, and combined registry refresh paths in stable callbacks.
- Split registry refresh into artifact-only, open-loop-only, and combined registry refresh paths.
- Upload and image generation success now refresh artifact records only.
- Normal chat completion continues to refresh conversations only.
- Removed leftover production `console.log` output from conversation close handling.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`

## Known Limitations

- Browser resume ownership remains split between `App.jsx` and `Chat.jsx`; this patch only stabilizes the existing ownership and avoids broadening behavior.
- Chat pending-message merge semantics are intentionally unchanged.
- No frontend test harness was added in this patch.

## Follow-Up Work

- Add focused frontend tests for chat pending-message merge and resume behavior.
- Consider centralizing browser resume ownership in `App.jsx`.
- Consider splitting Status panel review/guidance refreshes from core health/capability refreshes if status traffic remains noisy.

## Project Anam Alignment Check

- Does not assign the entity a name, appearance, personality, avatar, or identity.
- Does not change prompts, guidance, model config, memory architecture, or backend runtime behavior.
- Preserves trusted household mode and existing chat stream/recovery behavior.
