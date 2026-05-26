# Bounded Scheduler / Nightly Tick v1

## Summary

Added a disabled-by-default one-shot nightly tick command. The command records a heartbeat audit row when enabled and can optionally run one model-only bounded research run-next action when both configuration and CLI flags allow it.

## Files Changed

- `config/defaults.toml`
- `tir/config.py`
- `tir/memory/db.py`
- `tir/scheduler/__init__.py`
- `tir/scheduler/nightly.py`
- `tir/admin.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_nightly_tick.py`
- `tests/test_admin.py`
- `tests/test_config.py`
- `changelog/2026-05-25-bounded-scheduler-nightly-tick-v1.md`

## Behavior Changed

- Added `[scheduler]` config with all scheduler behavior disabled by default.
- Added `nightly-tick --dry-run` and `nightly-tick --write` admin commands.
- `nightly-tick --dry-run` reports a plan and writes nothing.
- `nightly-tick --write` records one `overnight_runs` audit row only when scheduler and nightly tick config are enabled.
- Optional bounded research requires both config `allow_bounded_research=true` and CLI `--allow-bounded-research`.
- Optional bounded research calls the existing model-only `research-open-loop-run-next` path and never enables Moltbook, web, or image generation.
- Scheduler audit summaries are stored as compact JSON in the existing `overnight_runs.summary` column.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_nightly_tick.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest tests/test_config.py tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python -m pytest tests -q`
- `git diff --check`

## Known Limitations

- V1 is not a daemon, worker, or always-on scheduler.
- V1 uses the existing `overnight_runs.summary` JSON field instead of adding a dedicated scheduler table.
- Moltbook, web, image generation, open-loop creation, review items, working theory promotion, and external writes remain unavailable to the scheduler.

## Follow-Up Work

- Add launchd/cron setup documentation after manual ticks are exercised.
- Consider a dedicated scheduler audit table only if querying `overnight_runs.summary` becomes insufficient.
- Revisit global daily caps after bounded one-action ticks have been observed.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved the Project Anam/entity distinction.
- Added no daemon, broad autonomy, external writes, Moltbook/web/image scheduling, prompt changes, guidance loading, DB schema migration, UI changes, or self-modification behavior.
