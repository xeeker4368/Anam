from pathlib import Path
from unittest.mock import patch

import pytest

from tir.engine.context_budget import budget_retrieved_chunks
from tir.engine.context import build_system_prompt, build_system_prompt_with_debug
from tir.engine.context_debug import build_context_debug


def test_root_behavioral_guidance_file_is_dormant_placeholder():
    content = Path("BEHAVIORAL_GUIDANCE.md").read_text(encoding="utf-8")

    assert "Status: dormant before go-live." in content
    assert "not loaded into runtime context" in content
    assert not any(
        line.strip().startswith("- Guidance:")
        for line in content.splitlines()
    )


@pytest.fixture()
def context_project(tmp_path, monkeypatch):
    soul = tmp_path / "soul.md"
    operational = tmp_path / "OPERATIONAL_GUIDANCE.md"
    behavioral = tmp_path / "BEHAVIORAL_GUIDANCE.md"
    soul.write_text("You are an AI.\n", encoding="utf-8")
    operational.write_text("Runtime operator guidance.\n", encoding="utf-8")
    monkeypatch.setattr("tir.engine.context.PROJECT_ROOT", tmp_path)
    return {
        "root": tmp_path,
        "soul": soul,
        "operational": operational,
        "behavioral": behavioral,
    }


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
    assert "[Current Situation]" in prompt
    assert "Conversation with: Lyle" in prompt

    assert prompt.index("You are an AI.") < prompt.index("[Operational Guidance]")
    assert prompt.index("[Operational Guidance]") < prompt.index("You have access to the following tools:")
    assert prompt.index("You have access to the following tools:") < prompt.index("These are your own experiences and memories.")
    assert prompt.index("These are your own experiences and memories.") < prompt.index("[Current Situation]")


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


def test_journal_memory_context_uses_journal_date_metadata():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "source_type": "journal",
                "created_at": "2026-05-09T01:00:00+00:00",
                "text": "Journal reflection text.",
                "metadata": {
                    "journal_date": "2026-05-08",
                    "source_type": "journal",
                },
            }
        ],
    )

    assert "[Your reflection journal entry from 2026-05-08 — personal reflection]" in prompt
    assert "Journal reflection text." in prompt


def test_project_reference_artifact_context_is_labeled_as_source_material():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "source_type": "artifact_document",
                "text": "Roadmap text.",
                "metadata": {
                    "title": "Roadmap",
                    "filename": "ROADMAP.md",
                    "source_type": "artifact_document",
                    "source_role": "project_reference",
                },
            }
        ],
    )

    assert (
        "[Project reference document: ROADMAP.md — source material, not runtime guidance]"
    ) in prompt
    assert "Roadmap text." in prompt


def test_research_memory_context_uses_working_research_label():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "source_type": "research",
                "created_at": "2026-05-10T12:00:00+00:00",
                "text": "Research note text.",
                "metadata": {
                    "research_date": "2026-05-10",
                    "research_title": "Manual Research Cycle",
                    "source_type": "research",
                    "source_role": "research_reference",
                    "origin": "manual_research",
                    "provisional": True,
                },
            }
        ],
    )

    assert (
        "[Research you wrote on 2026-05-10: Manual Research Cycle — working research notes]"
    ) in prompt
    assert "Research note text." in prompt
    assert "[Conversation —" not in prompt
    assert "[Project reference document:" not in prompt


def test_research_reference_role_takes_precedence_over_project_reference_label():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "source_type": "artifact_document",
                "text": "Registered research note text.",
                "metadata": {
                    "filename": "2026-05-10-local-models.md",
                    "research_date": "2026-05-10",
                    "research_title": "Local Models",
                    "source_type": "artifact_document",
                    "source_role": "research_reference",
                    "origin": "manual_research",
                    "provisional": True,
                },
            }
        ],
    )

    assert "[Research you wrote on 2026-05-10: Local Models — working research notes]" in prompt
    assert "[Project reference document:" not in prompt
    assert "[Artifact source:" not in prompt


