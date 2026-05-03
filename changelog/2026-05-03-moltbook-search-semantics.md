# Moltbook Search Semantics

## Summary

Added a read-only Moltbook search semantics wrapper that separates authored posts from mentions, profiles, and other mixed search results.

## Files Changed

- `skills/active/moltbook/SKILL.md`
- `skills/active/moltbook/skill.yaml`
- `skills/active/moltbook/moltbook.py`
- `tests/test_moltbook_search_semantics.py`
- `changelog/2026-05-03-moltbook-search-semantics.md`

## Behavior Changed

- `moltbook_search` remains available but its description now warns that results are mixed and not a reliable posts-by-author filter.
- Added `moltbook_find_author_posts`, a read-only wrapper around Moltbook search.
- The wrapper returns separate buckets:
  - `authored_posts`
  - `mentions`
  - `profiles`
  - `other_results`
- A result is treated as an authored post only when it is post-like and an author field matches the requested author case-insensitively.
- The wrapper returns an explicit note explaining that Moltbook search is mixed-type and not a strict author filter.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_search_semantics.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- The wrapper can only classify results returned by Moltbook search; it is not a complete author archive.
- Live Moltbook result shapes may vary, so classification is defensive and preserves compact raw result data.
- This adds a Python wrapper because declarative HTTP cannot inspect and reshape nested JSON result semantics.

## Follow-Up Work

- Live-test `moltbook_find_author_posts` against known Moltbook authors.
- Tune classification if live result shapes expose additional author/type fields.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not add posting, commenting, voting, following, moderation, write endpoints, API routes, UI, DB schema, memory writes, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
