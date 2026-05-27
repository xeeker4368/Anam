# start.sh LAN + Local ComfyUI Startup v1

## Summary

Updated Project Anam startup planning/runtime ergonomics so `start.sh` can launch the local web UI for household LAN/iPhone access and optionally start or reuse a local ComfyUI server.

## Files Changed

- `start.sh`
- `frontend/vite.config.js`
- `changelog/2026-05-26-start-sh-lan-comfyui-startup-v1.md`

## Behavior Changed

- `./start.sh` remains local-only by default.
- `./start.sh --lan` exposes the Vite frontend on `0.0.0.0` while keeping the backend bound to `127.0.0.1`.
- `./start.sh --with-comfyui` starts or reuses local ComfyUI on `127.0.0.1:8188`.
- `./start.sh --no-comfyui` explicitly skips ComfyUI startup.
- `./start.sh --help` prints supported startup options.
- Startup now prints clearer local/LAN URLs, readiness status, and a trusted-household LAN/VPN warning.
- Vite now proxies `/api/*` to `http://127.0.0.1:8000` to avoid localhost IPv6 ambiguity.

## Tests/Checks Run

- `bash -n start.sh`
- `./start.sh --help`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Manual local startup smoke test on temporary frontend port `5174`
- Manual LAN startup smoke test on temporary frontend port `5175`
- Manual `--with-comfyui` startup smoke test on temporary frontend port `5176`

## Known Limitations

- The script does not install ComfyUI dependencies or download image models.
- ComfyUI defaults to `python3` unless `COMFYUI_PYTHON` is set.
- Local ComfyUI startup with default `python3` failed in this environment because `sqlalchemy` was missing; startup warned and continued as intended.
- The script fails clearly or warns if expected ports are unavailable, but it does not kill unknown pre-existing processes.
- LAN mode is intended only for trusted household LAN/VPN use.

## Follow-up Work

- Add a production/static-frontend startup path later if the dev server should not be used for go-live household access.
- Consider a dedicated `stop.sh` if operator workflow needs separate start/stop commands.

## Project Anam Alignment Check

- Does not expose ComfyUI on LAN.
- Does not make image generation agent-callable.
- Does not change backend API behavior, image generation semantics, prompts, guidance, model config, scheduler, research, Moltbook, or web behavior.
- Preserves Trusted Household User Mode boundaries by requiring explicit LAN startup.
