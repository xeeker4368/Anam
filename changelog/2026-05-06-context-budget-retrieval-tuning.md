## Summary

Tightened automatic retrieval and prompt-context budgeting for `/api/chat/stream` to reduce prompt bloat and slow first-token latency.

## Files Changed

- `tir/engine/context_budget.py`
- `tir/engine/retrieval_policy.py`
- `tir/api/routes.py`
- `tests/test_retrieval_policy.py`
- `tests/test_context.py`
- `tests/test_api_agent_stream.py`

## Behavior Changed

- Automatic chat retrieval now requests 8 chunks by default.
- Retrieved chunks are capped to a 14,000 character context budget.
- Individual retrieved chunks are capped to 3,000 characters with an explicit truncation marker.
- Context-inspection prompts skip memory retrieval to avoid polluting the answer.
- Chat debug output now includes retrieval budget metadata and a prompt budget warning when the system prompt exceeds 30,000 characters.
- `memory_search` tool behavior is unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_retrieval_policy.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- The budget applies only to automatic chat retrieval, not explicit tool calls.
- Prompt budget warnings are diagnostic only; they do not block generation or force prompt pruning outside retrieved memory context.
- Existing retrieved chunk ranking is preserved; this patch budgets ranked results but does not change ranking behavior.

## Follow-Up Work

- Consider adding a later explicit “deep memory” mode for broad recall requests.
- Consider exposing retrieval budget diagnostics in the frontend debug panel if not already visible through existing debug payload rendering.
- Consider additional source-type caps if artifact and conversation chunks need separate budgets.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Preserved raw memory/chunk architecture.
- Kept context construction inspectable through debug metadata.
- Did not modify `soul.md`.
- Did not rename `tir/`.
