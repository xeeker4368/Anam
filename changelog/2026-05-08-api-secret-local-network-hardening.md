# Minimal API Secret for Local-Network Hardening

## Summary
- Added optional shared-secret protection for non-public `/api` routes when `ANAM_API_SECRET` is configured.
- Added frontend request handling that sends `x-anam-secret` from browser localStorage.
- Added a compact System panel control for saving or clearing the API secret in the current browser.

## Files Changed
- `tir/api/auth.py`
- `tir/api/routes.py`
- `frontend/src/api.js`
- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`
- `frontend/src/components/SystemPanel.jsx`
- `frontend/src/styles.css`
- `tests/test_api_auth.py`
- `changelog/2026-05-08-api-secret-local-network-hardening.md`

## Behavior Changed
- If `ANAM_API_SECRET` is unset, existing local/dev API behavior remains unchanged and startup logs a warning.
- If `ANAM_API_SECRET` is set, non-public `/api` routes require `x-anam-secret`.
- Public unauthenticated routes remain:
  - `/api/health`
  - `/api/system/health`
  - `/api/system/capabilities`
- `OPTIONS` requests and non-API/static routes are not blocked.
- Unauthorized protected API requests return HTTP 401 with `{ "ok": false, "error": "unauthorized" }`.
- Frontend API calls now use `apiFetch`, which preserves streaming responses and avoids forcing `Content-Type` for `FormData` uploads.

## Tests/Checks Run
- `.pyanam/bin/python -m pytest tests/test_api_auth.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_system_status_api.py -v`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`

## Known Limitations
- This is local-network hardening, not full authentication.
- Browser `localStorage` is not a secure credential vault.
- `reviewed_by_role=admin` and similar governance checks are still text-level validation, not full user/session role enforcement.
- If the frontend is served through Vite from another device, Vite host/CORS/network settings may still need separate configuration.

## Follow-Up Work
- Add full admin/user session authentication before exposing broader admin or self-modification controls.
- Consider protecting additional read-only status endpoints if operator metadata exposure becomes a concern.

## Project Anam Alignment Check
- Does not assign the entity a name or personality.
- Does not modify `soul.md` or `BEHAVIORAL_GUIDANCE.md`.
- Does not change schema, memory architecture, prompt loading, or governance proposal semantics.
- Keeps local-network access operator-controlled without introducing full auth prematurely.
