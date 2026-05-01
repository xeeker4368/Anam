# Startup And DB Reliability

## Summary

Fixed small startup and runtime reliability issues around server logging, archive DB initialization, CORS dev origins, and default web binding.

## Files Changed

- `run_server.py`
- `tir/config.py`
- `tir/api/routes.py`
- `tir/memory/db.py`
- `tests/test_run_server.py`
- `tests/test_db.py`
- `changelog/2026-05-01-startup-db-reliability.md`

## Behavior Changed

- `run_server.py` now writes logs to `DATA_DIR / "tir.log"` and creates the parent directory before constructing the file handler.
- Archive DB initialization now closes its SQLite connection explicitly.
- CORS dev origins now include both `http://localhost:5173` and `http://127.0.0.1:5173`.
- `WEB_HOST` now defaults to `127.0.0.1`.
- LAN binding is opt-in with `TIR_WEB_HOST=0.0.0.0`.
- `WEB_PORT` can be overridden with `TIR_WEB_PORT`.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_db.py -v`
- `.pyanam/bin/python -m pytest tests/test_run_server.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_chunking.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py tests/test_diagnostics.py -v`
- `git diff --check`
- Manual checks:
  - Verified `run_server.py` uses `DATA_DIR / "tir.log"`.
  - Verified CORS origins include `http://localhost:5173` and `http://127.0.0.1:5173`.
  - Verified `WEB_HOST` defaults to `127.0.0.1`.
  - Verified LAN access remains opt-in with `TIR_WEB_HOST=0.0.0.0`.

## Known Limitations

- CORS origins remain dev-focused and explicit.
- Existing deployments relying on LAN binding must set `TIR_WEB_HOST=0.0.0.0`.

## Follow-up Work

- Consider documenting environment variables in a dedicated operations guide if deployment needs expand.

## Project Anam Alignment Check

- Did not add new features.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not change memory retrieval behavior.
- Did not add memory scopes.
- Did not add registries.
- Did not add web search, Moltbook, image generation, autonomy, or self-modification.
- Did not remove CLI chat.
