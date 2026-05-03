# Declarative HTTP Skills v1.1 Path Templates And Defaults

## Summary

Extended declarative HTTP skills with safe read-only URL path templates and top-level JSON Schema defaults.

## Files Changed

- `tir/tools/http_declarative.py`
- `tests/test_declarative_http_skills.py`
- `changelog/2026-05-03-declarative-http-skills-v1-1-path-templates-defaults.md`

## Behavior Changed

- Declarative HTTP tools can now use simple `{arg}` placeholders in URL paths.
- Path placeholder values come from validated arguments plus applied top-level defaults.
- Path placeholder values are encoded as single path segments, so slashes become `%2F`.
- Placeholders outside the URL path are rejected.
- Malformed or unknown placeholders fail loudly at skill load time.
- Missing required path values fail as an `ok:false` tool result without making a request.
- Top-level JSON Schema `default` values are applied for missing optional args before path and query mapping.
- Existing GET-only, read-only, no-redirect, env-only auth, byte-cap, and normalized response behavior is preserved.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_declarative_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- Defaults apply only to top-level `args_schema.properties`; nested defaults are not applied.
- Tool traces still reflect registry-normalized args and do not include executor-applied defaults.
- Path templating is limited to simple `{arg}` replacement; no expressions or path-template conditionals are supported.
- Declarative HTTP remains GET-only and read-only.

## Follow-Up Work

- Add Moltbook read-only path-template endpoints in a separate patch.
- Consider whether tool trace should include executor-applied defaults in a later observability patch.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not rename `tir/`.
- Did not add POST, write/action tools, approval flow, UI, API-key management, DB schema, remote skill installation, memory writes, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
