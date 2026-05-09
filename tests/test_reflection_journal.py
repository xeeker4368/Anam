import json
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


JOURNAL_BODY = """## Notable Interactions
The reviewed material included a concrete correction.

## Corrections Or Clarifications
The correction was about source framing.

## Behavioral Guidance Activity
No guidance activity changed the journal instructions.

## Unresolved Questions
None were explicit.

## Possible Follow-Ups
Review whether the correction recurs.

## Reflection
I can describe the correction without treating it as a personality trait.
"""


@pytest.fixture()
def reflection_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "working.db")
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")

    import tir.memory.db as db_mod
    import tir.behavioral_guidance.service as guidance_mod
    import tir.artifacts.service as artifacts_mod
    import tir.open_loops.service as open_loops_mod
    import tir.review.service as review_mod
    import tir.reflection.journal as journal_mod

    importlib.reload(db_mod)
    importlib.reload(guidance_mod)
    importlib.reload(artifacts_mod)
    importlib.reload(open_loops_mod)
    importlib.reload(review_mod)
    importlib.reload(journal_mod)
    db_mod.init_databases()
    user = db_mod.create_user("Lyle", role="admin")
    return {
        "db": db_mod,
        "guidance": guidance_mod,
        "artifacts": artifacts_mod,
        "open_loops": open_loops_mod,
        "review": review_mod,
        "journal": journal_mod,
        "user": user,
        "tmp_path": tmp_path,
        "workspace": tmp_path / "workspace",
    }


def _set_conversation_started(db_mod, conversation_id, timestamp):
    with db_mod.get_connection() as conn:
        conn.execute(
            "UPDATE main.conversations SET started_at = ? WHERE id = ?",
            (timestamp, conversation_id),
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


def _set_table_timestamps(db_mod, table, id_column, item_id, **timestamps):
    assignments = ", ".join(f"{field} = ?" for field in timestamps)
    values = [*timestamps.values(), item_id]
    with db_mod.get_connection() as conn:
        conn.execute(
            f"UPDATE main.{table} SET {assignments} WHERE {id_column} = ?",
            values,
        )
        conn.commit()


def _make_conversation(db_mod, user_id, *, started_at, message_times):
    conversation_id = db_mod.start_conversation(user_id)
    _set_conversation_started(db_mod, conversation_id, started_at)
    messages = []
    for index, timestamp in enumerate(message_times):
        message = db_mod.save_message(
            conversation_id,
            user_id,
            "user" if index % 2 == 0 else "assistant",
            f"message {index}",
        )
        _set_message_timestamp(db_mod, message["id"], timestamp)
        messages.append(message)
    return conversation_id, messages


def _activity_selection():
    return {
        "selection_mode": "date",
        "local_date": "2026-05-08",
        "timezone": "UTC",
        "local_offset": "+00:00",
        "utc_start": "2026-05-08T00:00:00+00:00",
        "utc_end": "2026-05-09T00:00:00+00:00",
    }


def test_local_date_window_selects_by_message_activity(reflection_env):
    db_mod = reflection_env["db"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    tzinfo = timezone(timedelta(hours=-4))

    included_id, _messages = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-07T23:00:00+00:00",
        message_times=[
            "2026-05-08T03:59:00+00:00",
            "2026-05-08T04:30:00+00:00",
        ],
    )
    _excluded_id, _messages = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T05:00:00+00:00",
        message_times=["2026-05-09T04:01:00+00:00"],
    )

    rows, selection = journal.list_conversations_for_reflection_journal(
        date_text="2026-05-08",
        tzinfo=tzinfo,
    )

    assert selection["utc_start"] == "2026-05-08T04:00:00+00:00"
    assert selection["utc_end"] == "2026-05-09T04:00:00+00:00"
    assert [row["id"] for row in rows] == [included_id]
    assert rows[0]["window_message_count"] == 1


def test_since_rejects_naive_timestamp(reflection_env):
    journal = reflection_env["journal"]

    with pytest.raises(journal.ReflectionJournalError, match="timezone or Z"):
        journal.list_conversations_for_reflection_journal(since="2026-05-08T12:00:00")


