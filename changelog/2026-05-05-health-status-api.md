# Health and Status API Foundation

## Summary

Added read-only system status endpoints for Project Anam runtime health, memory integrity, and capability visibility.

## Files Changed

- `tir/ops/status.py`
- `tir/api/routes.py`
- `tests/test_system_status_api.py`
- `changelog/2026-05-05-health-status-api.md`

## Behavior Changed

- Added `GET /api/system/health`.
- Added `GET /api/system/memory`.
- Added `GET /api/system/capabilities`.
- Runtime health reports DB existence/status, Chroma count best-effort, latest backup metadata, external configuration presence, and skill/tool counts.
- Memory status wraps the existing audit helper without mutation.
- Capability status reports current implemented tools and explicitly disabled future capabilities.
- Existing `GET /api/health` remains unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_system_status_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_memory_audit.py -v`
- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `git diff --check`

## Known Limitations

- SearXNG status reports configuration only and does not perform a live network check.
- Chroma count is best-effort and may report a structured error.
- Capability status is reporting-only and does not enforce routing or policy.

## Follow-Up Work

- Add frontend operator panels that consume these endpoints.
- Add optional bounded live checks for external services only if useful.
- Add status for future upload/research/reflection systems when implemented.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience and memory architecture.
- Adds read-only operator visibility without mutation endpoints, schema changes, UI changes, or autonomy.
