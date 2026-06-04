# LAN Backend Bind v1

## Summary

`./start.sh --lan` exposed the Vite frontend on `0.0.0.0:5173` but left the
backend bound to `127.0.0.1:8000` (loopback only), so household devices could not
reach the backend at the Mac's LAN IP (`http://192.168.0.41:8000/`). This patch
makes `--lan` bind the backend to `0.0.0.0:8000` the same way it binds Vite,
unblocking the go-live "LAN reachability verify" item. The non-LAN default is
unchanged (loopback only).

## Root Cause

The backend host is flag/env-driven, not hardcoded in Python: `start_backend()`
passes `ANAM_API_HOST="$BACKEND_HOST"` to `run_server.py`, which binds uvicorn to
`WEB_HOST`, read from `ANAM_API_HOST` (`tir/config.py`). The bug was scope, not
plumbing: `BACKEND_HOST="127.0.0.1"` in `start.sh` was never changed by `--lan`.
`--lan` only flipped the frontend's local `frontend_host` to `0.0.0.0`; the
backend always received `127.0.0.1`.

## Files Changed

- `start.sh`
- `docs/GO_LIVE_RESET_RUNBOOK.md` (follow-up checklist item)

## Behavior Changed

- `start_backend()` now uses a LAN-gated local bind host (`127.0.0.1`, or
  `0.0.0.0` when `--lan` is set), mirroring `start_frontend()`. The global
  `BACKEND_HOST="127.0.0.1"` is unchanged and still used for the loopback health
  check (`wait_for_url …/api/health`) and the "Backend local URL" display —
  uvicorn on `0.0.0.0` still answers on loopback.
- Without `--lan`, the backend stays bound to `127.0.0.1` (unchanged safe
  default).
- Corrected the `--lan` help text, which previously claimed the backend "remains
  bound to 127.0.0.1 and is reached through Vite proxy" — no longer true.
- `detect_lan_urls` now takes a port argument (default `FRONTEND_PORT` for
  backward compatibility); under `--lan` the startup output prints both
  "Frontend LAN URL(s)" and "Backend LAN URL(s)".

## CORS

Not changed — confirmed unnecessary, not assumed. `apiFetch` uses relative paths
(`fetch('/api/…')`, no base URL), and the backend serves the built frontend
(`FRONTEND_DIR = …/frontend/dist`). When a phone loads the UI from
`http://<lan-ip>:8000/`, its API calls are same-origin (`http://<lan-ip>:8000/api/…`),
so no CORS preflight occurs. The existing `allow_origins` (localhost/127.0.0.1
:5173) only concerns the Vite-dev path, which is same-origin to the browser via
the Vite proxy.

## Security Note

Binding the backend to `0.0.0.0` makes it reachable by any LAN device. With
`ANAM_API_SECRET` unset the API is unauthenticated. This is consistent with the
documented trusted-household LAN/VPN model (Decisions #15–17) and the startup
banner already warns LAN/VPN-only. The secret change was intentionally NOT
bundled here; instead, a "Set `ANAM_API_SECRET` before go-live" item was added to
the Pre-Go-Live Network Hardening Checklist in `docs/GO_LIVE_RESET_RUNBOOK.md`.

## Tests/Checks Run

- `bash -n start.sh` — syntax OK.
- shellcheck — not installed locally; skipped.
- Manual device verification pending (see Known Limitations).

## Known Limitations

- Phone reachability of `http://192.168.0.41:8000/` is to be verified on-device
  before commit (the acceptance check for this patch).
- If `TIR_WEB_HOST` is set in the environment it takes precedence over
  `ANAM_API_HOST` and would override the bind; `start.sh` does not set it. The
  uvicorn startup log line confirms the effective bind host.

## Follow-Up Work

- Set `ANAM_API_SECRET` before go-live (now tracked in the runbook checklist).
- Phase B (resume coordination) and Phase C (keyboard loop) remain queued from
  the frontend consolidation plan, independent of this patch.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, guidance, model config, memory, scheduler, research, or
  image generation.
- No schema change; no migration required.
- No new external dependencies or paid services.
- No package rename; `tir/` untouched.
- Change is additive and strictly gated behind `--lan`; the safe loopback-only
  default is preserved. Surfaced the unauthenticated-API/wide-bind tradeoff
  rather than silently widening exposure.