def test_empty_day_returns_no_content_without_model_call(reflection_env, monkeypatch):
    journal = reflection_env["journal"]
    called = False

    def fake_model(*args, **kwargs):
        nonlocal called
        called = True
        return JOURNAL_BODY

    monkeypatch.setattr(journal, "chat_completion_text", fake_model)

    result = journal.generate_reflection_journal_day(date_text="2026-05-08")

    assert result["status"] == "no_content"
    assert result["journal"] is None
    assert result["reason"]
    assert called is False


def test_journal_prompt_uses_short_journal_space_wording(reflection_env):
    journal = reflection_env["journal"]
    messages = journal.build_reflection_journal_messages(
        selection={"local_date": "2026-05-08", "selection_mode": "date"},
        conversations=[{"id": "conv-1"}],
        transcript="A conversation happened.",
        guidance_activity=[],
        activity_packet="[Conversation activity]\n- compact packet line",
        entity_context={
            "soul": "Seed context line.",
            "behavioral_guidance": None,
        },
    )

    system = messages[0]["content"]
    user_prompt = messages[1]["content"]
    assert system.startswith("This is your journal space.")
    assert "Write in your own voice" in system
    assert "This is a journal, not an audit log or external report." in system
    assert "Seed context line." in user_prompt
    assert "[Current seed context]" in user_prompt
    assert "[Active reviewed behavioral guidance]" in user_prompt
    assert "Today's activity packet" in user_prompt
    assert "- compact packet line" in user_prompt


def test_journal_prompt_includes_active_behavioral_guidance(reflection_env):
    journal = reflection_env["journal"]
    messages = journal.build_reflection_journal_messages(
        selection={"local_date": "2026-05-08", "selection_mode": "date"},
        conversations=[{"id": "conv-1"}],
        transcript="A conversation happened.",
        guidance_activity=[],
        activity_packet="[Conversation activity]\n- compact packet line",
        entity_context={
            "soul": "Seed context line.",
            "behavioral_guidance": "[Reviewed Behavioral Guidance]\n\n- Speak plainly.",
        },
    )

    user_prompt = messages[1]["content"]
    assert "[Reviewed Behavioral Guidance]" in user_prompt
    assert "- Speak plainly." in user_prompt


def test_journal_prompt_omits_old_compliance_heavy_wording(reflection_env):
    journal = reflection_env["journal"]
    messages = journal.build_reflection_journal_messages(
        selection={"local_date": "2026-05-08", "selection_mode": "date"},
        conversations=[{"id": "conv-1"}],
        transcript="A conversation happened.",
        guidance_activity=[],
        activity_packet="[Conversation activity]\n- compact packet line",
        entity_context={
            "soul": "Seed context line.",
            "behavioral_guidance": None,
        },
    )
    prompt_text = "\n\n".join(message["content"] for message in messages)

    forbidden = [
        "unnamed AI entity operating within Project Anam",
        "unnamed AI entity",
        "do not assign a name",
        "do not assign personality",
        "do not claim feelings as facts",
        "Do not create behavioral guidance proposals",
        "Do not edit or refer to mutating BEHAVIORAL_GUIDANCE.md",
        "Do not frame this as self-modification",
        "Avoid melodramatic or self-mythologizing language",
    ]
    for phrase in forbidden:
        assert phrase not in prompt_text


