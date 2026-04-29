import importlib
import sqlite3
from unittest.mock import patch

import pytest

from tir.artifacts.service import create_artifact
from tir.diagnostics.service import (
    DiagnosticValidationError,
    create_diagnostic_issue,
    get_diagnostic_issue,
    list_diagnostic_issues,
    update_diagnostic_status,
)
from tir.feedback.service import create_feedback_record
from tir.open_loops.service import create_open_loop
from tir.workspace.service import ensure_workspace


@pytest.fixture()
def temp_stores(tmp_path):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod

        importlib.reload(db_mod)
        db_mod.init_databases()
        yield {
            "db": db_mod,
            "workspace_root": workspace_root,
            "archive_db": tmp_path / "archive.db",
            "working_db": tmp_path / "working.db",
        }


def test_create_get_list_and_update_diagnostic_issue(temp_stores):
    diagnostic = create_diagnostic_issue(
        title="Retrieval missed obvious prior context",
        description="A targeted memory search failed to surface known relevant messages.",
        category="retrieval_quality",
        status="open",
        severity="high",
        evidence_summary="Query for project decision returned unrelated chunks.",
        suspected_component="memory_search",
        source="test",
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        source_tool_name="memory_search",
        target_type="tool_trace",
        target_id="trace-1",
        next_action="Inspect retrieval query and ranking",
        metadata={"query": "project decision"},
    )

    assert diagnostic["diagnostic_id"]
    assert diagnostic["title"] == "Retrieval missed obvious prior context"
    assert diagnostic["description"] == "A targeted memory search failed to surface known relevant messages."
    assert diagnostic["category"] == "retrieval_quality"
    assert diagnostic["status"] == "open"
    assert diagnostic["severity"] == "high"
    assert diagnostic["evidence_summary"] == "Query for project decision returned unrelated chunks."
    assert diagnostic["suspected_component"] == "memory_search"
    assert diagnostic["source"] == "test"
    assert diagnostic["source_conversation_id"] == "conv-1"
    assert diagnostic["source_message_id"] == "msg-1"
    assert diagnostic["source_tool_name"] == "memory_search"
    assert diagnostic["target_type"] == "tool_trace"
    assert diagnostic["target_id"] == "trace-1"
    assert diagnostic["next_action"] == "Inspect retrieval query and ranking"
    assert diagnostic["resolved_at"] is None
    assert diagnostic["metadata"] == {"query": "project decision"}
    assert diagnostic["metadata_json"] == '{"query": "project decision"}'

    fetched = get_diagnostic_issue(diagnostic["diagnostic_id"])
    assert fetched == diagnostic

    listed = list_diagnostic_issues(
        category="retrieval_quality",
        status="open",
        severity="high",
        source_conversation_id="conv-1",
        target_type="tool_trace",
        target_id="trace-1",
    )
    assert [item["diagnostic_id"] for item in listed] == [diagnostic["diagnostic_id"]]

    updated = update_diagnostic_status(diagnostic["diagnostic_id"], "investigating")
    assert updated["status"] == "investigating"
    assert updated["resolved_at"] is None
    assert updated["updated_at"] >= diagnostic["updated_at"]


def test_required_title_and_evidence_summary_validation(temp_stores):
    with pytest.raises(DiagnosticValidationError):
        create_diagnostic_issue(
            title="   ",
            evidence_summary="Evidence is required",
        )

    with pytest.raises(DiagnosticValidationError):
        create_diagnostic_issue(
            title="Required title",
            evidence_summary="   ",
        )


def test_invalid_category_status_and_severity_rejected(temp_stores):
    with pytest.raises(DiagnosticValidationError):
        create_diagnostic_issue(
            title="Bad category",
            evidence_summary="Invalid category",
            category="research_idea",
        )

    with pytest.raises(DiagnosticValidationError):
        create_diagnostic_issue(
            title="Bad status",
            evidence_summary="Invalid status",
            status="accepted",
        )

    with pytest.raises(DiagnosticValidationError):
        create_diagnostic_issue(
            title="Bad severity",
            evidence_summary="Invalid severity",
            severity="urgent",
        )

    diagnostic = create_diagnostic_issue(
        title="Good",
        evidence_summary="Valid",
    )
    with pytest.raises(DiagnosticValidationError):
        update_diagnostic_status(diagnostic["diagnostic_id"], "unknown")


