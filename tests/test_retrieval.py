from unittest.mock import patch

from tir.memory.retrieval import retrieve


def _conversation_chunk(chunk_id="conversation-mention"):
    return {
        "chunk_id": chunk_id,
        "text": "The user mentioned roadmap.md during upload discussion.",
        "metadata": {
            "source_type": "conversation",
            "source_trust": "firsthand",
            "conversation_id": "conv-old",
            "created_at": "2026-05-07T10:00:00+00:00",
        },
        "distance": 0.1,
    }


def _artifact_chunk(
    chunk_id="artifact-roadmap",
    *,
    filename="roadmap.md",
    title="Project Roadmap Notes",
    artifact_id="artifact-1234567890",
):
    return {
        "chunk_id": chunk_id,
        "text": (
            f"Artifact source: {title}\n"
            f"File: {filename}\n"
            "Origin: User upload\n"
            "Source role: Uploaded source\n"
            f"Artifact ID: {artifact_id}\n\n"
            "Roadmap artifact content."
        ),
        "metadata": {
            "source_type": "artifact_document",
            "source_trust": "thirdhand",
            "filename": filename,
            "title": title,
            "artifact_id": artifact_id,
            "origin": "user_upload",
            "source_role": "uploaded_source",
            "created_at": "2026-05-07T11:00:00+00:00",
        },
        "distance": 0.2,
    }


def test_artifact_intent_exact_filename_ranks_artifact_above_conversation_mention():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk(), _artifact_chunk()],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("Do you see roadmap.md?", max_results=2, artifact_intent=True)

    assert [result["chunk_id"] for result in results] == [
        "artifact-roadmap",
        "conversation-mention",
    ]
    assert results[0]["artifact_exact_match"] is True
    assert results[0]["artifact_match_field"] == "filename"
    assert results[0]["artifact_boost"] > 1.0


def test_artifact_intent_meaningful_title_ranks_artifact_first():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk(), _artifact_chunk()],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve(
            "Can you find Project Roadmap Notes?",
            max_results=2,
            artifact_intent=True,
        )

    assert results[0]["chunk_id"] == "artifact-roadmap"
    assert results[0]["artifact_match_field"] == "title"


def test_artifact_intent_artifact_id_ranks_artifact_first():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk(), _artifact_chunk()],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve(
            "Open artifact-1234567890",
            max_results=2,
            artifact_intent=True,
        )

    assert results[0]["chunk_id"] == "artifact-roadmap"
    assert results[0]["artifact_match_field"] == "artifact_id"


def test_artifact_intent_false_preserves_original_ordering():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk(), _artifact_chunk()],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("Do you see roadmap.md?", max_results=2)

    assert [result["chunk_id"] for result in results] == [
        "conversation-mention",
        "artifact-roadmap",
    ]
    assert "artifact_boost" not in results[0]


def test_bm25_only_artifact_can_be_boosted_from_text_header():
    bm25_artifact = {
        "chunk_id": "artifact-bm25",
        "text": (
            "Artifact source: Architecture Notes\n"
            "File: architecture.md\n"
            "Artifact ID: artifact-bm25-id\n"
            "Origin: User upload\n"
            "Source role: Uploaded source"
        ),
        "source_type": "artifact_document",
        "source_trust": "thirdhand",
        "created_at": "2026-05-07T11:00:00+00:00",
    }

    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk()],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[bm25_artifact]):
        results = retrieve("architecture.md", max_results=2, artifact_intent=True)

    assert results[0]["chunk_id"] == "artifact-bm25"
    assert results[0]["artifact_match_field"] == "filename"
    assert "source_material" not in results[0]["text"]
    assert "authority" not in results[0]["text"].lower()


def test_generic_one_word_title_does_not_get_strong_title_boost():
    artifact = _artifact_chunk(title="Notes", filename="unmatched.md")
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk(), artifact],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("Notes", max_results=2, artifact_intent=True)

    artifact_result = next(result for result in results if result["chunk_id"] == "artifact-roadmap")
    assert artifact_result["artifact_exact_match"] is False
    assert artifact_result["artifact_boost"] == 1.25
