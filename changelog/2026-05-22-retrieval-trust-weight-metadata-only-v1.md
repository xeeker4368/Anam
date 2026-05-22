# Retrieval Trust Weight Metadata-Only v1

## Summary

Stopped applying `source_trust` as a hidden final retrieval ranking multiplier. `source_trust` remains stored and visible as provenance/debug metadata, but it no longer silently downranks research notes, uploaded sources, or other source-derived continuity artifacts.

## Files Changed

- `tir/memory/retrieval.py`
- `tests/test_retrieval.py`
- `changelog/2026-05-22-retrieval-trust-weight-metadata-only-v1.md`

## Behavior Changed

- Hybrid retrieval still uses Chroma vector search plus FTS5/BM25 fused with Reciprocal Rank Fusion.
- Final `adjusted_score` now starts as the unweighted `rrf_score`.
- `source_trust` remains in chunk metadata and context debug output.
- Research notes tagged `source_trust="thirdhand"` are no longer penalized by the old `0.7` multiplier.
- Uploaded/source-derived materials are no longer penalized by hidden trust multipliers.
- Explicit artifact-intent boosts still apply when `artifact_intent=True`.
- Context labels remain unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_retrieval.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- The `source_trust` field name is preserved for compatibility; this patch does not rename it to `source_distance` or `source_derivation`.
- `TRUST_WEIGHTS` remains defined in configuration for now, but the default retrieval path no longer uses it as a ranking multiplier.
- The `trust_weights` retrieval argument remains as a compatibility no-op.

## Follow-Up Work

- Consider renaming or re-framing `source_trust` in a future migration/design pass if the vocabulary keeps implying factual authority.
- Consider removing unused `TRUST_WEIGHTS` configuration only after checking any external callers or operator expectations.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved source labels as visible provenance instead of hidden truth/ranking control.
- Kept research notes available as continuity artifacts without source-derived downranking.
- Did not change DB schema, Chroma schema, indexing assignments, context labels, prompts, guidance files, `soul.md`, model config, UI, research behavior, or Moltbook/web behavior.
