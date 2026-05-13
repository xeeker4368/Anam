# Single-Model Temperature / Voice Stabilization v1

## Summary

Added a global default Ollama sampling temperature for Project Anam's primary model path. The committed default keeps Anam-owned roles on the same model while sharing one sampling style.

## Files Changed

- `config/defaults.toml`
- `config/local.example.toml`
- `tir/config.py`
- `tests/test_config.py`
- `tests/test_ollama.py`

## Behavior Changed

- `model_options.default.temperature` now defaults to `0.35`.
- `ANAM_MODEL_TEMPERATURE` can override the global default temperature as a float.
- Ollama requests continue to place `think` at the top level and send `temperature` under `options`.
- Existing role model names remain unchanged in committed defaults.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_config.py -v`
- `.pyanam/bin/python -m pytest tests/test_ollama.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- This does not add prompt damping.
- This does not add role-specific temperature tuning.
- Model behavior may still require later calibration if `0.35` remains too expressive or becomes too flat.

## Follow-Up Work

- If Gemma4 remains overly dramatic after live testing, tune `ANAM_MODEL_TEMPERATURE` or `config/local.toml`.
- Consider a separate operational guidance review only if temperature calibration is insufficient.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not define a fixed personality.
- Preserves a single primary model voice for Anam-owned roles.
- Does not modify `soul.md`, `BEHAVIORAL_GUIDANCE.md`, or `OPERATIONAL_GUIDANCE.md`.