def test_daily_activity_packet_includes_available_activity_sources(reflection_env):
    db_mod = reflection_env["db"]
    guidance = reflection_env["guidance"]
    artifacts = reflection_env["artifacts"]
    open_loops = reflection_env["open_loops"]
    review = reflection_env["review"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    selection = _activity_selection()

    conversation_id, messages = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-07T20:00:00+00:00",
        message_times=[
            "2026-05-08T10:00:00+00:00",
            "2026-05-08T10:01:00+00:00",
        ],
    )
    trace_message = db_mod.save_message(
        conversation_id,
        user_id,
        "assistant",
        "Tool result summary",
        tool_trace=json.dumps([
            {
                "iteration": 0,
                "tool_calls": [{"name": "memory_search", "arguments": {"q": "x"}}],
                "tool_results": [{"tool_name": "memory_search", "ok": True}],
            }
        ]),
    )
    _set_message_timestamp(db_mod, trace_message["id"], "2026-05-08T10:02:00+00:00")

    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Keep source framing explicit.",
        rationale="The conversation corrected a source boundary.",
        source_conversation_id=conversation_id,
        source_channel="chat",
    )
    _set_table_timestamps(
        db_mod,
        "behavioral_guidance_proposals",
        "proposal_id",
        proposal["proposal_id"],
        created_at="2026-05-08T11:00:00+00:00",
        updated_at="2026-05-08T11:00:00+00:00",
    )

    review_item = review.create_review_item(
        title="Check unresolved source issue",
        category="follow_up",
        priority="high",
        source_type="conversation",
        source_conversation_id=conversation_id,
        source_message_id=messages[0]["id"],
    )
    _set_table_timestamps(
        db_mod,
        "review_items",
        "item_id",
        review_item["item_id"],
        created_at="2026-05-08T12:00:00+00:00",
        updated_at="2026-05-08T12:00:00+00:00",
    )

    artifact = artifacts.create_artifact(
        artifact_type="generated_file",
        title="Daily report",
        path="generated/daily-report.md",
        status="active",
        source="tool",
        source_conversation_id=conversation_id,
        source_message_id=messages[1]["id"],
        source_tool_name="write_file",
        metadata={"source_role": "generated_artifact", "origin": "generated"},
        workspace_root=reflection_env["workspace"],
    )
    _set_table_timestamps(
        db_mod,
        "artifacts",
        "artifact_id",
        artifact["artifact_id"],
        created_at="2026-05-08T13:00:00+00:00",
        updated_at="2026-05-08T13:00:00+00:00",
    )

    open_loop = open_loops.create_open_loop(
        title="Follow up on generated report",
        loop_type="journal_followup",
        priority="normal",
        related_artifact_id=artifact["artifact_id"],
        source="reflection",
        source_conversation_id=conversation_id,
        next_action="Review the report.",
    )
    _set_table_timestamps(
        db_mod,
        "open_loops",
        "open_loop_id",
        open_loop["open_loop_id"],
        created_at="2026-05-08T14:00:00+00:00",
        updated_at="2026-05-08T14:00:00+00:00",
    )

    conversations = [
        {
            "id": conversation_id,
            "user_id": user_id,
            "started_at": "2026-05-07T20:00:00+00:00",
            "ended_at": None,
        }
    ]
    packet, meta = journal.build_daily_activity_packet(selection, conversations)

    assert "[Conversation activity]" in packet
    assert f"conversation={conversation_id}" in packet
    assert "[Behavioral guidance activity]" in packet
    assert "Keep source framing explicit." in packet
    assert "[Review queue activity]" in packet
    assert "Check unresolved source issue" in packet
    assert "[Open-loop activity]" in packet
    assert "Follow up on generated report" in packet
    assert "[Tool activity]" in packet
    assert "memory_search" in packet
    assert "[Artifact activity]" in packet
    assert "Daily report" in packet
    assert "role=Generated artifact" in packet
    assert "origin=Generated" in packet
    assert "[Generated files]" in packet
    assert meta["counts"]["behavioral_guidance"] == 1
    assert meta["counts"]["review_items"] == 1
    assert meta["counts"]["open_loops"] == 1
    assert meta["counts"]["tool_traces"] == 1
    assert meta["counts"]["artifacts"] == 1


def test_daily_activity_packet_marks_empty_sources(reflection_env):
    journal = reflection_env["journal"]
    packet, meta = journal.build_daily_activity_packet(_activity_selection(), [])

    assert "No conversation activity found in this window." in packet
    assert "No review queue activity found in this window." in packet
    assert "No open-loop activity found in this window." in packet
    assert "No tool activity found in this window." in packet
    assert "No artifact activity found in this window." in packet
    assert meta["truncated"] is False


def test_daily_activity_packet_enforces_limits_and_budget(reflection_env, monkeypatch):
    db_mod = reflection_env["db"]
    review = reflection_env["review"]
    journal = reflection_env["journal"]
    selection = _activity_selection()

    for index in range(3):
        item = review.create_review_item(
            title=f"Review item with enough text to consume packet budget {index}",
            category="research",
        )
        _set_table_timestamps(
            db_mod,
            "review_items",
            "item_id",
            item["item_id"],
            created_at=f"2026-05-08T12:0{index}:00+00:00",
            updated_at=f"2026-05-08T12:0{index}:00+00:00",
        )

    monkeypatch.setattr(journal, "REFLECTION_REVIEW_LIMIT", 1)
    packet, meta = journal.build_daily_activity_packet(selection, [])
    assert "additional review queue activity items omitted by limit" in packet
    assert meta["skipped"]["review_queue_activity"] == 2

    monkeypatch.setattr(journal, "REFLECTION_ACTIVITY_CHAR_BUDGET", 360)
    packet, meta = journal.build_daily_activity_packet(selection, [])
    assert meta["truncated"] is True
    assert len(packet) <= 360


