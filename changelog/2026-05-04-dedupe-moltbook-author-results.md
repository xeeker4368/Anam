# Deduplicate Moltbook Author Results

## Summary

Deduplicated `moltbook_find_author_posts` results so verified authored posts do not also appear in `other_results`.

## Files Changed

- `skills/active/moltbook/moltbook.py`
- `tests/test_moltbook_search_semantics.py`
- `changelog/2026-05-04-dedupe-moltbook-author-results.md`

## Behavior Changed

- `moltbook_find_author_posts` now tracks dedupe keys while building result buckets.
- Verified authored posts are not duplicated in `other_results`.
- Duplicate profile fallback posts are skipped when their IDs or title/date keys have already been included.
- Duplicate `other_results` are avoided where practical.
- Mismatched-author posts can still appear in `other_results`.
- Compact result output and top-level result shape are preserved.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_search_semantics.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- Title plus `created_at` dedupe is a fallback heuristic for posts without stable IDs.
- Posts without IDs and without both title and `created_at` cannot be reliably deduplicated.

## Follow-Up Work

- Prefer stable post IDs from Moltbook whenever available.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not change tool schemas, endpoints, UI, API routes, DB schema, memory architecture, write behavior, autonomy, or self-modification.
