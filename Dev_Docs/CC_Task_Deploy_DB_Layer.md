# CC Task: Deploy Database Layer + Admin CLI

## What this is

Three files that implement the Tír database layer and admin CLI. Copy them to the project directory on the Mac, install dependencies, run tests, verify.

## Files to deploy

Copy these files into the Tír project directory, preserving this structure:

```
tir/
    __init__.py
    config.py
    admin.py
    memory/
        __init__.py
        db.py
tests/
    test_db.py
```

If `tir/` and `tests/` directories don't exist at the project root, create them.

## Before running

1. Make sure `data/prod/` directory exists at the project root (config.py expects it):
```bash
mkdir -p data/prod
```

2. Install pytest if not already present:
```bash
pip install pytest
```

3. No other dependencies needed for the database layer. argon2-cffi is optional (only needed for `set-password` command, not for tests).

## Verify — run the tests

From the project root:

```bash
python -m pytest tests/test_db.py -v
```

All tests should pass. There are 20 tests across 7 test classes:
- TestSchemaCreation (4 tests) — tables exist, FTS5 exists, journaling mode correct
- TestUserManagement (4 tests) — create, lookup, dual-database presence
- TestChannelIdentifiers (3 tests) — add, resolve, uniqueness constraint
- TestAtomicDualWrite (3 tests) — message in both DBs, count increment, tool trace
- TestConversations (3 tests) — start/end, active filtering, turn counting
- TestTasks (2 tests) — add/get pending, status updates
- TestFTS5 (2 tests) — upsert/search, conversation exclusion

## Verify — admin CLI

After tests pass:

```bash
# Initialize databases
python -m tir.admin init-db

# Create admin user
python -m tir.admin add-user Lyle --admin

# Add iMessage channel identifier (use real phone number)
python -m tir.admin add-channel Lyle imessage "+1XXXXXXXXXX"

# Verify
python -m tir.admin show-user Lyle
python -m tir.admin list-users
```

Expected output from show-user:
```
Name:       Lyle
Role:       admin
ID:         <uuid>
Created:    <timestamp>
Last seen:  never
Channels:
  imessage     +1XXXXXXXXXX                   [verified, no auth]
```

## Verify — database files

After running admin commands:

```bash
# Both database files should exist
ls -la data/prod/

# Archive should have the user
sqlite3 data/prod/archive.db "SELECT * FROM users;"

# Working should have user + channel identifier
sqlite3 data/prod/working.db "SELECT * FROM users;"
sqlite3 data/prod/working.db "SELECT * FROM channel_identifiers;"
```

## What NOT to do

- Do not modify config.py paths unless the project root is somewhere unexpected
- Do not add tables to archive.db — its scope is frozen at users + messages
- Do not switch journal_mode to WAL — DELETE is required for ATTACH atomicity
- Do not create additional files — this task is deploy + verify only

## If something fails

- Import errors: make sure you're running from the project root and the `tir/` package structure is correct with `__init__.py` files
- FTS5 not available: SQLite on macOS ships with FTS5 enabled. If somehow missing, check `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"`
- Path issues: check that DATA_DIR in config.py resolves correctly from wherever you're running

## What comes next

After this is verified working:
- Phase 1 Step 2: soul.md (seed identity file)
- Phase 1 Step 3: ChromaDB + embedding layer
- Phase 1 Step 4: Minimal context construction + agent loop
- Phase 1 Step 5: CLI chat interface (first conversation)
- Phase 1 Step 6: iMessage adapter
