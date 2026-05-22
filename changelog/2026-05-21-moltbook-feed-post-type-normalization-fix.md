# Moltbook Feed Post Type Normalization Fix

## Summary

Fixed feed source preview recognition for direct `moltbook_feed` post objects whose `type` field describes the post/content kind rather than a search result kind.

## Files Changed

- `tir/research/moltbook_sources.py`
- `tests/test_moltbook_source_collection.py`
- `changelog/2026-05-21-moltbook-feed-post-type-normalization-fix.md`

## Behavior Changed

- Feed mode now accepts direct feed dictionaries as post candidates unless they explicitly identify as comment, agent, profile, submolt, or mention results.
- Search mode remains strict and continues to omit mixed non-post result types.
- Existing compact source output, spam filtering, verification metadata-only handling, read-only registry dispatch, and no-result behavior are preserved.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_moltbook_source_collection.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest`

## Known Limitations

- Live Moltbook dispatch could not be run from this Codex subprocess because `MOLTBOOK_TOKEN` was not available in the shell environment.
- Timeout/retry handling remains deferred.

## Follow-Up Work

- Re-run `moltbook-source-preview --feed --limit 3` in the token-configured shell to confirm live compaction.
- If live feed items use another wrapper shape, add a fixture from that confirmed shape in a separate narrow patch.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Kept Moltbook read-only.
- Did not add bounded research integration, research notes, open loops, DB schema changes, Chroma indexing, prompts, guidance, scheduler, UI, or Moltbook write behavior.
