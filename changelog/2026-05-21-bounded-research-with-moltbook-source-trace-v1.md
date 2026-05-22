# Bounded Research With Moltbook Source Trace v1

## Summary

Manual bounded open-loop research can now explicitly collect compact read-only Moltbook source traces and use them as bounded research context. Moltbook remains external context rather than factual authority, and raw source traces are not registered or indexed.

## Files Changed

- `tir/research/bounded.py`
- `tir/admin.py`
- `tests/test_research_bounded.py`
- `tests/test_admin.py`
- `docs/PROMPT_INVENTORY.md`
- `changelog/2026-05-21-bounded-research-with-moltbook-source-trace-v1.md`

## Behavior Changed

- Added `research-open-loop-run --use-moltbook`.
- Added Moltbook query mode with `--moltbook-query`.
- Added Moltbook feed mode with `--moltbook-feed`.
- Added `--moltbook-limit` and `--moltbook-sort`.
- Moltbook flags are rejected unless `--use-moltbook` is present.
- `--use-moltbook` requires exactly one of query or feed.
- Dry-runs collect and inject compact Moltbook context but write no notes, traces, artifacts, or metadata.
- Write mode writes the compact Moltbook source trace sidecar before writing the research note.
- Register mode registers and indexes the research note only; raw Moltbook source traces are not registered or indexed.
- Bounded research prompts now include explicit Moltbook source-boundary language when Moltbook is used.
- Research artifact metadata records Moltbook trace path, source count, collection error state, no-result state, and metadata-only verification status.
- Open-loop completion metadata records last Moltbook trace path, source count, and collection error state after durable success.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`

## Known Limitations

- No scheduler or autonomous Moltbook research integration was added.
- No Moltbook comments or full post reads were added.
- No Moltbook write/post/comment/vote/follow/profile capabilities were added.
- Moltbook source traces may remain as orphan sidecars if trace writing succeeds and a later note write fails; open-loop metadata still does not advance.

## Follow-Up Work

- Consider a later patch for controlled read-post/comment expansion.
- Consider source trace cleanup tooling if orphan sidecars become common.
- Consider bounded web-source collection separately from Moltbook.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality or alter behavioral guidance.
- Preserved Moltbook as read-only external context.
- Preserved raw source provenance and did not treat Moltbook as factual authority.
- Did not change DB schema, scheduler/autonomy, UI, prompts outside bounded research construction, or Moltbook write behavior.
