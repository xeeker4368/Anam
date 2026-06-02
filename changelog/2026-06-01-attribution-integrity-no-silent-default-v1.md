# Attribution integrity — no silent default user — v1

Date: 2026-06-01

## Summary

`_resolve_user(None)` in `tir/api/routes.py` silently fell back to
`DEFAULT_USER` ("Lyle"). Because the frontend sends `user_id` from
`activeUserId`, which is null on fresh/cleared localStorage, a request with a
null `user_id` was silently attributed to Lyle. For an attribution-critical
experiment (raw-transcript memory permanently bakes in the source label), that
is silent, irreversible mislabeling.

This patch makes `_resolve_user` reject a missing/blank `user_id` (HTTP 422)
instead of defaulting, keeps the existing unknown-user rejection (404), and adds
a case-insensitive name→user resolution endpoint for the upcoming login UI. The
change is scoped to user-facing request handling; no CLI/admin/internal caller
is affected.

## Investigation (call sites + confinement)

All three `_resolve_user` call sites are user-attributed content creators, so
all must require an explicit known user (no site where defaulting is correct):

- `routes.py` `POST /api/chat/stream` — conversations + raw-transcript messages.
- `routes.py` `POST /api/artifacts/upload` — user-attributed artifact + indexed
  source material.
- `routes.py` `POST /api/image-generation/generate` — user-attributed generated
  media artifact.

`_resolve_user` is referenced only in `routes.py` (these three sites) plus test
mocks — no CLI/admin/internal caller uses it (repo-wide grep). So tightening it
affects request handling only.

## Files changed

- `tir/api/routes.py`
  - Rewrote `_resolve_user`: a missing/blank `user_id` raises
    `HTTPException(422, "user_id is required; the request must identify a known
    user")`; an unknown `user_id` still raises 404. Removed the `DEFAULT_USER` /
    `get_all_users` / admin fallback entirely. The three call sites are
    unchanged: chat lets the exception propagate (raised before the streaming
    generator, so FastAPI returns a clean 422/404 `{"detail": ...}`); upload and
    image-generation already catch `HTTPException` and return
    `{"ok": false, "error": ...}` via `_error_response`.
  - Removed the now-dead imports `DEFAULT_USER` (from `tir.config`) and
    `get_user_by_name` (from `tir.memory.db`). `get_all_users` is retained.
  - Added `GET /api/users/resolve?name=...` — resolves a user by name
    case-insensitively (404 on no match, 422 on blank name), implemented at the
    route layer via `get_all_users()`.
- `docs/PROMPT_INVENTORY.md`
  - Regenerated via `scripts/extract_prompt_inventory.py` (canonical generator).
    Only two `routes.py` line numbers shifted (805→802, 824→821) from the edits;
    no prompt content changed. Keeps `tests/test_prompt_inventory.py` green.
- `tests/test_attribution_integrity.py` (new) — 6 tests.

## DEFAULT_USER disposition

`DEFAULT_USER` remains defined at `tir/config.py:321` (not removed, per
instruction). After this patch it is no longer referenced anywhere in the
codebase; no non-request caller used it. Only its dead use and import in
`routes.py` were removed.

## Behavior changed

- `POST /api/chat/stream` with missing/blank `user_id` → **422** (was: silently
  attributed to Lyle). With unknown `user_id` → **404** (unchanged). With a
  valid `user_id` → attributed to that user, message saved under that user_id
  (unchanged).
- `POST /api/artifacts/upload` and `POST /api/image-generation/generate` with
  missing/blank `user_id` → **422** `{"ok": false, "error": ...}` (was:
  defaulted). Unknown `user_id` → 404 (unchanged).
- New `GET /api/users/resolve?name=...` for name→user lookup.
- The DB layer (`get_user`, `get_user_by_name`, `get_all_users`) is unchanged;
  CLI/admin exact-match name lookups behave exactly as before.

## Tests/checks run

- New tests: `pytest tests/test_attribution_integrity.py -q` → 6 passed:
  - chat missing `user_id` rejected (422) AND not attributed — a `Lyle` user is
    created first so a regression to the old default would mis-attribute to him;
    asserts 0 conversations/0 messages written.
  - chat unknown `user_id` → 404, nothing written.
  - chat valid `user_id` → `start_conversation` and `save_message` receive the
    real user's id (Renee), not Lyle.
  - upload missing `user_id` → 422 `{"ok": false, ...}`.
  - image-generation missing `user_id` → 422 `{"ok": false, ...}`.
  - name resolution: exact + lowercased + whitespace-padded uppercase all match
    case-insensitively; unknown → 404; blank → 422.
  - Confirmed the missing-`user_id` rejections trigger our explicit 422 (string
    `detail` / our error body), not a pydantic field-required 422 (`user_id` is
    optional on both `ChatRequest` and `ImageGenerationRequest`).
- Full suite: `python -m pytest -q` → 851 passed (845 prior + 6 new), 145
  pre-existing deprecation warnings (chromadb / FastAPI `on_event`), unrelated.
- `git diff --check` → clean.

## Known limitations

- `/api/users/resolve` returns the earliest-created user if two users share a
  name case-insensitively (names are distinct people in this experiment).
- This is backend-only. The frontend must send a real `user_id` (Part 2); until
  then a null `user_id` now yields a clear 422 rather than silent mislabeling.

## Follow-up work

- Out of scope here: the login UI, the "you are: X" indicator, per-device
  identity (Part 2 frontend task).

## Project Anam alignment check

1. Assign the entity a name? No.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No.
4. Preserve raw experience? Yes — and strengthens its integrity: raw transcripts
   are no longer silently mislabeled with the wrong source user.
5. Are derived artifacts traceable? Yes — attribution is now explicit;
   `docs/PROMPT_INVENTORY.md` regenerated from source.
6. Are tool calls recorded? Unaffected.
7. Are created artifacts remembered? Unaffected (now correctly attributed).
8. Is context construction inspectable? Unaffected.
9. Does this make autonomy more cumulative? Neutral.
10. Preserve the Anam/entity distinction? Yes.
11. Require a migration? No — no schema change.
12. Tests run? Full suite (851 passed) + new tests + `git diff --check`.
13. Change core substrate behavior unnecessarily? No — scoped to user-facing
    request attribution.
14. Add external dependencies/services? No.
15. Preserve workspace vs self-modification distinction? Yes — unaffected.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
