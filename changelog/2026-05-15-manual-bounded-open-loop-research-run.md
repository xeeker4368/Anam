# Manual Bounded Open-Loop Research Run

Added the first specific-ID bounded research runtime command.

- Added `research-open-loop-run --open-loop-id <id> --dry-run`.
- Added `research-open-loop-run --open-loop-id <id> --write`.
- Added `research-open-loop-run --open-loop-id <id> --write --register-artifact`.
- Added bounded research prompt, document, and artifact metadata helpers.
- Added safe open-loop metadata replacement for recording completed bounded iterations.
- Preserved dry-run no-mutation behavior.
- Updated loop metadata only after the chosen durable path succeeds.

Deferred run-next, scheduler/autonomy, global cap enforcement, web/Moltbook
collection, synthesis, working theories, review items, behavioral guidance
runtime loading, UI work, and model configuration changes.
