# Moltbook Source Preview Failure Handling v1

## Summary

Moltbook source preview now represents Moltbook collection failures as compact structured traces instead of collapsing them into a human-readable CLI failure. Timeout, HTTP status, and registry/tool failures are reported as inconclusive source collection failures.

## Files Changed

- `tir/research/moltbook_sources.py`
- `tests/test_moltbook_source_collection.py`
- `changelog/2026-05-21-moltbook-source-preview-failure-handling-v1.md`

## Behavior Changed

- Inner Moltbook tool failures now return traces with `collection_error=true`.
- Timeout failures are classified as `error_type=timeout`.
- HTTP status failures are classified as `error_type=http_error` and include `status_code` when available.
- Registry-level or unclassified failures are classified as `error_type=tool_error`.
- Failure traces keep `results=[]`, `omitted_count=0`, `omitted_reasons=[]`, `no_usable_results=false`, and `no_result_note=null`.
- Failure traces include the note: `This is not evidence that no relevant Moltbook material exists.`
- `--write-trace` writes structured failure traces as sidecar JSON without registering artifacts or indexing anything.
- CLI argument validation errors still raise normal command errors.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- No retry behavior was added.
- No timeout configuration flag was added.
- Failure traces use safe reconstructed Moltbook paths when the underlying tool does not provide a sanitized URL or path.

## Follow-Up Work

- Consider a separate timeout/retry design if live Moltbook instability continues.
- Consider enriching declarative HTTP failure metadata with sanitized status/path information in a dedicated tool-layer patch.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality or alter guidance.
- Preserved raw external tool failures as explicit source collection traces.
- Did not change bounded research, memory indexing, open loops, scheduler behavior, prompts, UI, or database schema.
- Preserved the read-only Moltbook boundary and did not add external writes.
