from unittest.mock import patch

from tir.engine.context_debug import build_context_debug
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


def _research_chunk(chunk_id="research-note", *, distance=0.1):
    return {
        "chunk_id": chunk_id,
        "text": "Manual research note: Source Trust Audit\n\nRetrieval trust audit findings.",
        "metadata": {
            "source_type": "research",
            "source_trust": "thirdhand",
            "artifact_id": "research-artifact-1",
            "title": "Research Note - Source Trust Audit",
            "path": "research/2026-05-22-source-trust-audit.md",
            "created_at": "2026-05-22T10:00:00+00:00",
        },
        "distance": distance,
    }


def test_source_trust_is_metadata_only_not_ranking_multiplier():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_conversation_chunk("firsthand"), _artifact_chunk("thirdhand")],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("source trust", max_results=2)

    assert [result["chunk_id"] for result in results] == ["firsthand", "thirdhand"]
    assert results[0]["metadata"]["source_trust"] == "firsthand"
    assert results[1]["metadata"]["source_trust"] == "thirdhand"
    assert results[0]["adjusted_score"] == results[0]["rrf_score"]
    assert results[1]["adjusted_score"] == results[1]["rrf_score"]
    assert results[1]["adjusted_score"] == 1.0 / 62


def test_research_note_chunks_are_not_downweighted_by_source_trust():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_research_chunk(), _conversation_chunk()],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("retrieval trust audit", max_results=2)

    assert results[0]["chunk_id"] == "research-note"
    assert results[0]["metadata"]["source_type"] == "research"
    assert results[0]["metadata"]["source_trust"] == "thirdhand"
    assert results[0]["adjusted_score"] == results[0]["rrf_score"]
    assert results[0]["adjusted_score"] == 1.0 / 61


def test_source_trust_remains_visible_in_context_debug_metadata():
    retrieved_chunks = [_research_chunk()]

    debug = build_context_debug(
        prompt_breakdown={"system_prompt_chars": 100},
        retrieval_skipped=False,
        retrieval_policy={"mode": "normal"},
        query="retrieval trust audit",
        retrieved_chunks=retrieved_chunks,
        retrieval_budget={"max_chars": 1000, "used_chars": 100},
    )

    included = debug["retrieval"]["included_chunks"][0]
    assert included["metadata"]["source_trust"] == "thirdhand"
    assert included["source_type"] == "research"


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


def _slimmed_artifact_chunk():
    """An artifact chunk with the NEW slimmed event text (no 'Artifact ID:' /
    'File:' header lines) but full metadata — mirrors what the slimmed
    _event_text produces alongside base_metadata."""
    return {
        "chunk_id": "artifact-roadmap",
        "text": "Artifact: Project Roadmap Notes (id: artifact-1234567890)\nDescription: the roadmap.",
        "metadata": {
            "source_type": "artifact_document",
            "source_trust": "thirdhand",
            "filename": "roadmap.md",
            "title": "Project Roadmap Notes",
            "artifact_id": "artifact-1234567890",
            "origin": "user_upload",
            "source_role": "uploaded_source",
            "created_at": "2026-05-07T11:00:00+00:00",
        },
        "distance": 0.2,
    }


def test_artifact_match_uses_metadata_not_slimmed_text():
    # Consumer-safety for the _event_text slim: _artifact_match reads
    # metadata[artifact_id/filename/title] FIRST; the header-text fallback is only
    # a legacy path. With slimmed text (no 'Artifact ID:'/'File:' lines) exact
    # matching must still work via metadata for id, filename, and title.
    for query, expected_field in [
        ("Open artifact-1234567890", "artifact_id"),
        ("Do you see roadmap.md?", "filename"),
        ("Can you find Project Roadmap Notes?", "title"),
    ]:
        with patch(
            "tir.memory.retrieval.query_similar",
            return_value=[_conversation_chunk(), _slimmed_artifact_chunk()],
        ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
            results = retrieve(query, max_results=2, artifact_intent=True)
        assert results[0]["chunk_id"] == "artifact-roadmap", query
        assert results[0]["artifact_exact_match"] is True, query
        assert results[0]["artifact_match_field"] == expected_field, query


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


# ---------------------------------------------------------------------------
# Relevance floor (PLAN-2026-08-16-relevance-floor.md)
# ---------------------------------------------------------------------------

def _vector_chunk(chunk_id, distance):
    return {
        "chunk_id": chunk_id,
        "text": f"text for {chunk_id}",
        "metadata": {
            "source_type": "conversation",
            "source_trust": "firsthand",
            "created_at": "2026-05-07T10:00:00+00:00",
        },
        "distance": distance,
    }


def _bm25_chunk(chunk_id, score):
    return {
        "chunk_id": chunk_id,
        "text": f"lexical text for {chunk_id}",
        "source_type": "conversation",
        "source_trust": "firsthand",
        "created_at": "2026-05-07T10:00:00+00:00",
        "bm25_score": score,
    }


def test_vector_candidates_above_the_distance_floor_are_dropped():
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_vector_chunk("near", 0.30), _vector_chunk("far", 0.55)],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("some query about things", max_results=5)

    assert [r["chunk_id"] for r in results] == ["near"]


