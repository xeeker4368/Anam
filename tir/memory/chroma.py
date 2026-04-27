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
