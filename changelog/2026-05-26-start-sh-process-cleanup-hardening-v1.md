# start.sh Process Cleanup Hardening v1

## Summary

Hardened `start.sh` shutdown so Ctrl+C stops the backend/frontend process trees started by the script and only stops ComfyUI when this script launched it.

## Files Changed

- `start.sh`
- `changelog/2026-05-26-start-sh-process-cleanup-hardening-v1.md`

## Behavior Changed

- `start.sh` now enables job control so started services can run in separate process groups where supported.
- Cleanup now stops frontend, backend, and script-spawned ComfyUI through a shared process-tree helper.
- Cleanup sends TERM first, waits briefly, then sends KILL only to PIDs/process groups started by this script if they remain alive.
- Pre-existing ComfyUI is marked as reused and explicitly skipped during cleanup.
- Shutdown output now names each service PID as it is stopped.

## Tests/Checks Run

- `bash -n start.sh`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Manual alternate-port cleanup check: `ANAM_API_PORT=8765 ANAM_FRONTEND_PORT=5765 ./start.sh --no-comfyui`, then Ctrl+C. Confirmed ports 8765 and 5765 no longer listened.
- Manual LAN cleanup check: `ANAM_API_PORT=8768 ANAM_FRONTEND_PORT=5768 ./start.sh --lan --no-comfyui`, then Ctrl+C. Confirmed ports 8768 and 5768 no longer listened.
- Manual reused-ComfyUI protection check using a temporary local `/system_stats` service on port 8188. `start.sh --with-comfyui` reused it, cleanup skipped it, and the temporary service remained reachable until stopped separately.
- Manual unavailable ComfyUI check: `start.sh --with-comfyui` with default `python3` reported the missing ComfyUI dependency and did not leave port 8188 listening.

## Known Limitations

- Process-tree fallback depends on `pgrep -P` when a started process is not its own process-group leader.
- This script still does not manage or stop Ollama.
- The local ComfyUI checkout did not start with default `python3` because `sqlalchemy` was not installed there; use `COMFYUI_PYTHON` for a configured ComfyUI environment.

## Follow-up Work

- Consider a separate operator-facing status/stop command if process management needs to cover manually started services later.

## Project Anam Alignment Check

- This is local startup/tooling hygiene for the Project Anam substrate.
- Does not change backend API behavior, frontend app behavior, memory, prompts, guidance, model config, scheduler, research, Moltbook, web, image generation semantics, or avatar behavior.
- Does not assign the entity a name, avatar, appearance, personality, or self-representation.