def test_dry_run_generates_journal_and_writes_nothing(reflection_env, monkeypatch):
    db_mod = reflection_env["db"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T12:00:00+00:00",
        message_times=["2026-05-08T12:00:00+00:00", "2026-05-08T12:01:00+00:00"],
    )
    monkeypatch.setattr(journal, "chat_completion_text", lambda *args, **kwargs: JOURNAL_BODY)

    result = journal.run_reflection_journal_day(date_text="2026-05-08")

    assert result["status"] == "generated"
    assert result["target_path"] == "journals/2026-05-08.md"
    assert "# Reflection Journal — 2026-05-08" in result["journal"]
    assert not (reflection_env["workspace"] / "journals" / "2026-05-08.md").exists()


def test_write_mode_creates_workspace_journal(reflection_env, monkeypatch):
    db_mod = reflection_env["db"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T12:00:00+00:00",
        message_times=["2026-05-08T12:00:00+00:00", "2026-05-08T12:01:00+00:00"],
    )
    monkeypatch.setattr(journal, "chat_completion_text", lambda *args, **kwargs: JOURNAL_BODY)

    result = journal.run_reflection_journal_day(date_text="2026-05-08", write=True)

    target = reflection_env["workspace"] / "journals" / "2026-05-08.md"
    assert result["write_result"]["path"] == "journals/2026-05-08.md"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "Messages reviewed: 2" in content
    assert "Do not" not in content
    assert reflection_env["artifacts"].list_artifacts(
        workspace_root=reflection_env["workspace"],
    ) == []


def test_existing_journal_file_is_not_overwritten(reflection_env, monkeypatch):
    db_mod = reflection_env["db"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T12:00:00+00:00",
        message_times=["2026-05-08T12:00:00+00:00", "2026-05-08T12:01:00+00:00"],
    )
    target = reflection_env["workspace"] / "journals" / "2026-05-08.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(journal, "chat_completion_text", lambda *args, **kwargs: JOURNAL_BODY)

    with pytest.raises(journal.ReflectionJournalError, match="already exists"):
        journal.run_reflection_journal_day(date_text="2026-05-08", write=True)

    assert target.read_text(encoding="utf-8") == "existing"


def test_empty_model_output_fails_clearly(reflection_env, monkeypatch):
    db_mod = reflection_env["db"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T12:00:00+00:00",
        message_times=["2026-05-08T12:00:00+00:00"],
    )
    monkeypatch.setattr(journal, "chat_completion_text", lambda *args, **kwargs: " ")

    with pytest.raises(journal.ReflectionJournalError, match="empty"):
        journal.generate_reflection_journal_day(date_text="2026-05-08")


def test_behavioral_guidance_file_is_not_mutated(reflection_env, monkeypatch):
    db_mod = reflection_env["db"]
    journal = reflection_env["journal"]
    user_id = reflection_env["user"]["id"]
    guidance_path = reflection_env["tmp_path"] / "BEHAVIORAL_GUIDANCE.md"
    guidance_path.write_text("seed guidance file\n", encoding="utf-8")
    _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T12:00:00+00:00",
        message_times=["2026-05-08T12:00:00+00:00"],
    )
    monkeypatch.setattr(journal, "chat_completion_text", lambda *args, **kwargs: JOURNAL_BODY)

    journal.run_reflection_journal_day(date_text="2026-05-08", write=True)

    assert guidance_path.read_text(encoding="utf-8") == "seed guidance file\n"


def test_no_scheduler_or_background_api_is_exposed():
    import tir.reflection.journal as journal

    public_names = {name for name in dir(journal) if not name.startswith("_")}
    assert "schedule_reflection_journal" not in public_names
    assert "run_nightly_reflection" not in public_names
