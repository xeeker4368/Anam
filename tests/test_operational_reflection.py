import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture()
def operational_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "working.db")
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "chromadb"))

    import tir.memory.db as db_mod
    import tir.artifacts.service as artifacts_mod
    import tir.behavioral_guidance.service as guidance_mod
    import tir.open_loops.service as open_loops_mod
    import tir.review.service as review_mod
    import tir.reflection.operational as operational_mod

    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    importlib.reload(guidance_mod)
    importlib.reload(open_loops_mod)
    importlib.reload(review_mod)
    importlib.reload(operational_mod)
    db_mod.init_databases()
    user = db_mod.create_user("Lyle", role="admin")
    return {
        "db": db_mod,
        "artifacts": artifacts_mod,
        "guidance": guidance_mod,
        "open_loops": open_loops_mod,
        "review": review_mod,
        "operational": operational_mod,
        "user": user,
        "workspace": tmp_path / "workspace",
    }


def _selection():
    return {
        "selection_mode": "date",
        "local_date": "2026-05-08",
        "timezone": "UTC",
        "local_offset": "+00:00",
        "utc_start": "2026-05-08T00:00:00+00:00",
        "utc_end": "2026-05-09T00:00:00+00:00",
    }


def _set_table_timestamps(db_mod, table, id_column, item_id, **timestamps):
    assignments = ", ".join(f"{field} = ?" for field in timestamps)
    values = [*timestamps.values(), item_id]
    with db_mod.get_connection() as conn:
        conn.execute(
            f"UPDATE main.{table} SET {assignments} WHERE {id_column} = ?",
            values,
        )
        conn.commit()


def _set_message_timestamp(db_mod, message_id, timestamp):
    with db_mod.get_connection() as conn:
        conn.execute(
            "UPDATE main.messages SET timestamp = ? WHERE id = ?",
            (timestamp, message_id),
        )
        conn.execute(
            "UPDATE archive.messages SET timestamp = ? WHERE id = ?",
            (timestamp, message_id),
        )
        conn.commit()


def _make_tool_failure(env):
    db_mod = env["db"]
    user_id = env["user"]["id"]
    conversation_id = db_mod.start_conversation(user_id)
    message = db_mod.save_message(
        conversation_id,
        user_id,
        "assistant",
        "Tool failed.",
        tool_trace=json.dumps([
            {
                "tool_calls": [{"name": "memory_search"}],
                "tool_results": [
                    {
                        "tool_name": "memory_search",
                        "ok": False,
                        "error": "backend unavailable",
                    }
                ],
            }
        ]),
    )
    _set_message_timestamp(db_mod, message["id"], "2026-05-08T12:00:00+00:00")
    return conversation_id, message


def _populate_activity(env):
    db_mod = env["db"]
    conversation_id, message = _make_tool_failure(env)
    artifact = env["artifacts"].create_artifact(
        artifact_type="generated_file",
        title="Generated report",
        path="generated/report.md",
        status="active",
        source="reflection",
        source_conversation_id=conversation_id,
        source_message_id=message["id"],
        source_tool_name="workspace_write",
        workspace_root=env["workspace"],
    )
    _set_table_timestamps(
        db_mod,
        "artifacts",
        "artifact_id",
        artifact["artifact_id"],
        created_at="2026-05-08T12:05:00+00:00",
        updated_at="2026-05-08T12:05:00+00:00",
    )
    review_item = env["review"].create_review_item(
        title="Existing review item",
        category="tool_failure",
        source_message_id=message["id"],
    )
    _set_table_timestamps(
        db_mod,
        "review_items",
        "item_id",
        review_item["item_id"],
        created_at="2026-05-08T12:06:00+00:00",
        updated_at="2026-05-08T12:06:00+00:00",
    )
    open_loop = env["open_loops"].create_open_loop(
        title="Follow up on failed tool",
        loop_type="tool_failure_followup",
        source_conversation_id=conversation_id,
        source_message_id=message["id"],
        next_action="Inspect failure.",
    )
    _set_table_timestamps(
        db_mod,
        "open_loops",
        "open_loop_id",
        open_loop["open_loop_id"],
        created_at="2026-05-08T12:07:00+00:00",
        updated_at="2026-05-08T12:07:00+00:00",
    )
    proposal = env["guidance"].create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Keep tool failure reporting concrete.",
        rationale="Tool failures need clear review.",
        source_conversation_id=conversation_id,
        source_message_id=message["id"],
        source_channel="chat",
    )
    _set_table_timestamps(
        db_mod,
        "behavioral_guidance_proposals",
        "proposal_id",
        proposal["proposal_id"],
        created_at="2026-05-08T12:08:00+00:00",
        updated_at="2026-05-08T12:08:00+00:00",
    )
    return {
        "conversation_id": conversation_id,
        "message": message,
        "artifact": artifact,
    }


