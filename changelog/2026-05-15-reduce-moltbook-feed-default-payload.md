# Reduce Moltbook Feed Default Payload

## Summary

Reduced broad Moltbook feed reads by making `moltbook_feed.limit` optional with a smaller default.

## Files Changed

- `skills/active/moltbook/skill.yaml`
- `tests/test_moltbook_declarative_skill.py`
- `changelog/2026-05-15-reduce-moltbook-feed-default-payload.md`

## Behavior Changed

- `moltbook_feed` now defaults to `limit=10` when no limit is supplied.
- `moltbook_feed.limit` is no longer required by the tool schema.
- `moltbook_feed.limit.maximum` is now `20`.
- Explicit `moltbook_feed` limits still work within the allowed range.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest`

## Known Limitations

- Feed results are still returned as the raw Moltbook API payload.
- If the model explicitly requests `limit=20`, the tool will still allow that maximum.

## Follow-Up Work

- Design a separate Moltbook result compaction/truncation path if raw feed payloads remain too large.

## Project Anam Alignment Check

- Does not assign the entity a name or personality.
- Preserves Moltbook read-only behavior.
- Does not alter memory authority, retrieval ranking, research behavior, prompts, or runtime guidance.