def test_research_memory_context_falls_back_when_metadata_is_missing():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "source_type": "research",
                "created_at": "2026-05-10T12:00:00+00:00",
                "text": "Research note text.",
                "metadata": {},
            }
        ],
    )

    assert (
        "[Research you wrote on 2026-05-10T12:00:00+00:00 — working research notes]"
    ) in prompt
    assert "Research note text." in prompt


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


def test_context_debug_maps_prompt_sections_and_retrieval_sources():
    prompt_breakdown = {
        "total_chars": 1000,
        "soul_chars": 10,
        "operational_guidance_chars": 20,
        "behavioral_guidance_chars": 30,
        "tool_descriptions_chars": 40,
        "retrieved_context_chars": 50,
        "conversation_history_chars": 60,
        "artifact_context_chars": 70,
        "selection_context_chars": 80,
        "situation_chars": 90,
        "other_chars": 5,
    }
    retrieved_chunks = [
        {
            "chunk_id": "journal_2026_05_08_chunk_0",
            "text": "Reflection journal text",
            "metadata": {
                "source_type": "journal",
                "artifact_id": "artifact-1",
                "journal_date": "2026-05-08",
                "title": "Reflection Journal — 2026-05-08",
                "chunk_index": 0,
                "chunk_kind": "journal_content",
            },
            "vector_rank": 1,
            "adjusted_score": 0.75,
        },
        {
            "chunk_id": "conversation-1",
            "text": "Conversation text",
            "source_type": "conversation",
        },
    ]

    debug = build_context_debug(
        prompt_breakdown=prompt_breakdown,
        retrieval_skipped=False,
        retrieval_policy={"mode": "normal"},
        query="what happened yesterday?",
        retrieved_chunks=retrieved_chunks,
        retrieval_budget={
            "input_chunks": 3,
            "included_chunks": 2,
            "skipped_chunks": 1,
            "skipped_empty_chunks": 0,
            "skipped_budget_chunks": 1,
            "truncated_chunks": 0,
            "max_chars": 14000,
            "used_chars": 100,
        },
    )

    assert debug["prompt_total_chars"] == 1000
    assert debug["prompt_section_chars"]["soul"] == 10
    assert debug["prompt_section_chars"]["retrieved_memories"] == 50
    assert debug["prompt_section_chars"]["current_situation"] == 90
    assert debug["retrieval"]["sources_by_type"] == {
        "conversation": 1,
        "journal": 1,
    }
    journal = debug["retrieval"]["included_chunks"][0]
    assert journal["source_type"] == "journal"
    assert journal["metadata"]["journal_date"] == "2026-05-08"
    assert journal["metadata"]["artifact_id"] == "artifact-1"
    assert journal["metadata"]["chunk_index"] == 0
    assert journal["journal"]["journal_date"] == "2026-05-08"
    assert journal["journal"]["full_journal_included"] is None
    assert debug["context_budget"]["remaining_chars"] == 13900
    assert debug["context_budget"]["skipped_budget_chunks"] == 1


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
    assert "[Current Situation]" in prompt
    assert "Conversation with: Lyle" in prompt


def test_behavioral_guidance_file_is_not_loaded_when_no_active_section(context_project):
    context_project["behavioral"].write_text(
        "# BEHAVIORAL_GUIDANCE.md\n\nThis file contains reviewed guidance proposed by the AI.\n",
        encoding="utf-8",
    )

    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )

    assert "This file contains reviewed guidance proposed by the AI" not in prompt
    assert "BEHAVIORAL_GUIDANCE" not in prompt


