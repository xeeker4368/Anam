# Set-role admin command — v1

Date: 2026-06-01

## Summary

`add-user --admin` could create an admin, but there was no way to change an
EXISTING user's role. Both current users (Lyle, Jodie) are role `user`, and the
upcoming role-based UI (Part 2) needs a real admin/user distinction. This patch
adds a `set-role <name> <role>` admin command that changes a single user's role
in place — preserving their `user_id` and all referencing data (Lyle's 373
messages / 32 conversations are untouched; no delete-and-recreate).

## Files changed

- `tir/memory/db.py`
  - Added `update_user_role(user_id, role)` — a single-column
    `UPDATE main.users SET role = ? WHERE id = ?`, mirroring the existing
    `update_user_last_seen` helper. Working store only.
- `tir/admin.py`
  - Imported `update_user_role`.
  - Added `VALID_USER_ROLES = ("admin", "user")` with a comment noting these are
    the only values the `users.role` column uses (schema default `user` plus
    `admin` from `add-user --admin`); not invented.
  - Added `cmd_set_role`: validates the role in-handler (clear error + exit 1 on
    an invalid role), looks the user up via the existing case-sensitive
    `get_user_by_name` (same as show-user / set-password), errors clearly +
    exit 1 if the user does not exist, then performs the single-row update and
    prints `Set role for <name>: <old> -> <new> (id: <id>)`.
  - Registered the `set-role` subcommand (positional `name`, `role`) and added
    it to the command dispatch table. Validation lives in the handler, not as
    argparse `choices`, so the CLI and direct-call paths give the same error and
    exit code, with one source of truth for valid roles.
- `tests/test_admin.py`
  - Added 4 tests (see below).

## Behavior changed

- New admin command: `python -m tir.admin set-role <name> <role>`.
  - Valid roles: `admin`, `user` (case-sensitive). Invalid role → clear error,
    exit 1. Unknown user → clear error, exit 1.
  - Updates only the target user's `role` column on `working.db`; no other
    column (not `last_seen_at`, `name`, `created_at`, `id`) and no archive row
    is touched (archive.db `users` has no `role` column).
- No change to `add-user`, `get_user_by_name`, or any other command.

## Tests/checks run

- New tests in `tests/test_admin.py`:
  - `test_set_role_changes_role_and_nothing_else` — snapshots the full working
    `users` row before/after and asserts only `role` changed (every other column
    equal), the archive `users` row is byte-identical, and the confirmation line
    is printed.
  - `test_set_role_persists_across_reread` — a fresh `get_user_by_name` (new
    connection) returns the new role.
  - `test_set_role_invalid_role_rejected` — `superuser` → `SystemExit(1)`, clear
    message, role unchanged.
  - `test_set_role_nonexistent_user_rejected` — unknown name → `SystemExit(1)`,
    clear message.
- Full suite: `python -m pytest -q` → 855 passed (851 prior + 4 new), 145
  pre-existing deprecation warnings (chromadb / FastAPI `on_event`), unrelated.
- `git diff --check` → clean.

## Known limitations

- Valid roles are fixed to `("admin", "user")`. A future role would require
  extending `VALID_USER_ROLES` (the single source of truth).
- No bulk role change (out of scope) — one user per invocation.

## Follow-up work

- Operator step (manual, not part of this patch): run
  `python -m tir.admin set-role Lyle admin` to promote the operator before
  shipping Part 2, so the role-based UI's `role === 'admin'` gate does not lock
  the operator out of the full view. Jodie remains `user`.
- Then resume the held Part 2 (login UI + role-based view + source indicator).

## Project Anam alignment check

1. Assign the entity a name? No.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No — this is a household
   user's access role, not entity identity/personality.
4. Preserve raw experience? Yes — promotes a user in place; all their
   conversations/messages and the user_id they are attributed to are preserved.
5. Are derived artifacts traceable? N/A.
6. Are tool calls recorded? Unaffected.
7. Are created artifacts remembered? Unaffected.
8. Is context construction inspectable? Unaffected.
9. Does this make autonomy more cumulative? Neutral.
10. Preserve the Anam/entity distinction? Yes — operates on household users.
11. Require a migration? No — uses the existing `users.role` column; no schema
    change.
12. Tests run? Full suite (855 passed) + 4 new targeted tests.
13. Change core substrate behavior unnecessarily? No — additive admin command.
14. Add external dependencies/services? No.
15. Preserve workspace vs self-modification distinction? Yes — unaffected.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
