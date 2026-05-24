# Embedding Dimension Guard v1

## Summary

Added an explicit embedding-dimension guard before ChromaDB chunk upserts so an embedding model/config mismatch cannot silently write incompatible vectors into the vector index.

## Files Changed

- `tir/config.py`
- `config/defaults.toml`
- `tir/memory/chroma.py`
- `tests/test_chroma.py`
- `changelog/2026-05-22-embedding-dimension-guard-v1.md`

## Behavior Changed

- The expected embedding dimension is now explicit in configuration as `embedding.expected_dimension = 768`.
- `tir.memory.chroma.upsert_chunk(...)` validates generated or precomputed embeddings before acquiring the Chroma collection and before calling `collection.upsert(...)`.
- Wrong-dimensional embeddings raise `EmbeddingDimensionError` with the expected dimension, actual dimension, and embedding model name.
- Valid 768-dimensional embeddings continue to write through the existing Chroma upsert path.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_chroma.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_chroma.py -v` (optional file absent; no tests collected)
- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_research_bounded.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- This patch guards Chroma writes. It does not migrate existing vectors or change the configured embedding model.
- There is no batch Chroma upsert helper in the current code path; the guard covers the single-chunk write boundary used by conversation, research, journal, and artifact indexing.

## Follow-Up Work

- If a batch upsert API is added later, validate every embedding in the batch before performing any write.
- If the embedding model changes, update `embedding.expected_dimension` alongside the model change.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved raw experience by preventing malformed vector writes from corrupting retrieval memory.
- Did not change DB schema, Chroma schema, retrieval ranking, research behavior, Moltbook/web behavior, prompts, guidance files, `soul.md`, model config values, or UI.
