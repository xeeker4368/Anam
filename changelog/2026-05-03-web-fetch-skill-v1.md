# Web Fetch Skill v1

## Summary

Added a read-only `web_fetch` tool to fetch and extract readable text from one public web page.

## Files Changed

- `skills/active/web_search/SKILL.md`
- `skills/active/web_search/web_search.py`
- `tests/test_web_search_skill.py`
- `changelog/2026-05-03-web-fetch-skill-v1.md`

## Behavior Changed

- Added `web_fetch(url, max_chars=12000)` to the existing active web skill package.
- Preserved `web_search` behavior and interface.
- `web_fetch` accepts only public `http` and `https` URLs.
- `web_fetch` rejects localhost, `.localhost`, literal private/local/link-local/reserved/multicast IP URLs, and URLs with embedded credentials.
- Requests use timeout, explicit headers, `stream=True`, and `allow_redirects=False`.
- Responses are capped at 2 MB before extraction.
- Clearly binary/non-text content types are rejected.
- `trafilatura` is used for readable text extraction when available, with simple title/text fallback extraction.
- Returned text is capped to `max_chars` clamped to 1,000..30,000 characters.
- No DB writes, memory indexing, artifacts, open loops, feedback, diagnostics, API routes, UI changes, crawling, browser automation, or autonomy were added.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- Manual check: `web_fetch("https://example.com", max_chars=2000)`
- `git diff --check`

## Known Limitations

- DNS resolution is not used for private-network detection in v1; only localhost names and literal IP addresses are rejected before fetch.
- Redirects are disabled, so pages requiring redirects return a non-200/redirect status instead of following.
- Extraction quality depends on page structure and `trafilatura`.
- JavaScript-rendered content is not available because this is not browser automation.
- This tool fetches one supplied URL only; it is not a crawler.

## Follow-Up Work

- Add redirect handling only if a later safety review approves validating redirect targets.
- Add `web_fetch` result storage as artifacts/memory only through a separate intentional ingestion design.
- Add provider diagnostics later if repeated fetch failures should become diagnostic issues.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md` or operational guidance.
- Did not change memory retrieval or indexing behavior.
- Did not add artifacts, open loops, feedback, diagnostics, autonomy, self-modification, API routes, or UI changes.
- Kept external page reading bounded, read-only, and explicit.
