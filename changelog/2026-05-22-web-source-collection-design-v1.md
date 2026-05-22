# Web Source Collection Design v1

## Summary

Added a design-only document for future general web source collection in Project Anam.

The design mirrors the Moltbook source collection approach: web sources are external context, search results are leads, fetched pages are source material, source text stays separate from interpretation, and raw source traces are not indexed into ChromaDB by default.

## Files Changed

- `docs/WEB_SOURCE_COLLECTION_DESIGN.md`
- `changelog/2026-05-22-web-source-collection-design-v1.md`

## Behavior Changed

No runtime behavior changed.

This patch documents the future source collection model only. It does not add CLI commands, runtime code, bounded research integration, indexing behavior, database schema changes, scheduler behavior, UI behavior, prompt behavior, guidance loading, or model configuration.

## Tests/Checks Run

- `git diff --check`

## Known Limitations

- No `web-source-preview` command exists yet.
- No bounded research `--use-web` integration exists yet.
- No robots policy runtime helper exists yet.
- Existing `web_fetch` is a safe direct fetch tool, but it is not itself a durable provenance/source-trace system.

## Follow-Up Work

- Implement standalone `web-source-preview`.
- Add compact web source trace generation.
- Add optional selected URL fetch with robots/paywall/unavailable-page handling.
- Add optional sidecar trace writing.
- Later add explicit bounded research `--use-web` integration.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign a fixed personality.
- Preserved raw source traces as provenance material rather than truth.
- Kept source-derived material traceable and provisional.
- Avoided DB schema changes and raw Chroma indexing.
- Avoided scheduler/autonomy, UI, prompt runtime, and guidance changes.
- Preserved the distinction between Project Anam, the legacy `tir/` package, and the unnamed entity.
