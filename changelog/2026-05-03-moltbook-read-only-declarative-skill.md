# Moltbook Read-Only Declarative Skill

## Summary

Added Moltbook as the first real read-only declarative HTTP skill using local `SKILL.md` plus `skill.yaml`.

## Files Changed

- `skills/active/moltbook/SKILL.md`
- `skills/active/moltbook/skill.yaml`
- `tests/test_moltbook_declarative_skill.py`
- `changelog/2026-05-03-moltbook-read-only-declarative-skill.md`

## Behavior Changed

- Registered four read-only Moltbook declarative GET tools:
  - `moltbook_feed`
  - `moltbook_search`
  - `moltbook_profile`
  - `moltbook_me`
- Moltbook tools use `MOLTBOOK_TOKEN` through `bearer_env` auth.
- Missing `MOLTBOOK_TOKEN` returns the existing declarative executor `ok:false` result without making a request.
- No posting, comments, voting, following, registration, profile edits, moderation, identity-token operations, path-template endpoints, UI, API routes, database schema, memory writes, artifacts, open loops, feedback, diagnostics, or autonomy were added.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- Only read-only GET endpoints that fit declarative HTTP v1 are included.
- Dynamic path endpoints such as reading a single post or comments are deferred until path templating exists.
- JSON-schema defaults are not applied by declarative HTTP v1, so query arguments are required explicitly.
- No live Moltbook API calls are made in tests.

## Follow-Up Work

- Add path templating in a later declarative HTTP v2 before single-post/comment/submolt endpoints.
- Design explicit approval and safety gates before any write/action Moltbook capability.
- Add UI/API-key management only after the local declarative skill path has more runtime mileage.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not add write/action behavior, UI, API routes, DB schema, memory writes, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
- Preserved Moltbook as read-only tool/provenance access, not automatic memory.
