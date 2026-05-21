# Moltbook Source Preview Feed Normalization Fix v1

## Summary

Fixed `moltbook-source-preview --feed` normalization so direct feed post objects from `moltbook_feed` are compacted as `moltbook_post` source records instead of being omitted as `non_post_result`.

## Files Changed

- `tir/research/moltbook_sources.py`
- `tests/test_moltbook_source_collection.py`
- `changelog/2026-05-21-moltbook-source-preview-feed-normalization-fix-v1.md`

## Behavior Changed

- Feed mode now treats direct dictionary results from `moltbook_feed` as post candidates unless they explicitly identify as comment, agent, profile, submolt, or mention results.
- Search mode remains stricter and continues omitting non-post mixed search results.
- Feed compaction now supports `name` as a title fallback and `body`/`text` as excerpt fallbacks.
- Spam filtering, verification metadata-only handling, no-result behavior, read-only registry dispatch, and compact-only output are preserved.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest`

## Known Limitations

- No timeout or retry handling was changed.
- Comments, agents, profiles, submolts, and mentions remain omitted in v1 source preview.
- No full post body reads are supported in this patch.

## Follow-Up Work

- Consider a separate timeout/retry policy patch for intermittent Moltbook read timeouts.
- Consider explicit selected post reads and comment collection only in later approved patches.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Kept Moltbook read-only.
- Preserved source/provenance boundaries.
- Did not add bounded research integration, research note creation, open-loop behavior, DB schema changes, Chroma indexing, prompts, guidance, scheduler, UI, or Moltbook write behavior.
