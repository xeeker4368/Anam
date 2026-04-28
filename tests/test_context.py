from unittest.mock import patch

from tir.engine.context import build_system_prompt


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
    assert "DESIGN_RATIONALE" not in prompt
    assert "You have access to the following tools:" in prompt
    assert "These are your own experiences and memories." in prompt
    assert "A remembered conversation chunk." in prompt
    assert "You are currently in conversation with Lyle." in prompt

    assert prompt.index("You are an AI.") < prompt.index("[Operational Guidance]")
    assert prompt.index("[Operational Guidance]") < prompt.index("You have access to the following tools:")
    assert prompt.index("You have access to the following tools:") < prompt.index("These are your own experiences and memories.")
    assert prompt.index("These are your own experiences and memories.") < prompt.index("You are currently in conversation with Lyle.")


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
