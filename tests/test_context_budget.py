from tir.engine.context_budget import budget_retrieved_chunks


def test_budget_retrieved_chunks_skips_missing_text():
    budgeted, metadata = budget_retrieved_chunks([{"chunk_id": "missing"}])

    assert budgeted == []
    assert metadata["input_chunks"] == 1
    assert metadata["included_chunks"] == 0
    assert metadata["skipped_chunks"] == 1
    assert metadata["skipped_empty_chunks"] == 1
    assert metadata["skipped_budget_chunks"] == 0
    assert metadata["used_chars"] == 0


def test_budget_retrieved_chunks_skips_none_text():
    budgeted, metadata = budget_retrieved_chunks([
        {"chunk_id": "none", "text": None},
    ])

    assert budgeted == []
    assert metadata["skipped_chunks"] == 1
    assert metadata["skipped_empty_chunks"] == 1
    assert metadata["skipped_budget_chunks"] == 0


def test_budget_retrieved_chunks_skips_empty_text():
    budgeted, metadata = budget_retrieved_chunks([
        {"chunk_id": "empty", "text": ""},
    ])

    assert budgeted == []
    assert metadata["skipped_chunks"] == 1
    assert metadata["skipped_empty_chunks"] == 1
    assert metadata["skipped_budget_chunks"] == 0


def test_budget_retrieved_chunks_skips_whitespace_only_text():
    budgeted, metadata = budget_retrieved_chunks([
        {"chunk_id": "space", "text": "   \n\t  "},
    ])

    assert budgeted == []
    assert metadata["skipped_chunks"] == 1
    assert metadata["skipped_empty_chunks"] == 1
    assert metadata["skipped_budget_chunks"] == 0


def test_budget_retrieved_chunks_skips_non_string_text():
    budgeted, metadata = budget_retrieved_chunks([
        {"chunk_id": "number", "text": 42},
    ])

    assert budgeted == []
    assert metadata["skipped_chunks"] == 1
    assert metadata["skipped_empty_chunks"] == 1
    assert metadata["skipped_budget_chunks"] == 0


def test_budget_retrieved_chunks_truncates_oversized_chunk_with_marker():
    budgeted, metadata = budget_retrieved_chunks(
        [{"chunk_id": "large", "text": "x" * 1000, "metadata": {"source": "test"}}],
        max_chars=800,
        max_chunk_chars=300,
    )

    assert len(budgeted) == 1
    assert budgeted[0]["chunk_id"] == "large"
    assert budgeted[0]["metadata"] == {"source": "test"}
    assert len(budgeted[0]["text"]) <= 300
    assert "[retrieved chunk truncated]" in budgeted[0]["text"]
    assert metadata["included_chunks"] == 1
    assert metadata["skipped_chunks"] == 0
    assert metadata["truncated_chunks"] == 1
    assert metadata["used_chars"] == len(budgeted[0]["text"])


def test_budget_retrieved_chunks_skips_chunk_that_cannot_fit():
    chunks = [
        {"chunk_id": "first", "text": "a" * 450},
        {"chunk_id": "second", "text": "b" * 600},
    ]

    budgeted, metadata = budget_retrieved_chunks(
        chunks,
        max_chars=900,
        max_chunk_chars=1000,
    )

    assert [chunk["chunk_id"] for chunk in budgeted] == ["first"]
    assert metadata["input_chunks"] == 2
    assert metadata["included_chunks"] == 1
    assert metadata["skipped_chunks"] == 1
    assert metadata["skipped_empty_chunks"] == 0
    assert metadata["skipped_budget_chunks"] == 1
    assert metadata["used_chars"] == 450


def test_budget_retrieved_chunks_metadata_counts_remain_coherent():
    chunks = [
        {"chunk_id": "missing"},
        {"chunk_id": "included", "text": "hello"},
        {"chunk_id": "empty", "text": ""},
        {"chunk_id": "large", "text": "x" * 1000},
    ]

    budgeted, metadata = budget_retrieved_chunks(
        chunks,
        max_chars=700,
        max_chunk_chars=300,
    )

    assert [chunk["chunk_id"] for chunk in budgeted] == ["included", "large"]
    assert metadata["input_chunks"] == 4
    assert metadata["included_chunks"] == 2
    assert metadata["skipped_chunks"] == 2
    assert metadata["skipped_empty_chunks"] == 2
    assert metadata["skipped_budget_chunks"] == 0
    assert metadata["truncated_chunks"] == 1
    assert metadata["used_chars"] == sum(len(chunk["text"]) for chunk in budgeted)
