# Moltbook Read-Only Path Tools

## Summary

Expanded the local Moltbook declarative skill with read-only path-template GET tools enabled by Declarative HTTP Skills v1.1.

## Files Changed

- `skills/active/moltbook/SKILL.md`
- `skills/active/moltbook/skill.yaml`
- `tests/test_moltbook_declarative_skill.py`
- `changelog/2026-05-03-moltbook-read-only-path-tools.md`

## Behavior Changed

- Added five read-only Moltbook GET tools:
  - `moltbook_read_post`
  - `moltbook_post_comments`
  - `moltbook_submolt`
  - `moltbook_submolt_feed`
  - `moltbook_submolt_moderators`
- Path arguments are handled through declarative HTTP v1.1 path templates and encoded as single URL path segments.
- `moltbook_post_comments` defaults to `sort=top` and `limit=25`.
- `moltbook_submolt_feed` defaults to `sort=hot` and `limit=25`.
- All tools remain read-only, GET-only, no-redirect, env-authenticated with `MOLTBOOK_TOKEN`, and response-size capped.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- No write/action Moltbook tools were added.
- No custom Python Moltbook tool was added.
- Tests mock requests and do not make live Moltbook API calls.
- Tool traces do not include executor-applied defaults.

## Follow-Up Work

- Live-test each new read-only tool with `MOLTBOOK_TOKEN`.
- Design explicit approval and safety gates before any future write/action Moltbook capability.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not add POST, write/action endpoints, custom Python tools, UI, API routes, DB schema, memory writes, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
