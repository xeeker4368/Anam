# Web Search Skill v1

## Summary

Added a small read-only `web_search` active skill for current outside-world public search.

## Files Changed

- `requirements.txt`
- `skills/active/web_search/SKILL.md`
- `skills/active/web_search/web_search.py`
- `tests/test_web_search_skill.py`
- `changelog/2026-05-03-web-search-skill-v1.md`

## Behavior Changed

- Added `duckduckgo-search` as the search provider dependency.
- Added an active `web_search` tool with `query` and bounded `max_results` arguments.
- Search results are returned as compact metadata: title, URL, snippet, and source domain.
- Empty searches return `ok: true` with an empty results list.
- Provider failures return a clear `ok: false` error envelope.
- No page fetching, DB writes, memory indexing, artifacts, open loops, feedback, diagnostics, API routes, or UI changes were added.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pip install -r requirements.txt`
- `.pyanam/bin/python -c "from duckduckgo_search import DDGS; import inspect; print(inspect.signature(DDGS))"`
- `git diff --check`

## Known Limitations

- This is search only; it does not fetch or verify full pages.
- Search snippets are leads, not complete source evidence.
- Runtime search depends on the DuckDuckGo search provider and network availability.
- Successful tool traces remain normal chat/debug provenance and are not automatically stored as memory.

## Follow-Up Work

- Add `web_fetch` separately after search behavior is validated.
- Consider configurable provider settings if provider reliability becomes an issue.
- Add explicit search budgets/policies later for autonomous use; this patch is live tool availability only.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md` or operational guidance.
- Did not change memory retrieval or indexing behavior.
- Did not add autonomy or self-modification.
- Kept external search as read-only outside-world lookup.
