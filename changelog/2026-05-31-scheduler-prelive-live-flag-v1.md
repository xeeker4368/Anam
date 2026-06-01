# Scheduler pre_live/live config flag + clarifying comments — v1

Date: 2026-05-31

## Summary

The nightly scheduler hardcoded `"pre_live_or_live": "pre_live"` in
`_base_result()`, so every audit row recorded `pre_live` regardless of the
scheduler's actual operating state, with no way to mark a tick as live. This
patch adds a `go_live` scheduler config flag (with an `ANAM_SCHEDULER_GO_LIVE`
env override, mirroring the existing `SCHEDULER_*` pattern) and uses it to set
the recorded `pre_live_or_live` label. It also adds clarifying comments. No
scheduling behavior changes — only the recorded label and comments.

## Files changed

- `tir/config.py`
  - Added `"go_live": False` to `_FALLBACK_CONFIG["scheduler"]`.
  - Added `SCHEDULER_GO_LIVE = _env_bool("ANAM_SCHEDULER_GO_LIVE", ...)`,
    copying the shape of the existing `SCHEDULER_ENABLED` constant.
- `config/defaults.toml`
  - Added `go_live = false` under `[scheduler]`.
- `tir/scheduler/nightly.py`
  - Imported `SCHEDULER_GO_LIVE` alongside the other `SCHEDULER_*` imports.
  - `_scheduler_config()` now returns `"go_live": bool(SCHEDULER_GO_LIVE)`.
  - `_base_result()` now sets
    `"pre_live_or_live": "live" if config["go_live"] else "pre_live"`.
  - Added a comment that a heartbeat-only tick keeps `action_count == 0` and
    that this completed-with-zero-actions baseline is expected, not an error.
  - Added a comment noting `allow_moltbook` / `allow_image_generation` are
    reserved for deferred capabilities and remain disabled for v1.
- `tests/test_nightly_tick.py`
  - Added a `go_live=False` parameter to `_set_scheduler_config()` and a
    matching `monkeypatch.setattr(nightly_mod, "SCHEDULER_GO_LIVE", go_live)`.
  - Added `test_default_tick_records_pre_live` and `test_go_live_tick_records_live`.

## Behavior changed

- When `go_live` is false (default, unset, or `ANAM_SCHEDULER_GO_LIVE=false`):
  `_base_result()` yields `pre_live_or_live == "pre_live"` and the audit-derived
  `pre_live == True`. Identical to prior behavior.
- When `go_live` is true (via `[scheduler] go_live` or `ANAM_SCHEDULER_GO_LIVE`):
  `pre_live_or_live == "live"` and the audit-derived `pre_live == False`.
- `_scheduler_config()` now exposes `go_live` in the `config` dict surfaced on
  every result.
- No change to action gating, bounded-research flow, max-actions enforcement,
  enable gating, or any scheduling/automation behavior. `_save_audit_row`'s
  derivation logic is unchanged; it simply reflects the new label.

## Tests / checks run

- Full suite: `python -m pytest -q` → **838 passed** (836 prior + 2 new),
  133 pre-existing deprecation warnings (chromadb / FastAPI `on_event`),
  unrelated to this change.
- New tests assert both the in-result label and the persisted audit-row
  `pre_live` value for the default (pre_live) and go-live (live) states.

## Known limitations

- `go_live` is purely a labeling flag in this patch: it records pre_live vs live
  in audit rows but does not itself gate, enable, or alter any action behavior.
- The `ANAM_SCHEDULER_GO_LIVE` env var is intentionally not added to
  `tests/test_config.py`'s `CONFIG_ENV_VARS` cleanup list, matching the existing
  `SCHEDULER_*` convention (those flags are resolved at import time and the
  scheduler tests monkeypatch the module constants directly).

## Follow-up work

- Out of scope here and deferred to separate patches: greeting dedup, the
  no-persist warning log / no-persist branch, scheduler automation
  (launchd/cron), and enabling the deferred capabilities
  (`allow_moltbook` / `allow_image_generation` / `allow_web`).
- A future patch could let `go_live` actually gate live-mode side effects once
  those capabilities are designed.

## Project Anam alignment check

1. Assign the entity a name? No.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No.
4. Preserve raw experience? Yes — audit rows still record raw tick outcomes.
5. Are derived artifacts traceable? Yes — `pre_live` is derived from the
   recorded `pre_live_or_live` label, now driven by an inspectable config flag.
6. Are tool calls recorded? Unaffected; tick actions still recorded as before.
7. Are created artifacts remembered? Unaffected.
8. Is context construction inspectable? Yes — `go_live` is surfaced in the
   result `config` dict and the persisted audit summary.
9. Does this make autonomy more cumulative? Neutral — clearer audit labeling.
10. Preserve the Anam/entity distinction? Yes.
11. Require a migration? No — no schema change; audit summary is JSON and the
    `pre_live` field already existed.
12. Tests run? Full suite (838 passed) including two new state-coverage tests.
13. Change core substrate behavior unnecessarily? No — label/comments only.
14. Add external dependencies/services? No.
15. Preserve workspace vs self-modification distinction? Yes — unaffected.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
