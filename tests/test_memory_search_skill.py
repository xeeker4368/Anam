from unittest.mock import patch

import pytest

from skills.active.memory_search.memory_search import memory_search
from tir.config import SKILLS_DIR
from tir.tools.registry import SkillRegistry


def test_memory_search_skill_loads_from_active_directory():
    registry = SkillRegistry.from_directory(SKILLS_DIR)

    tools = registry.list_tools()

    assert any(tool["function"]["name"] == "memory_search" for tool in tools)


def test_empty_skills_directory_loads_zero_tools(tmp_path):
    registry = SkillRegistry.from_directory(tmp_path)

    assert registry.list_tools() == []


def test_malformed_active_skill_fails_loudly(tmp_path):
    bad_skill = tmp_path / "bad_skill"
    bad_skill.mkdir()
    (bad_skill / "SKILL.md").write_text(
        "---\nname: bad_skill\nversion: \"1.0\"\n---\nMissing description.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Missing required frontmatter field 'description'"):
        SkillRegistry.from_directory(tmp_path)


@patch("skills.active.memory_search.memory_search.retrieve")
def test_memory_search_formats_results(mock_retrieve):
    mock_retrieve.return_value = [
        {
            "text": "We discussed retrieval traces.",
            "metadata": {
                "source_type": "conversation",
                "created_at": "2026-04-27T12:00:00+00:00",
            },
        }
    ]

    result = memory_search("retrieval traces")

    assert "1. [conversation - 2026-04-27T12:00:00+00:00]" in result
    assert "We discussed retrieval traces." in result
    mock_retrieve.assert_called_once_with(query="retrieval traces", max_results=5)


@patch("skills.active.memory_search.memory_search.retrieve")
def test_memory_search_empty_results(mock_retrieve):
    mock_retrieve.return_value = []

    assert memory_search("nothing") == "No memories found for that query."
