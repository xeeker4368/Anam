import importlib
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def review_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "working.db")

    import tir.memory.db as db_mod
    import tir.behavioral_guidance.service as guidance_mod
    import tir.behavioral_guidance.review as review_mod

    importlib.reload(db_mod)
    importlib.reload(guidance_mod)
    importlib.reload(review_mod)
    db_mod.init_databases()

    user = db_mod.create_user("Lyle", role="admin")
    conversation_id = db_mod.start_conversation(user["id"])
    first_message = db_mod.save_message(
        conversation_id,
        user["id"],
        "user",
        "When I correct source framing, do not treat uploaded files as truth.",
    )
    db_mod.save_message(
        conversation_id,
        user["id"],
        "assistant",
        "Understood. I should frame them as uploaded sources.",
    )
    db_mod.save_message(
        conversation_id,
        user["id"],
        "user",
        "That distinction matters for future behavior.",
    )

    return {
        "db": db_mod,
        "guidance": guidance_mod,
        "review": review_mod,
        "user": user,
        "conversation_id": conversation_id,
        "first_message": first_message,
        "tmp_path": tmp_path,
    }


def _model_payload(message_id=None, count=1):
    proposals = []
    for index in range(count):
        proposals.append(
            {
                "proposal_type": "addition",
                "proposal_text": f"Frame uploaded files as uploaded sources, not runtime truth {index}.",
                "rationale": "The conversation corrected source framing behavior.",
                "source_experience_summary": "The user corrected how uploaded files should be described.",
                "source_message_id": message_id,
                "risk_if_added": "May underweight a legitimate uploaded source.",
                "risk_if_not_added": "The entity may overstate uploaded source authority.",
                "metadata": {"topic": "source_framing"},
            }
        )
    return {"proposals": proposals, "no_proposal_reason": None}


def test_dry_run_does_not_write_proposals(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    message_id = review_env["first_message"]["id"]

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(_model_payload(message_id)),
    )

    result = review.generate_behavioral_guidance_review(conversation_id)

    assert len(result["proposals"]) == 1
    assert guidance.list_behavioral_guidance_proposals() == []


def test_write_mode_creates_proposed_records(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    message_id = review_env["first_message"]["id"]

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(_model_payload(message_id)),
    )

    result = review.generate_behavioral_guidance_review(conversation_id, model="test-model")
    created = review.write_behavioral_guidance_review_proposals(result)

    assert len(created) == 1
    proposal = created[0]
    assert proposal["status"] == "proposed"
    assert proposal["source_channel"] == "chat"
    assert proposal["source_conversation_id"] == conversation_id
    assert proposal["source_user_id"] == review_env["user"]["id"]
    assert proposal["source_message_id"] == message_id
    assert proposal["reviewed_by_user_id"] is None
    assert proposal["reviewed_by_role"] is None
    assert proposal["reviewed_at"] is None
    assert proposal["metadata"]["generation_method"] == "conversation_review_v1"
    assert proposal["metadata"]["model"] == "test-model"
    assert len(guidance.list_behavioral_guidance_proposals()) == 1


def test_no_proposals_returned_writes_nothing(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    payload = {"proposals": [], "no_proposal_reason": "No durable guidance warranted."}

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(payload),
    )

    result = review.generate_behavioral_guidance_review(conversation_id)
    created = review.write_behavioral_guidance_review_proposals(result)

    assert result["no_proposal_reason"] == "No durable guidance warranted."
    assert created == []
    assert guidance.list_behavioral_guidance_proposals() == []


def test_malformed_model_json_fails_and_writes_nothing(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: "{not json",
    )

    with pytest.raises(review.BehavioralGuidanceReviewError, match="malformed JSON"):
        review.generate_behavioral_guidance_review(review_env["conversation_id"])

    assert guidance.list_behavioral_guidance_proposals() == []


def test_invalid_proposal_fails_and_writes_nothing(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    payload = {
        "proposals": [
            {
                "proposal_type": "revision",
                "proposal_text": "Revise an unspecified item.",
                "rationale": "No target is supplied.",
            }
        ],
        "no_proposal_reason": None,
    }

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(payload),
    )

    with pytest.raises(review.BehavioralGuidanceReviewError, match="require target"):
        review.generate_behavioral_guidance_review(review_env["conversation_id"])

    assert guidance.list_behavioral_guidance_proposals() == []


