# Tool Loop Limit Bounded Response v1

## Summary

Replaced the generic tool-iteration-limit failure text with a bounded assistant response that summarizes available partial tool progress and proposes a smaller next step.

## Files Changed

- `tir/engine/agent_loop.py`
- `tir/api/routes.py`
- `tests/test_agent_loop.py`
- `tests/test_api_agent_stream.py`
- `docs/PROMPT_INVENTORY.md`
- `changelog/2026-05-25-tool-loop-limit-bounded-response-v1.md`

## Behavior Changed

- When the agent loop reaches its iteration limit, it now stops cleanly with a structured assistant message.
- The response acknowledges the iteration limit, summarizes any available tool-result previews, states that no further tool calls will be made in the turn, and suggests a smaller bounded next step.
- The streaming API now emits the iteration-limit response as assistant text instead of a generic error event.
- The bounded response is saved as the assistant message with the existing tool trace when partial tool activity exists.
- Existing debug and tool events remain available.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python -m pytest tests -q`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`

Pre-change note: `.pyanam/bin/python -m pytest` from the repository root attempted to collect the local untracked `ComfyUI/` checkout and failed during collection. The Project Anam test suite under `tests/` passed after the patch.

## Known Limitations

- The partial-progress summary is intentionally compact and only uses existing rendered tool-result previews.
- This does not add retries, scheduler behavior, broad autonomy, or task decomposition.

## Follow-Up Work

- Consider whether the frontend should visually distinguish bounded failure responses from ordinary successful completions without treating them as red connection errors.
- Re-run full pytest after the local untracked `ComfyUI/` directory is moved outside the repo or excluded from test discovery.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved raw tool traces and inspectable debug behavior.
- Did not change scheduler/autonomy behavior, image generation, Moltbook/web behavior, research semantics, prompts, guidance files, `soul.md`, model config, DB schema, Chroma schema, or UI.