def _model_output(source_message_id="msg-1", source_artifact_id=None):
    return json.dumps(
        {
            "operational_observations": [
                {
                    "title": "Tool failure needs review",
                    "description": "memory_search failed.",
                    "category": "tool_failure",
                    "severity": "normal",
                    "evidence": "tool trace had ok=false",
                    "source_type": "tool_trace",
                    "source_message_id": source_message_id,
                    "source_artifact_id": source_artifact_id,
                    "source_tool_name": "memory_search",
                }
            ],
            "review_item_candidates": [
                {
                    "title": "Tool failure needs review",
                    "description": "memory_search failed.",
                    "category": "tool_failure",
                    "priority": "normal",
                    "source_type": "tool_trace",
                    "source_message_id": source_message_id,
                    "source_artifact_id": source_artifact_id,
                    "source_tool_name": "memory_search",
                    "rationale": "A failed tool should be reviewed.",
                }
            ],
            "open_loop_candidates": [
                {"title": "Open loop candidate should be printed only"}
            ],
            "diagnostic_notes": ["Tool failure observed."],
            "no_action_reason": None,
        }
    )


def test_activity_packet_includes_operational_sources(operational_env):
    operational = operational_env["operational"]
    _populate_activity(operational_env)

    packet, meta = operational.build_operational_activity_packet(_selection())

    assert "[Tool trace activity]" in packet
    assert "memory_search" in packet
    assert "status=failure" in packet
    assert "[Artifact activity]" in packet
    assert "Generated report" in packet
    assert "[Review queue activity]" in packet
    assert "Existing review item" in packet
    assert "[Open-loop activity]" in packet
    assert "Follow up on failed tool" in packet
    assert "[Behavioral guidance operational metadata]" in packet
    assert "Keep tool failure reporting concrete" not in packet
    assert meta["counts"]["tool_failures"] == 1
    assert meta["counts"]["artifacts"] == 1
    assert meta["counts"]["review_items"] == 1
    assert meta["counts"]["open_loops"] == 1
    assert meta["counts"]["behavioral_guidance_proposals"] == 1


def test_dry_run_writes_nothing(operational_env, monkeypatch):
    operational = operational_env["operational"]
    activity = _populate_activity(operational_env)
    monkeypatch.setattr(
        operational,
        "chat_completion_json",
        lambda *args, **kwargs: _model_output(source_message_id=activity["message"]["id"]),
    )

    result = operational.run_operational_reflection_day(date_text="2026-05-08")

    assert result["mode"] == "dry-run"
    assert len(result["review_item_candidates"]) == 1
    items = operational_env["review"].list_review_items(limit=50)
    assert len(items) == 1
    assert items[0]["title"] == "Existing review item"


def test_write_mode_creates_review_items_only(operational_env, monkeypatch):
    operational = operational_env["operational"]
    activity = _populate_activity(operational_env)
    monkeypatch.setattr(
        operational,
        "chat_completion_json",
        lambda *args, **kwargs: _model_output(source_message_id=activity["message"]["id"]),
    )

    result = operational.run_operational_reflection_day(
        date_text="2026-05-08",
        write=True,
    )

    assert result["mode"] == "write"
    created = result["write_result"]["created"]
    assert len(created) == 1
    assert created[0]["category"] == "tool_failure"
    assert created[0]["metadata"]["generation_method"] == "operational_reflection_v1"
    assert created[0]["metadata"]["source_window"]["local_date"] == "2026-05-08"
    assert operational_env["open_loops"].list_open_loops(limit=50)[0]["title"] == "Follow up on failed tool"


def test_malformed_model_json_fails_and_writes_nothing(operational_env, monkeypatch):
    operational = operational_env["operational"]
    _populate_activity(operational_env)
    monkeypatch.setattr(operational, "chat_completion_json", lambda *args, **kwargs: "{bad")

    with pytest.raises(operational.OperationalReflectionError, match="malformed JSON"):
        operational.run_operational_reflection_day(date_text="2026-05-08", write=True)

    items = operational_env["review"].list_review_items(limit=50)
    assert len(items) == 1


def test_duplicate_candidate_is_skipped(operational_env, monkeypatch):
    operational = operational_env["operational"]
    activity = _populate_activity(operational_env)
    existing = operational_env["review"].create_review_item(
        title="Tool failure needs review",
        category="tool_failure",
        source_message_id=activity["message"]["id"],
        metadata={"generation_method": "operational_reflection_v1"},
    )
    monkeypatch.setattr(
        operational,
        "chat_completion_json",
        lambda *args, **kwargs: _model_output(source_message_id=activity["message"]["id"]),
    )

    result = operational.run_operational_reflection_day(
        date_text="2026-05-08",
        write=True,
    )

    assert result["write_result"]["created"] == []
    assert result["write_result"]["skipped_duplicates"][0]["title"] == existing["title"]


def test_behavioral_guidance_file_is_not_mutated(operational_env, monkeypatch):
    operational = operational_env["operational"]
    activity = _populate_activity(operational_env)
    guidance_path = Path(operational_env["workspace"]).parent / "BEHAVIORAL_GUIDANCE.md"
    guidance_path.write_text("seed guidance file\n", encoding="utf-8")
    monkeypatch.setattr(
        operational,
        "chat_completion_json",
        lambda *args, **kwargs: _model_output(source_message_id=activity["message"]["id"]),
    )

    operational.run_operational_reflection_day(date_text="2026-05-08", write=True)

    assert guidance_path.read_text(encoding="utf-8") == "seed guidance file\n"


def test_no_scheduler_or_background_api_is_exposed():
    import tir.reflection.operational as operational

    names = set(dir(operational))
    assert "schedule_operational_reflection" not in names
    assert "run_background_operational_reflection" not in names