def test_active_behavioral_guidance_section_is_dormant(context_project):
    context_project["behavioral"].write_text(
        """# BEHAVIORAL_GUIDANCE.md

This file contains reviewed guidance proposed by the AI and approved by an admin.

## Active Guidance

### Proposal abc

- Proposal ID: abc
- Type: addition
- Applied: 2026-05-08T12:00:00+00:00
- Source: conversation conv-1, message msg-1
- Guidance: Keep behavioral guidance narrow and evidence-linked.
- Rationale: This rationale should not load.
""",
        encoding="utf-8",
    )

    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions="You have access to the following tools:\n- memory_search",
    )

    assert "[Reviewed Behavioral Guidance]" not in prompt
    assert "Keep behavioral guidance narrow and evidence-linked." not in prompt
    assert "This file contains reviewed guidance proposed by the AI" not in prompt
    assert "Proposal ID" not in prompt
    assert "Applied:" not in prompt
    assert "Source: conversation" not in prompt
    assert "This rationale should not load" not in prompt
    assert prompt.index("[Operational Guidance]") < prompt.index("You have access to the following tools:")


def test_missing_behavioral_guidance_file_is_omitted(context_project):
    context_project["behavioral"].unlink(missing_ok=True)

    prompt, breakdown = build_system_prompt_with_debug(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )

    assert "[Reviewed Behavioral Guidance]" not in prompt
    assert breakdown["behavioral_guidance_runtime_enabled"] is False
    assert breakdown["behavioral_guidance_status"] == "dormant_before_go_live"
    assert breakdown["behavioral_guidance_chars"] == 0
    assert breakdown["behavioral_guidance_items_found"] == 0


def test_behavioral_guidance_dormant_ignores_budget_and_active_items(context_project):
    items = "\n".join(
        [
            "- Guidance: First compact guidance.",
            "- Guidance: " + ("Second long guidance " * 80),
            "- Guidance: Third compact guidance.",
        ]
    )
    context_project["behavioral"].write_text(
        f"# BEHAVIORAL_GUIDANCE.md\n\n## Active Guidance\n\n{items}\n",
        encoding="utf-8",
    )

    prompt, breakdown = build_system_prompt_with_debug(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )

    assert "[Reviewed Behavioral Guidance]" not in prompt
    assert "First compact guidance." not in prompt
    assert "Second long guidance" not in prompt
    assert "Third compact guidance." not in prompt
    assert breakdown["behavioral_guidance_runtime_enabled"] is False
    assert breakdown["behavioral_guidance_status"] == "dormant_before_go_live"
    assert breakdown["behavioral_guidance_items_found"] == 0
    assert breakdown["behavioral_guidance_items_included"] == 0
    assert breakdown["behavioral_guidance_items_skipped"] == 0
    assert breakdown["behavioral_guidance_budget_chars"] == 0
    assert breakdown["behavioral_guidance_chars"] == 0


def test_behavioral_guidance_debug_counts_items(context_project):
    context_project["behavioral"].write_text(
        """# BEHAVIORAL_GUIDANCE.md

## Active Guidance

- Guidance: First reviewed behavior.
- Guidance: Second reviewed behavior.
""",
        encoding="utf-8",
    )

    prompt, breakdown = build_system_prompt_with_debug(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )

    assert "[Reviewed Behavioral Guidance]" not in prompt
    assert "First reviewed behavior." not in prompt
    assert "Second reviewed behavior." not in prompt
    assert breakdown["behavioral_guidance_runtime_enabled"] is False
    assert breakdown["behavioral_guidance_status"] == "dormant_before_go_live"
    assert breakdown["behavioral_guidance_chars"] == 0
    assert breakdown["behavioral_guidance_items_found"] == 0
    assert breakdown["behavioral_guidance_items_included"] == 0
    assert breakdown["behavioral_guidance_items_skipped"] == 0


def test_behavioral_guidance_label_is_not_loaded_while_dormant(context_project):
    context_project["behavioral"].write_text(
        "# BEHAVIORAL_GUIDANCE.md\n\n## Active Guidance\n\n- Guidance: Use careful wording.\n",
        encoding="utf-8",
    )

    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[],
        tool_descriptions=None,
    )

    assert "[Reviewed Behavioral Guidance]" not in prompt
    assert "Active behavioral guidance proposed by the AI" not in prompt
    assert "approved/applied by an admin" not in prompt
    assert "below soul.md and operational guidance in precedence" not in prompt
    assert "Use careful wording." not in prompt


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
        "skipped_empty_chunks": 0,
        "skipped_budget_chunks": 1,
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