def test_more_than_max_proposals_fails_clearly(review_env, monkeypatch):
    review = review_env["review"]
    payload = _model_payload(review_env["first_message"]["id"], count=2)

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(payload),
    )

    with pytest.raises(review.BehavioralGuidanceReviewError, match="max is 1"):
        review.generate_behavioral_guidance_review(
            review_env["conversation_id"],
            max_proposals=1,
        )


def test_source_message_id_must_belong_to_selected_conversation(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    payload = _model_payload("not-in-this-conversation")

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(payload),
    )

    with pytest.raises(review.BehavioralGuidanceReviewError, match="source_message_id"):
        review.generate_behavioral_guidance_review(review_env["conversation_id"])

    assert guidance.list_behavioral_guidance_proposals() == []


def test_behavioral_guidance_file_is_not_read_or_mutated(review_env, monkeypatch):
    review = review_env["review"]
    guidance_file = review_env["tmp_path"] / "BEHAVIORAL_GUIDANCE.md"
    guidance_file.write_text("seed governance file\n", encoding="utf-8")

    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps({"proposals": []}),
    )

    review.generate_behavioral_guidance_review(review_env["conversation_id"])

    assert guidance_file.read_text(encoding="utf-8") == "seed governance file\n"


def _set_conversation_started(db_mod, conversation_id, started_at):
    with db_mod.get_connection() as conn:
        conn.execute(
            "UPDATE main.conversations SET started_at = ? WHERE id = ?",
            (started_at, conversation_id),
        )
        conn.commit()


def _make_conversation(db_mod, user_id, *, started_at, message_count=3):
    conversation_id = db_mod.start_conversation(user_id)
    _set_conversation_started(db_mod, conversation_id, started_at)
    first = None
    for index in range(message_count):
        message = db_mod.save_message(
            conversation_id,
            user_id,
            "user" if index % 2 == 0 else "assistant",
            f"message {index}",
        )
        if first is None:
            first = message
    return conversation_id, first


def test_date_window_selects_expected_conversations(review_env):
    db_mod = review_env["db"]
    review = review_env["review"]
    user_id = review_env["user"]["id"]
    outside_id, _ = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-07T23:59:00+00:00",
    )
    inside_id, _ = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T00:01:00+00:00",
    )

    selected = review.list_conversations_for_guidance_review(
        date_text="2026-05-08",
        max_conversations=10,
    )

    ids = [conversation["id"] for conversation in selected]
    assert inside_id in ids
    assert outside_id not in ids


def test_since_selects_expected_conversations(review_env):
    db_mod = review_env["db"]
    review = review_env["review"]
    user_id = review_env["user"]["id"]
    older_id, _ = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T01:00:00+00:00",
    )
    newer_id, _ = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T02:00:00+00:00",
    )

    selected = review.list_conversations_for_guidance_review(
        since="2026-05-08T01:30:00Z",
        max_conversations=10,
    )

    ids = [conversation["id"] for conversation in selected]
    assert newer_id in ids
    assert older_id not in ids


def test_repeated_conversation_id_selection_is_deduplicated(review_env):
    review = review_env["review"]
    conversation_id = review_env["conversation_id"]

    selected = review.list_conversations_for_guidance_review(
        conversation_ids=[conversation_id, conversation_id],
        max_conversations=10,
    )

    assert [conversation["id"] for conversation in selected] == [conversation_id]


def test_daily_dry_run_writes_nothing(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    message_id = review_env["first_message"]["id"]
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(_model_payload(message_id)),
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[conversation_id],
        write=False,
    )

    assert result["proposal_count"] == 1
    assert result["created_proposal_count"] == 0
    assert guidance.list_behavioral_guidance_proposals() == []


def test_daily_write_mode_creates_proposed_records(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    message_id = review_env["first_message"]["id"]
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(_model_payload(message_id)),
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[conversation_id],
        write=True,
    )

    assert result["proposal_count"] == 1
    assert result["created_proposal_count"] == 1
    proposals = guidance.list_behavioral_guidance_proposals()
    assert len(proposals) == 1
    assert proposals[0]["status"] == "proposed"