def test_non_serializable_metadata_rejected(temp_stores):
    with pytest.raises(DiagnosticValidationError):
        create_diagnostic_issue(
            title="Bad metadata",
            evidence_summary="Metadata cannot be serialized",
            metadata={"bad": object()},
        )


def test_related_feedback_open_loop_and_artifact_links_work(temp_stores):
    artifact = create_artifact(
        artifact_type="research_note",
        title="Diagnostic target artifact",
        path="research/diagnostic-target.md",
        workspace_root=temp_stores["workspace_root"],
    )
    open_loop = create_open_loop(
        title="Diagnostic target loop",
        related_artifact_id=artifact["artifact_id"],
    )
    feedback = create_feedback_record(
        feedback_type="tool_result_inaccurate",
        title="Bad tool result",
        user_feedback="The tool result was inaccurate.",
        related_artifact_id=artifact["artifact_id"],
        related_open_loop_id=open_loop["open_loop_id"],
    )

    diagnostic = create_diagnostic_issue(
        title="Tool result quality issue",
        evidence_summary="User reported inaccurate tool output.",
        category="tool_result_quality",
        related_feedback_id=feedback["feedback_id"],
        related_open_loop_id=open_loop["open_loop_id"],
        related_artifact_id=artifact["artifact_id"],
    )

    assert diagnostic["related_feedback_id"] == feedback["feedback_id"]
    assert diagnostic["related_open_loop_id"] == open_loop["open_loop_id"]
    assert diagnostic["related_artifact_id"] == artifact["artifact_id"]

    listed = list_diagnostic_issues(
        related_feedback_id=feedback["feedback_id"],
        related_open_loop_id=open_loop["open_loop_id"],
        related_artifact_id=artifact["artifact_id"],
    )
    assert [item["diagnostic_id"] for item in listed] == [diagnostic["diagnostic_id"]]


def test_related_foreign_keys_are_enforced(temp_stores):
    with pytest.raises(sqlite3.IntegrityError):
        create_diagnostic_issue(
            title="Bad feedback link",
            evidence_summary="Missing feedback",
            related_feedback_id="missing-feedback",
        )

    with pytest.raises(sqlite3.IntegrityError):
        create_diagnostic_issue(
            title="Bad open-loop link",
            evidence_summary="Missing open loop",
            related_open_loop_id="missing-open-loop",
        )

    with pytest.raises(sqlite3.IntegrityError):
        create_diagnostic_issue(
            title="Bad artifact link",
            evidence_summary="Missing artifact",
            related_artifact_id="missing-artifact",
        )


def test_resolved_at_lifecycle(temp_stores):
    diagnostic = create_diagnostic_issue(
        title="Lifecycle",
        evidence_summary="Track lifecycle fields",
    )

    resolved = update_diagnostic_status(diagnostic["diagnostic_id"], "resolved")
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None

    blocked = update_diagnostic_status(diagnostic["diagnostic_id"], "blocked")
    assert blocked["status"] == "blocked"
    assert blocked["resolved_at"] is None

    archived = update_diagnostic_status(diagnostic["diagnostic_id"], "archived")
    assert archived["status"] == "archived"
    assert archived["resolved_at"] is not None

    reopened = update_diagnostic_status(diagnostic["diagnostic_id"], "open")
    assert reopened["status"] == "open"
    assert reopened["resolved_at"] is None


def test_diagnostic_issues_table_is_working_db_only(temp_stores):
    archive_conn = sqlite3.connect(temp_stores["archive_db"])
    working_conn = sqlite3.connect(temp_stores["working_db"])
    try:
        archive_tables = {
            row[0]
            for row in archive_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        working_tables = {
            row[0]
            for row in working_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        archive_conn.close()
        working_conn.close()

    assert "diagnostic_issues" not in archive_tables
    assert "diagnostic_issues" in working_tables


def test_diagnostic_creation_does_not_invoke_memory_indexing(temp_stores):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        create_diagnostic_issue(
            title="No indexing",
            evidence_summary="Diagnostics stay metadata-only.",
            category="generic",
            metadata={"source": "test"},
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
