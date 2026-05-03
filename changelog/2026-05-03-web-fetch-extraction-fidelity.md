# Web Fetch Extraction Fidelity

## Summary

Improved `web_fetch` extraction fidelity by merging visible HTML lead text when trafilatura omits important early article content.

## Files Changed

- `skills/active/web_search/web_search.py`
- `tests/test_web_search_skill.py`
- `changelog/2026-05-03-web-fetch-extraction-fidelity.md`

## Behavior Changed

- `web_fetch` still uses trafilatura as the preferred extractor.
- `web_fetch` now always computes a plain visible-text extraction from decoded HTML.
- If trafilatura output is present but appears to omit substantially longer leading visible content, `web_fetch` merges a bounded visible-text prefix with the trafilatura result.
- Public tool name, schema, and result shape are unchanged.
- URL safety, redirect blocking, timeout, byte cap, content-type rejection, title extraction, max character cap, and truncation behavior are preserved.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_url_prefetch.py tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- The merge heuristic is intentionally simple and may include some leading boilerplate on pages where navigation appears before article text.
- The tool does not expose extraction method metadata in the public result.
- This does not add browser rendering, crawling, redirects, or JavaScript execution.

## Follow-Up Work

- Tune visible-text merge heuristics using real fetched pages that show extraction gaps.
- Consider internal debug-only extraction metadata if future debugging needs it.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not change deterministic URL prefetch behavior.
- Did not add memory writes, artifacts, open loops, feedback, diagnostics, API routes, UI changes, autonomy, crawling, browser automation, or new dependencies.
