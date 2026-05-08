from unittest.mock import patch

from tir.engine.context_budget import budget_retrieved_chunks
from tir.engine.context import build_system_prompt, build_system_prompt_with_debug


def test_operational_guidance_is_labeled_and_ordered():
    retrieved_chunks = [
        {
            "source_type": "conversation",
            "created_at": "2026-04-28T12:00:00+00:00",
            "text": "A remembered conversation chunk.",
        }
    ]

    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=retrieved_chunks,
        tool_descriptions="You have access to the following tools:\n- memory_search",
    )

    assert "You are an AI." in prompt
    assert "[Operational Guidance]" in prompt
    assert "Real-time source-of-truth tools must be used" in prompt
    assert "DESIGN_RATIONALE" not in prompt
    assert "You have access to the following tools:" in prompt
    assert "These are your own experiences and memories." in prompt
    assert "A remembered conversation chunk." in prompt
    assert "You are currently in conversation with Lyle." in prompt

    assert prompt.index("You are an AI.") < prompt.index("[Operational Guidance]")
    assert prompt.index("[Operational Guidance]") < prompt.index("You have access to the following tools:")
    assert prompt.index("You have access to the following tools:") < prompt.index("These are your own experiences and memories.")
    assert prompt.index("These are your own experiences and memories.") < prompt.index("You are currently in conversation with Lyle.")


def test_system_prompt_with_debug_preserves_existing_prompt_output():
    retrieved_chunks = [
        {
            "source_type": "conversation",
            "created_at": "2026-04-28T12:00:00+00:00",
            "text": "A remembered conversation chunk.",
        }
    ]
    kwargs = {
        "user_name": "Lyle",
        "retrieved_chunks": retrieved_chunks,
        "tool_descriptions": "You have access to the following tools:\n- memory_search",
    }

    prompt = build_system_prompt(**kwargs)
    debug_prompt, breakdown = build_system_prompt_with_debug(**kwargs)

    assert debug_prompt == prompt
    assert breakdown["system_prompt_chars"] == len(prompt)
    assert breakdown["best_effort"] is True


def test_system_prompt_breakdown_counts_sections():
    retrieved_chunks = [
        {
            "source_type": "conversation",
            "created_at": "2026-04-28T12:00:00+00:00",
            "text": "A remembered conversation chunk.",
        }
    ]

    prompt, breakdown = build_system_prompt_with_debug(
        user_name="Lyle",
        retrieved_chunks=retrieved_chunks,
        tool_descriptions="You have access to the following tools:\n- memory_search",
    )

    assert breakdown["system_prompt_chars"] == len(prompt)
    assert breakdown["soul_chars"] > 0
    assert breakdown["operational_guidance_chars"] > 0
    assert breakdown["tool_descriptions_chars"] > 0
    assert breakdown["retrieved_context_chars"] > 0
    assert breakdown["situation_chars"] > 0
    assert breakdown["other_chars"] >= 0


def test_retrieved_context_breakdown_changes_with_retrieved_chunks():
    _, empty_breakdown = build_system_prompt_with_debug(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )
    _, retrieved_breakdown = build_system_prompt_with_debug(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "source_type": "conversation",
                "created_at": "2026-04-28T12:00:00+00:00",
                "text": "A remembered conversation chunk.",
            }
        ],
        tool_descriptions=None,
    )

    assert empty_breakdown["retrieved_context_chars"] == 0
    assert retrieved_breakdown["retrieved_context_chars"] > 0


def test_missing_operational_guidance_is_omitted():
    missing_guidance = lambda: None

    with patch("tir.engine.context._load_operational_guidance", missing_guidance):
        prompt = build_system_prompt(
            user_name="Lyle",
            retrieved_chunks=[],
            tool_descriptions=None,
        )

    assert "[Operational Guidance]" not in prompt
    assert "You are an AI." in prompt
    assert "You are currently in conversation with Lyle." in prompt


def test_behavioral_guidance_file_is_not_loaded_into_prompt():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )

    assert "This file contains reviewed guidance proposed by the AI" not in prompt
    assert "BEHAVIORAL_GUIDANCE" not in prompt


def test_budget_retrieved_chunks_caps_total_context_chars():
    chunks = [
        {"chunk_id": "1", "text": "a" * 400, "metadata": {"source_type": "conversation"}},
        {"chunk_id": "2", "text": "b" * 400, "metadata": {"source_type": "conversation"}},
        {"chunk_id": "3", "text": "c" * 400, "metadata": {"source_type": "conversation"}},
    ]

    budgeted, metadata = budget_retrieved_chunks(
        chunks,
        max_chars=900,
        max_chunk_chars=1000,
    )

    assert [chunk["chunk_id"] for chunk in budgeted] == ["1", "2"]
    assert metadata == {
        "input_chunks": 3,
        "included_chunks": 2,
        "skipped_chunks": 1,
        "truncated_chunks": 0,
        "max_chars": 900,
        "used_chars": 800,
    }


def test_budget_retrieved_chunks_truncates_oversized_chunks_with_marker():
    chunks = [
        {"chunk_id": "large", "text": "x" * 1000, "metadata": {"keep": "metadata"}},
    ]

    budgeted, metadata = budget_retrieved_chunks(
        chunks,
        max_chars=800,
        max_chunk_chars=300,
    )

    assert len(budgeted) == 1
    assert len(budgeted[0]["text"]) <= 300
    assert "[retrieved chunk truncated]" in budgeted[0]["text"]
    assert budgeted[0]["metadata"] == {"keep": "metadata"}
    assert metadata["truncated_chunks"] == 1
    assert metadata["used_chars"] == len(budgeted[0]["text"])


def test_budget_retrieved_chunks_uses_remaining_budget_when_useful():
    chunks = [
        {"chunk_id": "first", "text": "a" * 400, "metadata": {}},
        {"chunk_id": "second", "text": "b" * 1000, "metadata": {}},
    ]

    budgeted, metadata = budget_retrieved_chunks(
        chunks,
        max_chars=950,
        max_chunk_chars=1000,
    )

    assert [chunk["chunk_id"] for chunk in budgeted] == ["first", "second"]
    assert len(budgeted[1]["text"]) <= 550
    assert "[retrieved chunk truncated]" in budgeted[1]["text"]
    assert metadata["truncated_chunks"] == 1
    assert metadata["used_chars"] <= 950