def test_retrieve_returns_empty_when_nothing_clears_either_floor():
    """A valid outcome, and the one the zero-result marker exists to describe."""
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_vector_chunk("far", 0.61)],
    ), patch("tir.memory.retrieval.search_bm25", return_value=[]):
        results = retrieve("nothing relevant here at all", max_results=5)

    assert results == []


def test_bm25_only_chunk_is_exempt_from_the_distance_floor():
    """An exact lexical match is evidence independent of semantic distance."""
    with patch(
        "tir.memory.retrieval.query_similar",
        return_value=[_vector_chunk("far", 0.75)],
    ), patch(
        "tir.memory.retrieval.search_bm25",
        return_value=[_bm25_chunk("lexical-hit", -30.0)],
    ), patch("tir.memory.retrieval._bm25_floor_applies", return_value=True):
        results = retrieve("distinctive phrase", max_results=5)

    assert [r["chunk_id"] for r in results] == ["lexical-hit"]
    assert results[0]["vector_distance"] is None
    assert results[0]["vector_rank"] is None


def test_weak_lexical_candidates_are_dropped_by_the_per_term_floor():
    # Two query terms survive sanitization, so the floor is score/2 <= -2.5.
    with patch(
        "tir.memory.retrieval.query_similar", return_value=[]
    ), patch(
        "tir.memory.retrieval.search_bm25",
        return_value=[_bm25_chunk("strong", -12.0), _bm25_chunk("weak", -2.0)],
    ), patch("tir.memory.retrieval._bm25_floor_applies", return_value=True):
        results = retrieve("distinctive phrase", max_results=5)

    assert [r["chunk_id"] for r in results] == ["strong"]


def test_per_term_floor_does_not_penalise_a_single_term_query():
    """An absolute floor killed exact-filename recall; per-term must not."""
    with patch(
        "tir.memory.retrieval.query_similar", return_value=[]
    ), patch(
        "tir.memory.retrieval.search_bm25",
        return_value=[_bm25_chunk("filename-hit", -7.8)],
    ), patch("tir.memory.retrieval._bm25_floor_applies", return_value=True):
        results = retrieve("anam_generated_00013_.png", max_results=5)

    assert [r["chunk_id"] for r in results] == ["filename-hit"]


def test_lexical_floor_is_skipped_on_a_small_corpus():
    """BM25 is IDF-driven; in a near-empty index even a perfect match scores ~0."""
    with patch(
        "tir.memory.retrieval.query_similar", return_value=[]
    ), patch(
        "tir.memory.retrieval.search_bm25",
        return_value=[_bm25_chunk("new-store-hit", -0.000001)],
    ), patch("tir.memory.retrieval._bm25_floor_applies", return_value=False):
        results = retrieve("uniquemarkerword", max_results=5)

    assert [r["chunk_id"] for r in results] == ["new-store-hit"]


def test_lexical_candidate_without_a_score_fails_open():
    with patch(
        "tir.memory.retrieval.query_similar", return_value=[]
    ), patch(
        "tir.memory.retrieval.search_bm25",
        return_value=[{"chunk_id": "unscored", "text": "t", "source_type": "conversation"}],
    ), patch("tir.memory.retrieval._bm25_floor_applies", return_value=True):
        results = retrieve("distinctive phrase", max_results=5)

    assert [r["chunk_id"] for r in results] == ["unscored"]


def test_stopwords_are_dropped_from_the_fts_query():
    from tir.memory.retrieval import _sanitize_fts5_query

    assert _sanitize_fts5_query("what did we decide about the roof repair?") == (
        '"decide" OR "roof" OR "repair?"'
    )


def test_content_words_survive_even_when_a_phrase_contains_stopwords():
    from tir.memory.retrieval import _sanitize_fts5_query

    sanitized = _sanitize_fts5_query("The Architecture of Thought")
    assert '"Architecture"' in sanitized
    assert '"Thought"' in sanitized
    assert '"of"' not in sanitized


def test_all_stopword_query_yields_no_fts_query_and_skips_the_bm25_leg():
    from tir.memory.retrieval import _sanitize_fts5_query

    assert _sanitize_fts5_query("a of the") == ""

    with patch(
        "tir.memory.retrieval.query_similar", return_value=[_vector_chunk("v", 0.2)]
    ), patch("tir.memory.retrieval.search_bm25") as mock_bm25:
        results = retrieve("a of the", max_results=5)

    mock_bm25.assert_not_called()
    assert [r["chunk_id"] for r in results] == ["v"]
