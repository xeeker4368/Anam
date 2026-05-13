# Runtime Configuration Foundation

## Summary

Added a TOML-backed runtime configuration foundation with safe code fallbacks, optional local overrides, environment variable precedence, role-specific model defaults, and Ollama `think` / timeout configuration.

## Files Changed

- `tir/config.py`
- `config/defaults.toml`
- `config/local.example.toml`
- `.gitignore`
- `tir/engine/ollama.py`
- `tir/reflection/journal.py`
- `tir/reflection/operational.py`
- `tir/behavioral_guidance/review.py`
- `tir/engine/context.py`
- `tir/engine/context_budget.py`
- `tir/engine/journal_context.py`
- `tir/engine/artifact_context.py`
- `tests/test_config.py`
- `tests/test_ollama.py`
- `changelog/2026-05-09-runtime-configuration-foundation.md`

## Behavior Changed

Defaults are now loaded from code fallbacks, `config/defaults.toml`, optional `config/local.toml`, and environment variables in that order.

Runtime defaults are intended to preserve existing behavior while making model names, Ollama host/timeout, model `think` behavior, and key budgets configurable without code edits.

Ollama `/api/chat` helpers now place configured `think` at the top level of the payload and use role-specific timeouts where configured.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_config.py -v`
- `.pyanam/bin/python -m pytest tests/test_ollama.py -v`
- `.pyanam/bin/python -m pytest tests/test_reflection_journal.py tests/test_behavioral_guidance_review.py tests/test_operational_reflection.py -v`
- `git diff --check`

## Known Limitations

- Config values are still exported as import-time constants for compatibility.
- `config/local.toml` is local-only and not backed up by this patch.
- CORS/dev-origin configuration remains hardcoded.
- Embedding calls keep their existing timeout behavior.
- Feature toggles are intentionally not introduced yet.

## Follow-Up Work

- Add an admin config-inspection command if operationally useful.
- Consider CORS/dev-origin config in a focused later patch.
- Consider dynamic config reload only if there is a concrete operator need.
- Add config coverage for future feature flags when those features are introduced.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Preserves existing runtime behavior while making operator-controlled model and budget changes explicit.
- Keeps secrets environment-only.
- Does not change schema, prompts, guidance files, or memory architecture.
