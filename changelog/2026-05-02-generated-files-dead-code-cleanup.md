# Generated Files And Dead Code Cleanup

## Summary

Removed tracked generated Python bytecode files, dropped unused non-agent Ollama helper functions, and removed the unused Flask dependency.

## Files Changed

- `requirements.txt`
- `tir/engine/ollama.py`
- tracked `__pycache__` / `*.pyc` files
- `changelog/2026-05-02-generated-files-dead-code-cleanup.md`

## Behavior Changed

- Generated Python bytecode files are no longer tracked by git.
- `tir.engine.ollama` now exposes only the tool-capable streaming chat helper used by the supported Web/API agent loop.
- Flask is no longer listed as a Python dependency.

## Tests/Checks Run

- `git ls-files '*__pycache__*' '*.pyc'`
- `rg "chat_completion\\(|chat_completion_stream\\(" tir tests -g '!*.pyc'`
- `rg "flask|Flask" . -g '!data/prod/**' -g '!*.pyc' -g '!frontend/node_modules/**'`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_agent_loop.py tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py tests/test_tool_registry.py -v`
- `git diff --check`

## Known Limitations

- Historical `Dev_Docs/` files may still mention older non-agent chat helpers or Flask-era implementation notes.
- `trafilatura` remains in `requirements.txt` for now by explicit patch constraint.

## Follow-up Work

- Continue to defer summaries/consolidation schema cleanup until there is an explicit migration decision.
- Address frontend non-OK fetch handling in a separate focused reliability patch.

## Project Anam Alignment Check

- Did not modify DB schema.
- Did not remove summaries or consolidation code.
- Did not remove `trafilatura`.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not add features.
- Did not change Web/API chat behavior.
- Did not change agent loop behavior.
- Did not change memory retrieval behavior.
- Did not touch `data/prod` files.
