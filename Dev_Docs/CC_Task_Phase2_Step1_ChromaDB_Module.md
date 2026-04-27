# CC Task: Phase 2 Step 1 — ChromaDB Module

## What this is

A new module `tir/memory/chroma.py` that handles all ChromaDB operations: embedding text via Ollama, storing chunks as vectors, and querying by vector similarity. This is the foundation for Phase 2 memory — nothing else in Phase 2 works without it.

## Prerequisites

- Database layer deployed and verified (Phase 1 Step 1)
- Conversation engine deployed and verified (Phase 1 Step 2)
- `chromadb` and `requests` installed (should be from requirements.txt)
- nomic-embed-text model available in Ollama: `ollama pull nomic-embed-text`

## File to create

```
tir/
    memory/
        chroma.py    ← NEW
```

## Exact code for `tir/memory/chroma.py`

```python
"""
Tír ChromaDB Layer

Handles vector storage and retrieval via ChromaDB + Ollama embeddings.
This is what makes the entity's memories searchable by meaning.

Three responsibilities:
- Embed text via Ollama's nomic-embed-text
- Store chunks with embeddings and metadata in ChromaDB
- Query chunks by vector similarity

The entity never calls this directly. The chunking pipeline writes here,
the retrieval pipeline reads here.
"""

import logging
import requests
import chromadb

from tir.config import CHROMA_DIR, EMBED_MODEL, OLLAMA_HOST

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client and collection
# ---------------------------------------------------------------------------

_client = None
_collection = None


def _get_collection(chroma_path: str = CHROMA_DIR) -> chromadb.Collection:
    """Get or create the tir_memory collection. Cached after first call."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=chroma_path)
        _collection = _client.get_or_create_collection(
            name="tir_memory",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection 'tir_memory' ready, {_collection.count()} chunks"
        )
    return _collection


def reset_client():
    """Reset the cached client. Used in tests and after path changes."""
    global _client, _collection
    _client = None
    _collection = None


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_text(
    text: str,
    model: str = EMBED_MODEL,
    ollama_host: str = OLLAMA_HOST,
) -> list[float]:
    """
    Embed a single text string via Ollama.

    Args:
        text: The text to embed.
        model: Embedding model name (default: nomic-embed-text).
        ollama_host: Ollama server URL.

    Returns:
        A list of floats (768 dimensions for nomic-embed-text).

    Raises:
        requests.RequestException: Ollama unreachable or error.
        ValueError: Empty text or malformed response.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    resp = requests.post(
        f"{ollama_host}/api/embed",
        json={"model": model, "input": text},
        timeout=30,
    )
    resp.raise_for_status()

    data = resp.json()

    if "embeddings" not in data or not data["embeddings"]:
        raise ValueError(f"Malformed embedding response: {list(data.keys())}")

    embedding = data["embeddings"][0]

    if not isinstance(embedding, list) or len(embedding) == 0:
        raise ValueError(f"Empty embedding returned for text of length {len(text)}")

    return embedding


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def upsert_chunk(
    chunk_id: str,
    text: str,
    metadata: dict,
    embedding: list[float] | None = None,
    chroma_path: str = CHROMA_DIR,
    ollama_host: str = OLLAMA_HOST,
):
    """
    Store or update a chunk in ChromaDB.

    If no embedding is provided, one is generated via Ollama.
    Upsert semantics: if chunk_id exists, it gets overwritten.

    Args:
        chunk_id: Unique identifier (e.g., "{conversation_id}_chunk_0").
        text: The chunk text to store and embed.
        metadata: Dict of metadata (conversation_id, source_type, etc.).
            All values must be str, int, float, or bool — no None values.
        embedding: Pre-computed embedding, or None to compute here.
        chroma_path: Path to ChromaDB persistent store.
        ollama_host: Ollama server URL.
    """
    collection = _get_collection(chroma_path)

    if embedding is None:
        embedding = embed_text(text, ollama_host=ollama_host)

    collection.upsert(
        ids=[chunk_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
    )
    logger.debug(f"Upserted chunk {chunk_id} ({len(text)} chars)")


def delete_chunks_by_prefix(
    prefix: str,
    chroma_path: str = CHROMA_DIR,
):
    """
    Delete all chunks whose ID starts with prefix.

    Used for re-chunking: delete all chunks for a conversation
    before re-creating them. Not used in normal operation
    (upsert handles overwrites), but available for cleanup.

    Args:
        prefix: ID prefix to match (e.g., a conversation_id).
        chroma_path: Path to ChromaDB persistent store.
    """
    collection = _get_collection(chroma_path)

    # ChromaDB doesn't support prefix queries on IDs directly.
    # Get all IDs and filter.
    all_ids = collection.get(include=[])["ids"]
    matching = [cid for cid in all_ids if cid.startswith(prefix)]

    if matching:
        collection.delete(ids=matching)
        logger.info(f"Deleted {len(matching)} chunks with prefix '{prefix[:12]}...'")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query_similar(
    query_text: str,
    n_results: int = 30,
    chroma_path: str = CHROMA_DIR,
    ollama_host: str = OLLAMA_HOST,
) -> list[dict]:
    """
    Find chunks similar to the query text.

    Embeds the query, then searches ChromaDB by cosine similarity.

    Args:
        query_text: Natural language query.
        n_results: Max results to return.
        chroma_path: Path to ChromaDB persistent store.
        ollama_host: Ollama server URL.

    Returns:
        List of dicts, each with:
            chunk_id: str
            text: str
            metadata: dict
            distance: float (cosine distance, lower = more similar)
        Ordered by distance ascending (most similar first).
        Empty list if collection is empty or query matches nothing.
    """
    collection = _get_collection(chroma_path)

    # Handle empty collection
    if collection.count() == 0:
        return []

    # Don't request more results than exist
    actual_n = min(n_results, collection.count())

    query_embedding = embed_text(query_text, ollama_host=ollama_host)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=actual_n,
        include=["documents", "metadatas", "distances"],
    )

    # Unpack ChromaDB's nested list format
    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "chunk_id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    return chunks


def get_collection_count(chroma_path: str = CHROMA_DIR) -> int:
    """Return the number of chunks in the collection."""
    collection = _get_collection(chroma_path)
    return collection.count()
```

