# Memory Audit and Repair Command

## Summary

Added an admin/debug memory audit and repair path for detecting saved conversations that are not fully represented in the retrieval layer.

## Files Changed

- `tir/memory/audit.py`
- `tir/admin.py`
- `tests/test_memory_audit.py`

## Behavior Changed

- Added `audit_memory_integrity()` to report working/archive message parity, conversation lifecycle counts, ended unchunked conversations, FTS chunk counts, best-effort Chroma counts, and bounded warning details.
- Added `repair_memory_integrity()` to dry-run or invoke existing recovery for ended unchunked conversations.
- Added admin CLI commands:
  - `memory-audit`
  - `memory-repair --limit N --dry-run`
- Active conversations are reported but not closed or mutated.
- No Chroma/FTS chunks are deleted or rebuilt.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_memory_audit.py -v`
- `.pyanam/bin/python -m pytest tests/test_chunking.py tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- FTS/Chroma comparison is count-level only.
- Repair v1 only targets ended unchunked conversations.
- Active conversations may remain partially unavailable to retrieval until live chunking or final close/chunking.
- Chroma count failures are reported as warnings and do not fail the audit.

## Follow-Up Work

- Consider an explicit full rebuild command only after designing index rebuild safety.
- Consider richer per-conversation chunk coverage checks if count-level audit is insufficient.
- Consider surfacing audit output in diagnostics later if an approved UI/API path exists.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved raw message persistence and existing memory architecture.
- Did not change Chroma/FTS schemas.
- Did not add startup auto-repair.
- Did not close active conversations.
- Did not add UI, API routes, autonomy, or new tools.
- Did not modify `soul.md`.
- Did not rename `tir/`.
