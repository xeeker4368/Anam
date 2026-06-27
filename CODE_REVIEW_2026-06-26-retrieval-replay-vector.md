# Part A — Retrieval-replay vector (investigation, verify-only)

**Date:** 2026-06-26 · **Mode:** verify-only. No code changed for Part A. Proposed fix is described, **not implemented**.

**Symptom:** In a clean test, the entity reproduced a real stored artifact block (`anam_generated_00007_`, real ID `0a2a95f5-667d-4ec1-b9e3-6de9ad09ab8a`, full real SHA256) when asked to generate a rainbow — **no tool call, no dispatch in the console.**

**Hypothesis (confirmed):** the full `[Artifact source: ...]` provenance block is indexed verbatim into memory, auto-retrieval injects it back into the prompt, and the model copies it.

---

## NORTH_STAR check
Aligned. Investigating this protects **Invariant 4** (the entity must distinguish what it *experienced/created* from what it *ingested/fabricated*) and the legible-substrate principle. No conflict.

---

## Finding 1 — What text is written into the chunk (it IS a replayable block)

`tir/memory/artifact_indexing.py::index_artifact_file` **always** writes an event chunk for every artifact (including generated images), id `artifact_{artifact_id}_event`, whose text is built by `_event_text(...)` (lines 74–154). That text is the full verbatim provenance block:

```
Artifact source: {title}
Artifact ID: {artifact_id}          ← real UUID
File: {filename}                    ← anam_generated_00007_*.png
Stored path: {path}
Source: {source}
Origin / Source role / MIME / Size
SHA256: {sha256}                    ← full real digest
Media kind: generated_image
Generation prompt (provenance metadata): {prompt}   ← "...rainbow..."
Generation seed: {seed}
Generation dimensions: {w}x{h}
```

This is **not** a lean reference — it is a complete, authoritative-looking, copyable record. It is dual-indexed and retrievable: `_store_artifact_chunk` (lines 176–200) calls **both** `upsert_chunk` (Chroma vector store, `chroma.py:142` — stores the text as `documents=[text]` + embedding) **and** `upsert_chunk_fts` (BM25/FTS, `db.py:865`). So the block is findable by both semantic and keyword search.

## Finding 2 — context.py:306 injects it verbatim into the model prompt

Normal retrieval/context-build pulls `source_type == "artifact_document"` chunks into the model-visible prompt. `tir/engine/context.py:292–308`:

```python
elif source_type == "artifact_document":
    ...
    formatted_chunks.append(
        f"[Artifact source: {title}, role: {source_role}, origin: {origin}, "
        f"file: {filename}]\n{text}"          # <-- {text} is the FULL _event_text block
    )
```

The wrapper header (`[Artifact source: title, role, origin, file]`) is prepended, and the entire chunk body (`{text}`) — including the real ID, full SHA256, prompt, and seed — is appended verbatim into the prompt. Retrieval includes artifact_document chunks (`retrieval.py:29,164–169`, with an `artifact_intent` boost). So asking "generate a rainbow" BM25/vector-matches the prior rainbow artifact's event chunk (its `Generation prompt` line contains "rainbow") and injects the whole block.

## Finding 3 — The replay turn issued NO tool call (confirmed from live data)

Queried `data/prod/archive.db` (and `working.db`) for assistant messages referencing the artifact:

- **Genuine generation turn:** `tool_trace` = a real `image_generate` call → `artifact_id: 0a2a95f5-...`, `artifact_title: anam_generated_00007_.png`, path `generated/2026/06/25/0a2a95f5-.../...`. (Real.)
- **Replay turn:** `tool_trace = NULL`, content reproduces the block verbatim:
  ```
  [Artifact source: anam_generated_00007_.png, role: Generated artifact, origin: Generated, file: anam_generated_00007_.png]
  Artifact source: anam_generated_00007_.png
  Artifact ID: 0a2a95f5-667d-4ec1-b9e3-6de9ad09ab8a
  ...
  SHA256: c79bbe55233cf9da2a5745154121e919ddbbb8bcc6e9aa7df52d2837d65b5fc
  Generation prompt (provenance metadata): A vibrant, brilliant rainbow ...
  ```
  **No tool call.** Pure retrieval-replay. The header line matches `context.py:306` exactly and the body matches `_event_text` exactly — the model copied the retrieval-injected text.

A second replay message shows the **confabulation** variant (invented ID `c9d8e7f6-...`, truncated SHA) — the same block used as a *template* with forged values. So both failure modes (verbatim replay of a real block, and fabrication in its format) flow from the same root: the full block is present as model-visible text.

## Conclusion

**Yes — the indexed unit is a replayable provenance block, and this is the vector.** The verbatim `_event_text` block (real ID + full SHA + path + prompt + seed) is indexed, retrieved on a topically-matching turn, and injected into the prompt by `context.py:306`, where the model reproduces it with no tool call.

---

## Proposed minimal fix (DO NOT IMPLEMENT — out of scope here)

Index a **lean reference**, not the forgeable block. The change is localized to `_event_text` in `tir/memory/artifact_indexing.py` (the chunk *text* only; metadata/ingestion/chunking untouched).

- **Option A (task's suggestion — leanest):** event chunk text = `artifact_id` + `title` only. Removes File/Stored path/**SHA256**/seed/dimensions from model-visible text entirely. Tradeoff: a generated image becomes hard to retrieve by *content* (its title is `anam_generated_00007_.png`, not "rainbow"), so topical recall would rely on `media_search`/`media_get`.
- **Option B (recall-preserving variant, recommended):** keep a short human-readable reference — `title`, `artifact_id`, and `prompt` (so "rainbow" still matches) — but **drop the forgeable identity fields**: `Stored path`, **`SHA256`**, exact byte size, and the block-style line layout. This kills the "authoritative record to reproduce" while keeping topical retrievability.
- **Either way, the load-bearing change is:** the exact crypto-identity (`SHA256`, full path, and arguably the raw UUID rendered as copyable text) must leave the *model-visible chunk text*. Those belong in chunk **metadata** (already stored separately) and behind `media_get`, not in retrievable prose.
- Note the interaction with `context.py:306`: it appends `{text}` verbatim, so slimming `_event_text` is the correct single locus; no context.py change is required for the minimal fix.

**Residual already noted:** existing contaminated chunks/history are erased by the go-live wipe; this fix prevents new replayable blocks from being indexed going forward. No editing of persisted messages is proposed (Invariant 4).

*Part A: verify + propose only. No code changed.*
