# Database Schema Documentation

## Summary

Added a standalone SQLite schema exporter and checked-in schema snapshot for Project Anam's current `working.db` and `archive.db` schemas.

## Files Changed

- `scripts/export_db_schema.py`
- `docs/DB_SCHEMA.md`
- `tests/test_db_schema_export.py`

## Behavior Changed

- No runtime behavior changed.
- Added a documentation-only CLI for exporting SQLite schema details:
  - tables
  - columns
  - primary keys
  - indexes
  - foreign keys
  - virtual/FTS tables
  - schema version rows
- Documented ownership notes for `working.db`, `archive.db`, Chroma, governance files, artifacts, journals, and behavioral guidance proposals.

## Tests/Checks Run

- `.pyanam/bin/python scripts/export_db_schema.py --working-db data/prod/working.db --archive-db data/prod/archive.db --output docs/DB_SCHEMA.md`
- `.pyanam/bin/python -m pytest tests/test_db_schema_export.py -v`

## Known Limitations

- Chroma is noted as vector storage but not fully documented as a schema.
- The snapshot reflects the inspected SQLite files at generation time.
- The exporter documents schema metadata only; it does not describe semantic row-level constraints beyond static schema and curated notes.

## Follow-Up Work

- Regenerate `docs/DB_SCHEMA.md` after future approved schema migrations.
- Consider adding schema export to release/checkpoint workflows.

## Project Anam Alignment Check

- Does not assign the entity a name or fixed personality.
- Does not mutate runtime databases or schema.
- Does not dump production row contents or sensitive data.
- Improves inspectability of durable operational/control-plane state.
