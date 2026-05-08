# Minimal Schema Migration Support

## Summary
- Added a lightweight working.db schema migration ledger and runner.
- Recorded the current hand-built working schema as baseline version 1.
- Added tests covering fresh DBs, existing DBs, idempotency, working-only scope, pending migration ordering, failure behavior, and skip behavior.

## Files Changed
- `tir/memory/migrations.py`
- `tir/memory/db.py`
- `tests/test_schema_migrations.py`
- `changelog/2026-05-08-schema-migration-foundation.md`

## Behavior Changed
- `init_databases()` now creates a `schema_versions` table in working.db only.
- Fresh and existing working DBs get baseline row `1 / baseline_current_schema` after current schema creation succeeds.
- Future migrations can be registered in version order starting at version 2.
- Failed migrations roll back and do not record their version.
- Archive DB schema remains unchanged.

## Tests/Checks Run
- `.pyanam/bin/python -m pytest tests/test_schema_migrations.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_audit.py -v`
- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `git diff --check`

## Known Limitations
- Baseline version 1 records that the current code recognized or initialized the existing schema; it does not infer or repair historical schema drift.
- No actual ALTER-style migration is included in this patch.
- Future migrations that touch virtual tables may need special handling.

## Follow-Up Work
- Add explicit version 2+ migrations for any future durable table or column changes.
- Use this framework before changing behavioral guidance provenance, reflection journals, or self-understanding records.

## Project Anam Alignment Check
- Does not assign the entity a name or personality.
- Does not modify `soul.md` or `BEHAVIORAL_GUIDANCE.md`.
- Preserves durable governance/control-plane state by reducing reliance on DB wipes.
- Does not change memory architecture, archive schema, retrieval behavior, or prompt loading.