## Verify — check nomic-embed-text is available

```bash
ollama show nomic-embed-text
```

If not found:
```bash
ollama pull nomic-embed-text
```

## Verify — test embedding works

```bash
cd /path/to/Tir
python3 -c "
from tir.memory.chroma import embed_text
e = embed_text('Hello world')
print(f'Embedding dimensions: {len(e)}')
print(f'First 5 values: {e[:5]}')
"
```

Expected: `Embedding dimensions: 768` and five float values.

## Verify — test upsert and query

```bash
cd /path/to/Tir
python3 -c "
from tir.memory.chroma import upsert_chunk, query_similar, get_collection_count, reset_client
import tempfile, os

# Use a temp directory so we don't pollute prod
tmpdir = tempfile.mkdtemp()
chroma_path = os.path.join(tmpdir, 'test_chroma')

reset_client()

# Store two chunks
upsert_chunk(
    chunk_id='test_chunk_0',
    text='We talked about building a memory system for an AI entity.',
    metadata={'source_type': 'conversation', 'source_trust': 'firsthand', 'conversation_id': 'conv1', 'user_id': 'user1', 'chunk_index': 0, 'message_count': 10, 'created_at': '2026-04-22T12:00:00Z'},
    chroma_path=chroma_path,
)

upsert_chunk(
    chunk_id='test_chunk_1',
    text='The weather was sunny and we went to the park for a picnic.',
    metadata={'source_type': 'conversation', 'source_trust': 'firsthand', 'conversation_id': 'conv2', 'user_id': 'user1', 'chunk_index': 0, 'message_count': 8, 'created_at': '2026-04-22T13:00:00Z'},
    chroma_path=chroma_path,
)

print(f'Chunk count: {get_collection_count(chroma_path)}')

# Query — should rank memory system chunk higher
results = query_similar('AI memory architecture', n_results=5, chroma_path=chroma_path)
for r in results:
    print(f'  {r[\"chunk_id\"]}: distance={r[\"distance\"]:.4f}  text={r[\"text\"][:60]}')

# Cleanup
import shutil
shutil.rmtree(tmpdir)
reset_client()
print('PASS')
"
```

Expected:
- Chunk count: 2
- `test_chunk_0` (memory system) ranks higher (lower distance) than `test_chunk_1` (picnic)
- Prints PASS

## Verify — empty collection query doesn't crash

```bash
cd /path/to/Tir
python3 -c "
from tir.memory.chroma import query_similar, reset_client
import tempfile, os

tmpdir = tempfile.mkdtemp()
chroma_path = os.path.join(tmpdir, 'empty_chroma')
reset_client()

results = query_similar('anything', n_results=5, chroma_path=chroma_path)
print(f'Results from empty collection: {results}')
assert results == [], f'Expected empty list, got {results}'

import shutil
shutil.rmtree(tmpdir)
reset_client()
print('PASS')
"
```

## What NOT to do

- Do NOT modify `db.py`, `config.py`, `conversation.py`, `context.py`, or `ollama.py`
- Do NOT create the ChromaDB data directory manually — `PersistentClient` creates it
- Do NOT add any retrieval logic here — that's a separate module (Step 3)
- Do NOT add any chunking logic here — that's a separate module (Step 2)
- Do NOT use the older `/api/embeddings` endpoint — use `/api/embed`
- Do NOT store None values in ChromaDB metadata — ChromaDB rejects them

## What comes next

After verifying this module works:
- Step 2: Chunking pipeline (uses this module to store chunks)
- Step 3: Retrieval pipeline (uses this module to query chunks)
