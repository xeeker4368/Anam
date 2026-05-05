# Capability State Foundation

## Summary

Added a central read-only capability status layer for Project Anam so current and future capabilities are reported consistently.

## Files Changed

- `tir/ops/capabilities.py`
- `tir/ops/status.py`
- `tests/test_capabilities.py`
- `tests/test_system_status_api.py`
- `changelog/2026-05-05-capability-state-foundation.md`

## Behavior Changed

- `/api/system/capabilities` now uses central capability definitions.
- Capability entries now share a stable schema with implementation, enablement, availability, mode, approval, real-time/source-of-truth, configuration, status, reason, and notes fields.
- Current capabilities report runtime availability from the active tool registry and configuration state.
- Future capabilities are explicitly reported as disabled or staged-only.
- Moltbook token status remains boolean-only and never exposes token values.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_capabilities.py -v`
- `.pyanam/bin/python -m pytest tests/test_system_status_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_backup_restore.py tests/test_memory_audit.py -v`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Capability state is reporting-only.
- There are no UI toggles, persistence, or enforcement hooks yet.
- Tool behavior is unchanged by capability status.

## Follow-Up Work

- Add explicit capability controls only after a separate design and approval.
- Add enforcement only after reporting semantics are stable.
- Extend the System panel if richer capability details need better presentation.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience and memory architecture.
- Adds inspectable runtime state without changing tools, autonomy, DB schema, or memory behavior.
