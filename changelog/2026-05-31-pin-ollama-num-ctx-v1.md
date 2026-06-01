# Pin Ollama context window via num_ctx — v1

Date: 2026-05-31

## Summary

The Ollama context window (`num_ctx`) was set nowhere — not in a Modelfile,
not in the API payload, not via env — so the model ran at Ollama's runtime
default instead of the value the code assumed. This patch pins `num_ctx` to
32768 through the existing `model_options.default` merge so it flows into
`payload["options"]` for every Ollama call, and adds an `ANAM_MODEL_NUM_CTX`
environment override mirroring the existing `ANAM_MODEL_TEMPERATURE` pattern.

## Files changed

- `tir/config.py`
  - Added `"num_ctx": 32768` to `_FALLBACK_CONFIG["model_options"]["default"]`.
  - Changed `CONTEXT_WINDOW` from `131072` to `32768` and updated its comment to
    `gemma4:26b pinned num_ctx=32K`.
  - Added an `ANAM_MODEL_NUM_CTX` env override in `get_model_options()` using the
    existing `_env_int` helper, mirroring the `ANAM_MODEL_TEMPERATURE` guard.
- `config/defaults.toml`
  - Added `num_ctx = 32768` under `[model_options.default]`.
- `tests/test_config.py`
  - Added `test_chat_model_options_pin_num_ctx` asserting
    `get_model_options("chat")["num_ctx"] == 32768`.
  - Added `ANAM_MODEL_NUM_CTX` to the `CONFIG_ENV_VARS` cleanup list so the new
    env override cannot leak from the real environment into reload-based tests.

## Behavior changed

- `get_model_options(role)` now returns a dict containing `num_ctx` (32768 by
  default for all roles via the `default` merge; no role currently overrides it).
- `tir/engine/ollama.py` is unchanged: `_apply_model_options` already forwards any
  non-`think`/`timeout_seconds` keys into `payload["options"]`, so `num_ctx` now
  reaches Ollama's `/api/chat` `options` unchanged on the stream-with-tools, JSON,
  and text paths.
- `num_ctx` can be overridden at runtime via `ANAM_MODEL_NUM_CTX`.
- `CONTEXT_WINDOW` constant value lowered to 32768. It currently has no consumers
  in the repo (verified by grep), so this is a documentation/constant update with
  no functional effect today.

## Tests / checks run

- Full suite: `python -m pytest -q` → **836 passed**, 133 pre-existing
  deprecation warnings (chromadb / FastAPI `on_event`), unrelated to this change.
- `num_ctx` whitelist for debug traces confirmed already present at
  `tir/ops/chat_debug_trace.py:34` (`safe_keys`), not modified.

## Known limitations

- All model roles (chat, reflection_journal, behavioral_guidance_review,
  operational_reflection) inherit the same 32768 via `model_options.default`;
  none override `num_ctx` individually.
- `CONTEXT_WINDOW` is not wired into the retrieval/context-budget math, so
  lowering it does not automatically tighten any budget.

## Follow-up work

- Out of scope here: conversation-history windowing / unbounded history.
- Optional future task: wire `CONTEXT_WINDOW` into budget calculations, or set
  per-role `num_ctx` overrides if a role needs a different window.

## Project Anam alignment check

1. Assign the entity a name? No.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No.
4. Preserve raw experience? Yes — unaffected.
5. Are derived artifacts traceable? N/A — no derived artifacts touched.
6. Are tool calls recorded? Unaffected.
7. Are created artifacts remembered? Unaffected.
8. Is context construction inspectable? Yes — `num_ctx` is whitelisted in the
   debug trace and visible in `payload["options"]`.
9. Does this make autonomy more cumulative? Neutral.
10. Preserve the Anam/entity distinction? Yes.
11. Require a migration? No — config/defaults only; no schema change.
12. Tests run? Full suite (836 passed) plus a new targeted assertion.
13. Change core substrate behavior unnecessarily? No — minimal, additive.
14. Add external dependencies/services? No.
15. Preserve workspace vs self-modification distinction? Yes — unaffected.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
