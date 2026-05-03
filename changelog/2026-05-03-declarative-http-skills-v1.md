# Declarative HTTP Skills v1

## Summary

Added a safe local declarative HTTP skill foundation for read-only GET tools defined by `SKILL.md` plus `skill.yaml`.

## Files Changed

- `tir/tools/http_declarative.py`
- `tir/tools/registry.py`
- `tests/test_declarative_http_skills.py`
- `changelog/2026-05-03-declarative-http-skills-v1.md`

## Behavior Changed

- Active skill folders can now include an optional `skill.yaml`.
- Valid declarative HTTP tools are registered as normal `ToolDefinition` entries.
- Declarative tools execute safe read-only HTTP GET requests with timeout, redirect blocking, response byte caps, query mapping, and env-only auth.
- Malformed active `skill.yaml` files fail loudly at registry load/startup.
- Existing Python `@tool` skills continue to load through the existing path.
- No API routes, UI, database schema, memory behavior, or autonomous behavior changed.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py tests/test_web_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- v1 supports GET only.
- v1 supports query-parameter templating only, not path templating or request bodies.
- v1 does not resolve DNS, so hostname-based private-network protection is limited to localhost-style names and literal IP addresses.
- v1 has no approval flow, UI, API key management, remote skill loading, or write/action tools.

## Follow-Up Work

- Add UI/API-key management only after this local executor has more runtime mileage.
- Consider a separate approval-gated design before any write/action HTTP tools.
- Consider DNS-aware private-network checks if hostname SSRF risk becomes relevant.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not add Moltbook, UI, write tools, API routes, database schema, memory writes, autonomy, or self-modification.
- Preserved local-only active skill loading and avoided arbitrary remote code execution.
