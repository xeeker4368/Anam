import importlib

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
