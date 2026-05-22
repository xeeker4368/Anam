# Source Trace Ingestion Blocklist Verification v1

## Summary

Added explicit guardrails and regression tests proving raw source trace sidecars are provenance/audit files, not ingestible artifacts or retrievable memory.

## Files Changed

- `tir/artifacts/governance_blocklist.py`
- `tir/artifacts/ingestion.py`
- `tir/artifacts/service.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_artifact_ingestion.py`
- `tests/test_artifacts.py`
- `changelog/2026-05-22-source-trace-ingestion-blocklist-verification-v1.md`

## Behavior Changed

- Source trace paths under `workspace/research/source-traces/` are rejected by artifact registration helpers.
- Known source-trace filename suffixes are rejected:
  - `.moltbook-sources.json`
  - `.web-sources.json`
  - `.source-trace.json`
- Upload/generated artifact ingestion rejects source trace files before writing files, creating artifact rows, or indexing Chroma/FTS chunks.
- Ordinary research note artifact paths under `workspace/research/*.md` remain allowed.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- This patch blocks normal artifact ingestion/registration paths only. Source trace sidecars can still be written by their dedicated provenance/audit writers.
- The blocklist is intentionally narrow and does not reject ordinary JSON uploads unless they use source-trace paths or source-trace filename suffixes.

## Follow-Up Work

- Keep future web/image/media source trace naming aligned with the blocked suffix patterns.
- Add any future source-trace suffixes to the shared blocklist before enabling new source collection runtimes.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved raw source traces as audit/provenance sidecars rather than memory.
- Kept research notes indexable while blocking raw source trace JSON.
- Did not change DB schema, Chroma schema, research loop behavior, Moltbook/web behavior, prompts, guidance files, `soul.md`, model config, or UI.
