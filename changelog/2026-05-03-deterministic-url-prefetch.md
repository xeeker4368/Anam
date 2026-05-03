# Deterministic URL Content Prefetch

## Summary

Added deterministic backend `web_fetch` prefetch for URL-content questions before the model generates an answer.

## Files Changed

- `tir/engine/url_prefetch.py`
- `tir/api/routes.py`
- `tests/test_url_prefetch.py`
- `changelog/2026-05-03-deterministic-url-prefetch.md`

## Behavior Changed

- Detects HTTP/HTTPS URL mentions paired with page/article/content intent.
- Runs `web_fetch` before the main agent loop for matching chat messages.
- Emits normal `tool_call` and `tool_result` stream events for deterministic prefetch.
- Passes fetched page text or fetch failure text into the model context before answer generation.
- Includes deterministic prefetch in tool call count timing/debug data.
- Combines deterministic prefetch trace with model-driven tool trace only when a real assistant message is persisted.
- Fetches only the first matching URL in v1.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_url_prefetch.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_web_search_skill.py -v`
- `git diff --check`

## Known Limitations

- URL-content intent detection uses conservative keyword and phrase rules, so false negatives remain possible.
- Some generic URL mentions may still be ambiguous and require later tuning.
- Multiple URLs are not all fetched; v1 fetches only the first matching URL.
- Deterministic prefetch is wired only into the Web/API chat stream path.

## Follow-Up Work

- Tune intent rules based on manual chat transcripts.
- Consider fetching multiple URLs if comparison or multi-source prompts become common.
- Consider shared helper behavior if future non-Web chat paths need the same deterministic prefetch.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not change memory retrieval, indexing, schema, artifacts, open loops, feedback, diagnostics, or autonomy.
- Preserved tool traces as inspectable provenance without storing prefetch as standalone memory.
