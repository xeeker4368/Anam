# URL Fetch Tool Guidance

## Summary

Strengthened runtime and skill guidance so URL-specific content questions use `web_fetch` before answering.

## Files Changed

- `OPERATIONAL_GUIDANCE.md`
- `skills/active/web_search/SKILL.md`
- `skills/active/web_search/web_search.py`
- `changelog/2026-05-03-url-fetch-tool-guidance.md`

## Behavior Changed

- Added URL-specific runtime guidance under real-time and external tools.
- Added web skill guidance requiring `web_fetch` for public URL summaries, page-content questions, article details, and claim verification about a specific URL.
- Updated the `web_fetch` tool description visible to the model with concise URL-content guidance.
- No tool implementation, schema, API, UI, memory, artifact, diagnostic, or autonomy behavior was changed.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- This is guidance, not hard routing. The model is still responsible for choosing the tool.
- No automated chat-level test currently verifies that a real model calls `web_fetch` for URL-summary prompts.
- `SKILL.md` body is not fully injected into the runtime prompt; the operational guidance and tool description carry the runtime weight.

## Follow-Up Work

- Manually verify chat behavior with a URL-summary prompt and confirm `web_fetch` appears in debug tool calls.
- Consider deterministic URL-intent routing only if guidance remains insufficient.
- Add chat-level model-behavior tests later if the project gets stable tool-call fixtures for URL prompts.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not change memory retrieval or indexing behavior.
- Did not add API routes, UI changes, tools, artifacts, open loops, feedback, diagnostics, autonomy, or self-modification.
- Reduced unsupported URL-content inference by strengthening source-appropriate tool-use guidance.