def test_daily_review_skips_conversations_below_message_threshold(review_env, monkeypatch):
    db_mod = review_env["db"]
    review = review_env["review"]
    short_id, _ = _make_conversation(
        db_mod,
        review_env["user"]["id"],
        started_at=datetime.now(timezone.utc).isoformat(),
        message_count=2,
    )
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: pytest.fail("model should not be called"),
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[short_id],
        write=False,
    )

    assert result["skipped_conversations"] == 1
    assert result["results"][0]["skip_reason"] == "too_few_messages"


def test_daily_review_enforces_max_conversations(review_env, monkeypatch):
    db_mod = review_env["db"]
    review = review_env["review"]
    user_id = review_env["user"]["id"]
    first_id, first_message = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T01:00:00+00:00",
    )
    second_id, _ = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T02:00:00+00:00",
    )
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(_model_payload(first_message["id"])),
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[first_id, second_id],
        max_conversations=1,
        write=False,
    )

    assert result["selected_conversations"] == 1
    assert result["results"][0]["conversation_id"] == first_id


def test_daily_review_enforces_max_total_proposals(review_env, monkeypatch):
    db_mod = review_env["db"]
    review = review_env["review"]
    user_id = review_env["user"]["id"]
    first_id, first_message = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T01:00:00+00:00",
    )
    second_id, second_message = _make_conversation(
        db_mod,
        user_id,
        started_at="2026-05-08T02:00:00+00:00",
    )

    def fake_model(messages, **kwargs):
        text = str(messages)
        message_id = first_message["id"] if first_id in text else second_message["id"]
        return review.json.dumps(_model_payload(message_id))

    monkeypatch.setattr(review, "chat_completion_json", fake_model)

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[first_id, second_id],
        max_total_proposals=1,
        write=False,
    )

    assert result["proposal_count"] == 1
    assert result["stopped_reason"] == "max_total_proposals_reached"
    assert len(result["results"]) == 1


def test_daily_review_skips_duplicates_by_default(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Existing generated proposal.",
        rationale="Existing review.",
        source_conversation_id=conversation_id,
        source_channel="chat",
        metadata={"generation_method": "conversation_review_v1"},
    )
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: pytest.fail("model should not be called"),
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[conversation_id],
        write=False,
    )

    assert result["skipped_conversations"] == 1
    assert result["results"][0]["skip_reason"] == "duplicate_review_exists"


def test_daily_review_allow_duplicates_permits_rerun(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    conversation_id = review_env["conversation_id"]
    message_id = review_env["first_message"]["id"]
    guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Existing generated proposal.",
        rationale="Existing review.",
        source_conversation_id=conversation_id,
        source_channel="chat",
        metadata={"generation_method": "conversation_review_v1"},
    )
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps(_model_payload(message_id)),
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[conversation_id],
        allow_duplicates=True,
        write=False,
    )

    assert result["reviewed_conversations"] == 1
    assert result["proposal_count"] == 1


def test_daily_review_model_failure_is_reported_without_writes(review_env, monkeypatch):
    review = review_env["review"]
    guidance = review_env["guidance"]
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: "{not json",
    )

    result = review.generate_behavioral_guidance_daily_review(
        conversation_ids=[review_env["conversation_id"]],
        write=True,
    )

    assert result["failed_conversations"] == 1
    assert "malformed JSON" in result["results"][0]["error"]
    assert guidance.list_behavioral_guidance_proposals() == []


def test_daily_review_does_not_read_or_mutate_behavioral_guidance_file(
    review_env,
    monkeypatch,
):
    review = review_env["review"]
    guidance_file = review_env["tmp_path"] / "BEHAVIORAL_GUIDANCE.md"
    guidance_file.write_text("seed governance file\n", encoding="utf-8")
    monkeypatch.setattr(
        review,
        "chat_completion_json",
        lambda *args, **kwargs: review.json.dumps({"proposals": []}),
    )

    review.generate_behavioral_guidance_daily_review(
        conversation_ids=[review_env["conversation_id"]],
        write=False,
    )

    assert guidance_file.read_text(encoding="utf-8") == "seed governance file\n"
