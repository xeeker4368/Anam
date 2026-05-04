# Moltbook Authored Posts Discovery

## Summary

Added a read-only Moltbook authored-post discovery path using the posts feed author filter, with profile `recentPosts` fallback for the existing author-post wrapper.

## Files Changed

- `skills/active/moltbook/SKILL.md`
- `skills/active/moltbook/skill.yaml`
- `skills/active/moltbook/moltbook.py`
- `tests/test_moltbook_declarative_skill.py`
- `tests/test_moltbook_search_semantics.py`
- `changelog/2026-05-03-moltbook-authored-posts-discovery.md`

## Behavior Changed

- Added `moltbook_posts_by_author`, a read-only declarative GET tool for `GET /api/v1/posts?author=...`.
- Updated Moltbook guidance so author-specific post requests use `moltbook_posts_by_author` or `moltbook_find_author_posts`, not semantic search.
- Updated `moltbook_find_author_posts` to use `/api/v1/posts?author=<author>&sort=new&limit=<limit>` as its primary source.
- The wrapper verifies returned author fields case-insensitively and does not blindly trust endpoint results with mismatched authors.
- If no authored posts are found from the primary source, the wrapper falls back to `/api/v1/agents/profile?name=<author>` and uses profile `recentPosts` as authored posts for that profile.
- The wrapper no longer uses semantic `/search` for authored-post discovery.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_search_semantics.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

Manual check:

- Skipped live `MOLTBOOK_TOKEN` tool check because `MOLTBOOK_TOKEN` was not configured in the shell environment.

## Known Limitations

- The `author` query parameter works in live probing but is not currently documented in Moltbook `skill.md`.
- Profile `recentPosts` is only a recent subset, not a full historical author archive.
- Pagination/cursor traversal for complete author archives is not implemented in this patch.
- Mentions and profiles are not populated from semantic search in `moltbook_find_author_posts`; use `moltbook_search` separately for semantic discovery.

## Follow-Up Work

- Add cursor support if full historical authored-post retrieval becomes necessary.
- Revisit the wrapper if Moltbook documents a dedicated author archive endpoint.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not add posting, commenting, voting, following, moderation, write endpoints, UI, API routes, DB schema, memory writes, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
