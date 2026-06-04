# Go-Live Reset Runbook

## Status

This is a design/runbook for a future go-live reset procedure.

Do not run a destructive reset during active development. Current pre-live runtime data may remain useful as test data until final launch preparation.

This document does not implement reset behavior. Any destructive reset command must be a separate explicitly approved patch.

## Purpose

Project Anam's live continuity should begin from a clean launch state, not from pre-live development conversations, test research notes, source traces, Chroma chunks, and experimental artifacts.

The reset must preserve the substrate, schema, household users, configuration, governance files, code, and backups while wiping pre-live runtime memory/state.

## Operator Procedure

1. Stop the backend and frontend.

2. Create a fresh backup:

   ```bash
   .pyanam/bin/python -m tir.admin backup
   ```

3. Verify the backup into an isolated target directory:

   ```bash
   .pyanam/bin/python -m tir.admin backup-restore-verify \
     --latest \
     --target-dir /tmp/anam-go-live-restore-check
   ```

4. Confirm backup verification passed and record the verified backup path.

5. Run the future reset command in dry-run mode first:

   ```bash
   .pyanam/bin/python -m tir.admin go-live-reset --dry-run
   ```

6. Review before/after counts and planned file removals.

7. Run destructive reset only with explicit confirmation:

   ```bash
   .pyanam/bin/python -m tir.admin go-live-reset \
     --confirm-go-live-reset \
     --typed-confirm "WIPE PRE-LIVE RUNTIME STATE" \
     --backup-path backups/<backup-id> \
     --backup-verified
   ```

8. Run post-reset verification:

   ```bash
   .pyanam/bin/python -m tir.admin go-live-reset --verify-clean
   ```

9. Start the app.

10. Confirm the first live chat has no pre-live retrieved memory.

## Pre-Go-Live Network Hardening Checklist

`./start.sh --lan` now binds the backend to `0.0.0.0:8000` (in addition to the
Vite frontend) so household devices can reach it directly. Before go-live on a
shared LAN:

- [ ] **Set `ANAM_API_SECRET` before go-live.** Under `--lan` the backend is
  reachable by any device on the LAN; with `ANAM_API_SECRET` unset the API is
  unauthenticated (read/write, user attribution). Set the secret so the wide
  bind is not also wide open. The frontend already sends `x-anam-secret`, and the
  backend enforces it (401) when configured. This stays consistent with the
  trusted-household LAN/VPN model — it is not real auth and not for public
  exposure.

## What To Wipe

The future reset should wipe pre-live continuity/runtime state:

- `archive.db` messages
- `working.db` conversations
- `working.db` messages
- `working.db` summaries
- `working.db` documents
- `working.db` overnight runs
- `working.db` tasks
- `working.db` artifacts
- `working.db` open loops
- `working.db` feedback records
- `working.db` diagnostic issues
- `working.db` review items
- `working.db` behavioral guidance proposals
- `working.db` chunks FTS table
- ChromaDB runtime data
- `workspace/research/`
- `workspace/research/source-traces/`
- `workspace/journals/`
- `workspace/uploads/`, unless explicitly allowlisted
- generated or staged runtime artifacts as approved
- local test research outputs
- user `last_seen` or activity traces, while preserving user rows

Uploaded artifacts should be wiped by default because they are pre-live experience/artifact continuity. Any upload preserved for launch should be explicitly allowlisted in the future implementation patch.

## What To Preserve

The reset must preserve substrate and launch scaffolding:

- code
- `.git`
- docs
- changelog
- `config/defaults.toml`
- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- `soul.md`
- `OPERATIONAL_GUIDANCE.md`
- `BEHAVIORAL_GUIDANCE.md`, verified dormant
- users tables
- `channel_identifiers`
- `schema_versions`
- backups
- `.pyanam`
- `node_modules`
- external env/token configuration, without printing values

## Future Command Guardrails

The future destructive command should require:

- a fresh backup
- a passing `backup-restore-verify` result
- dry-run mode before destructive mode
- `--confirm-go-live-reset`
- typed confirmation phrase: `WIPE PRE-LIVE RUNTIME STATE`
- refusal when no backup path is supplied
- refusal when backup verification has not been acknowledged
- an audit file with before/after counts, timestamp, backup path, verification target, and preserved users

The future command must never delete:

- backups
- `.git`
- code
- docs
- config
- `.pyanam`
- `node_modules`
- governance files

## Future Command Shape

Dry-run:

```bash
.pyanam/bin/python -m tir.admin go-live-reset --dry-run
```

Destructive reset:

```bash
.pyanam/bin/python -m tir.admin go-live-reset \
  --confirm-go-live-reset \
  --typed-confirm "WIPE PRE-LIVE RUNTIME STATE" \
  --backup-path backups/<backup-id> \
  --backup-verified
```

Clean-state verification:

```bash
.pyanam/bin/python -m tir.admin go-live-reset --verify-clean
```

## Post-Reset Verification Checklist

After reset, verify:

- `archive.db` messages count is `0`
- `working.db` conversations count is `0`
- `working.db` messages count is `0`
- `working.db` chunks FTS count is `0`
- ChromaDB is empty or freshly initialized
- `workspace/research/` is empty
- `workspace/research/source-traces/` is empty
- `workspace/journals/` is empty
- `workspace/uploads/` is empty
- open loops are empty
- artifacts are empty
- review items are empty
- behavioral guidance proposals are empty
- tasks are empty
- diagnostic issues are empty
- users still exist
- `schema_versions` still exists
- `BEHAVIORAL_GUIDANCE.md` remains dormant and has no active guidance lines
- reset audit file exists
- first chat retrieves no pre-live memory

## Tests Needed For Future Implementation

Future implementation should cover:

- dry-run reports planned deletions without mutation
- reset refuses without confirmation
- reset refuses without backup path
- reset refuses unless backup verification is acknowledged
- users are preserved
- `schema_versions` is preserved
- `channel_identifiers` are preserved
- archive messages are wiped
- working runtime tables are wiped
- FTS table is cleared
- Chroma directory is reset safely
- workspace runtime directories are cleared and recreated
- governance docs are untouched
- backups are untouched
- audit file records before/after counts
- verify-clean passes after reset
- verify-clean fails before reset when runtime state exists
- existing backup/restore tests pass
- full pytest passes
- `git diff --check` passes

## Deferred

This runbook does not implement:

- `go-live-reset`
- DB mutation
- Chroma deletion or reset
- workspace deletion
- backup verification enforcement
- audit file writing
- prompt, guidance, model, UI, auth, research, Moltbook, or web behavior changes
