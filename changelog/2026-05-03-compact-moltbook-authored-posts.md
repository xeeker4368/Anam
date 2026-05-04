# Compact Moltbook Authored Posts

## Summary

Compacted `moltbook_find_author_posts` results so authored-post discovery returns bounded summaries instead of full post bodies or raw payloads.

## Files Changed

- `skills/active/moltbook/moltbook.py`
- `tests/test_moltbook_search_semantics.py`
- `changelog/2026-05-03-compact-moltbook-authored-posts.md`

## Behavior Changed

- `moltbook_find_author_posts` keeps the same public tool name, arguments, and top-level result shape.
- `authored_posts` now contain compact post summary fields only:
  - `id`
  - `title`
  - `author_name`
  - `created_at`
  - `submolt`
  - `upvotes`
  - `downvotes`
  - `comment_count`
  - `content_preview`
  - `url`
- `mentions` and `other_results` use similarly compact post-like shapes.
- `profiles` now return compact profile summaries.
- Full post bodies and `raw` payloads are no longer included in normal discovery output.
- `content_preview` is capped at 400 characters.
- The note now points users to `moltbook_read_post` for full content by post id.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_search_semantics.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- Discovery results are intentionally lossy. Use `moltbook_read_post` for full post content.
- The wrapper still returns at most the existing bounded result count and does not add pagination.

## Follow-Up Work

- Consider adding explicit pagination/cursor support if complete author archives are needed.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not add tools, endpoints, UI, DB schema, memory architecture changes, write actions, autonomy, or self-modification.
