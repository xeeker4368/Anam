# Trusted Household User Mode v1

## Summary

Documented Project Anam's current trusted household identity model for Lyle and Lyle's wife on a trusted home LAN or VPN. Added small UI/status hardening so the active household user and identity-mode assumptions are more visible.

## Files Changed

- `docs/TRUSTED_HOUSEHOLD_USER_MODE.md`
- `PROJECT_STATE.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`
- `frontend/src/styles.css`
- `tir/ops/status.py`
- `tests/test_system_status_api.py`
- `changelog/2026-05-22-trusted-household-user-mode-v1.md`

## Behavior Changed

- The chat UI now shows the active household user outside the sidebar.
- System health now reports non-secret identity-mode metadata:
  - `identity_mode="trusted_client_user_id"`
  - `network_assumption="local_household_lan_or_vpn"`
  - `real_user_auth=false`

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_system_status_api.py -v`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Body/client-supplied `user_id` remains spoofable by anyone who can make API requests.
- `ANAM_API_SECRET` remains shared-secret API protection, not per-user authentication.
- No username/password login, sessions, cookies, OAuth, MFA, token auth, or public multi-user authentication was added.

## Follow-Up Work

- Implement Real Login / Session Auth v1 before public internet exposure, guest access, untrusted LAN access, broader device/network deployment, or sensitive admin UI expansion.
- Move user identity resolution to authenticated backend session/token state when real auth exists.
- Remove or ignore body-trusted `user_id` after real auth is implemented.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved source attribution for household users.
- Preserved raw experience and provenance boundaries.
- Did not change retrieval, memory semantics, research behavior, prompts, guidance files, model config, or DB schema.
