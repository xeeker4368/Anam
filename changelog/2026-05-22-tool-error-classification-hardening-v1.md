# Moltbook / Tool Error Classification Hardening v1

## Summary

Hardened declarative HTTP tool failure envelopes and Moltbook source collection failure classification so structured metadata is preferred over fragile error-string parsing.

## Files Changed

- `tir/tools/http_declarative.py`
- `tir/research/moltbook_sources.py`
- `tests/test_declarative_http_skills.py`
- `tests/test_moltbook_source_collection.py`
- `changelog/2026-05-22-tool-error-classification-hardening-v1.md`

## Behavior Changed

- Declarative HTTP request failures now include structured fields when available:
  - `error_class`
  - `error_type`
  - `status_code` for HTTP status failures
  - `url` for HTTP status failures when the response exposes it
- Timeout failures are classified as `error_type="timeout"`.
- Connection-style failures are classified as `error_type="network_error"`.
- HTTP non-200 responses are classified as `error_type="http_error"` with `error_class="HTTPError"`.
- Moltbook source preview now prefers structured `error_type`, `error_class`, and `status_code` fields before falling back to legacy string/regex parsing.
- Existing human-readable error strings are preserved.
- Authorization headers and bearer tokens are not copied into tool results or source traces.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Structured metadata is added for declarative HTTP runtime request/status/read failures. Registry-level Python tool exceptions still use the existing registry error envelope.
- URL metadata is included only where the response exposes a safe request URL; request headers and raw response payloads are not included.

## Follow-Up Work

- Consider extending structured error envelopes to non-HTTP registry tool crashes if future source collectors need cross-tool classification.
- Keep future web source collection aligned with these `error_type` values.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved source collection failure-vs-no-results semantics.
- Kept Moltbook read-only and did not add external write behavior.
- Did not change DB schema, Chroma schema, research loop behavior, prompts, guidance files, `soul.md`, model config, UI, or raw trace indexing behavior.
