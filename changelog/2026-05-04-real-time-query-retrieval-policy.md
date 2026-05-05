# Real-Time Query Retrieval Policy

## Summary

Added a narrow retrieval policy so direct real-time or source-specific external-state questions skip normal memory retrieval, letting live tool results dominate context.

## Files Changed

- `tir/engine/retrieval_policy.py`
- `tir/api/routes.py`
- `tests/test_retrieval_policy.py`
- `tests/test_api_agent_stream.py`

## Behavior Changed

- URL-content questions that trigger deterministic `web_fetch` now skip normal memory retrieval.
- Direct Moltbook external-state prompts now skip normal memory retrieval.
- Direct web/latest/current prompts now skip normal memory retrieval.
- Normal Project Anam, implementation, continuity, and ordinary chat prompts keep existing retrieval behavior.
- The initial debug event now includes `retrieval_policy` with `mode` and `reason`.
- Existing `retrieval_skipped` debug behavior remains for frontend compatibility.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_retrieval_policy.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_url_prefetch.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py -v`
- `git diff --check`

## Known Limitations

- This does not force Moltbook tool calls; it only prevents stale or unrelated memories from competing in obvious real-time/source-specific turns.
- The v1 policy uses conservative keyword rules rather than a planner.
- There is no reduced-retrieval mode yet; prompts are either normal retrieval or skipped retrieval.

## Follow-Up Work

- Consider deterministic Moltbook routing if metadata/guidance plus retrieval policy remain insufficient.
- Consider a per-call retrieval limit if a future patch needs a true reduced-memory mode.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved raw experience and memory architecture.
- Did not change Chroma/FTS retrieval internals.
- Did not add tools, API routes, UI, database schema, autonomy, or a broad planner.
- Did not modify `soul.md`.
- Did not rename `tir/`.
