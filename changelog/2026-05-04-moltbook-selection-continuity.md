# Moltbook Read-by-Selection Continuity

## Summary

Added compact Moltbook selection continuity so follow-up turns like "read the first one" can resolve the correct post id after `moltbook_find_author_posts` returns authored posts.

## Files Changed

- `tir/engine/agent_loop.py`
- `tir/engine/tool_trace_context.py`
- `tir/api/routes.py`
- `skills/active/moltbook/SKILL.md`
- `tests/test_moltbook_selection_continuity.py`

## Behavior Changed

- `moltbook_find_author_posts` tool traces now include bounded selection metadata for authored posts: index, id, title, author name, created timestamp, and submolt.
- Chat history construction now injects the latest compact Moltbook selection context before the current user message when available.
- The injected context is bounded to the latest selection and at most 10 posts.
- Full tool results, raw payloads, full content, and long previews are not replayed into model context.
- Moltbook skill guidance now instructs follow-up read/summarize/open requests to call `moltbook_read_post` with the selected post id.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_selection_continuity.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_search_semantics.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `git diff --check`

## Known Limitations

- Selection continuity currently covers compact metadata from `moltbook_find_author_posts`.
- It does not add a broad planner or stateful selection tool.
- It does not replay full Moltbook content; full post reading still requires `moltbook_read_post`.

## Follow-Up Work

- Consider similar compact selection context for other list-producing real-time tools if repeated follow-up failures appear.
- Consider extending compact metadata to declarative `moltbook_posts_by_author` if that tool is commonly used directly.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved raw experience and existing memory architecture.
- Kept Moltbook access read-only.
- Did not add UI, API routes, database schema, autonomy, or a broad planner.
- Did not modify `soul.md`.
- Did not rename `tir/`.
