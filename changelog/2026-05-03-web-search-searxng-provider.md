# Web Search SearXNG Provider

## Summary

Replaced the `web_search` skill provider with a configurable local SearXNG HTTP JSON endpoint.

## Files Changed

- `requirements.txt`
- `tir/config.py`
- `skills/active/web_search/web_search.py`
- `tests/test_web_search_skill.py`
- `changelog/2026-05-03-web-search-searxng-provider.md`

## Behavior Changed

- Removed `duckduckgo-search` from project requirements.
- Added `TIR_SEARXNG_URL` configuration through `SEARXNG_URL`, defaulting to `http://127.0.0.1:8080`.
- Added `TIR_WEB_SEARCH_TIMEOUT_SECONDS` configuration through `WEB_SEARCH_TIMEOUT_SECONDS`, defaulting to `10`.
- `web_search(query, max_results=5)` now calls `{SEARXNG_URL}/search` with `q=<query>` and `format=json`.
- Preserved the existing tool name, schema, max-result cap, success shape, and failure shape.
- SearXNG results are normalized to title, URL, snippet, and source domain.
- Provider failures, timeouts, non-200 responses, non-JSON responses, and malformed result payloads return clear `ok: false` errors.

## Tests/Checks Run

- `.pyanam/bin/python -m pip install -r requirements.txt`
- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- Manual live query check against `http://127.0.0.1:8080/search`
- `git diff --check`

## Known Limitations

- Live manual checks returned connection refused from `127.0.0.1:8080`, so live SearXNG search results were not validated in this patch.
- The tool depends on a running SearXNG instance with JSON search enabled.
- This remains search only; it does not fetch or verify full pages.
- Search snippets are leads, not complete source evidence.
- Previously installed local packages are not automatically uninstalled from `.pyanam` just because they were removed from `requirements.txt`.

## Follow-Up Work

- Start or configure local SearXNG, then rerun live query checks.
- Add `web_fetch` separately after search behavior is stable.
- Consider provider health diagnostics later if SearXNG availability remains ambiguous.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md` or operational guidance.
- Did not change memory retrieval or indexing behavior.
- Did not add API routes, UI changes, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
- Kept external search as read-only outside-world lookup.
