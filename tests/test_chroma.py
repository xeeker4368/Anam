import pytest

from tir.memory import chroma


def _embedding(dim: int = 768) -> list[float]:
    return [0.0] * dim


class RecordingCollection:
    def __init__(self):
        self.upsert_calls = []

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)


def test_valid_embedding_dimension_passes_and_writes(monkeypatch):
    collection = RecordingCollection()
    monkeypatch.setattr(
        chroma,
        "_get_collection",
        lambda chroma_path=chroma.CHROMA_DIR: collection,
    )

    chroma.upsert_chunk(
        chunk_id="chunk-valid",
        text="valid text",
        metadata={"source_type": "test"},
        embedding=_embedding(),
    )

    assert len(collection.upsert_calls) == 1
    assert collection.upsert_calls[0]["ids"] == ["chunk-valid"]
    assert collection.upsert_calls[0]["embeddings"] == [_embedding()]


def test_wrong_embedding_dimension_raises_before_write(monkeypatch):
    collection = RecordingCollection()
    monkeypatch.setattr(
        chroma,
        "_get_collection",
        lambda chroma_path=chroma.CHROMA_DIR: collection,
    )

    with pytest.raises(chroma.EmbeddingDimensionError) as excinfo:
        chroma.upsert_chunk(
            chunk_id="chunk-wrong",
            text="wrong text",
            metadata={"source_type": "test"},
            embedding=_embedding(1024),
        )

    assert "Embedding dimension mismatch: expected 768, got 1024" in str(excinfo.value)
    assert "nomic-embed-text" in str(excinfo.value)
    assert collection.upsert_calls == []


def test_generated_embedding_dimension_is_checked_before_write(monkeypatch):
    collection = RecordingCollection()
    monkeypatch.setattr(
        chroma,
        "_get_collection",
        lambda chroma_path=chroma.CHROMA_DIR: collection,
    )
    monkeypatch.setattr(
        chroma,
        "embed_text",
        lambda text, ollama_host=chroma.OLLAMA_HOST: _embedding(3),
    )

    with pytest.raises(chroma.EmbeddingDimensionError) as excinfo:
        chroma.upsert_chunk(
            chunk_id="chunk-generated-wrong",
            text="generated wrong text",
            metadata={"source_type": "test"},
        )

    assert "expected 768, got 3" in str(excinfo.value)
    assert collection.upsert_calls == []
