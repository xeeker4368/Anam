from unittest.mock import patch

from tir.engine.conversation import handle_turn


def _fake_user():
    return {"id": "user-1", "name": "Lyle", "role": "admin"}


def _fake_message(role, content, message_id):
    return {
        "id": message_id,
        "conversation_id": "conv-1",
        "role": role,
        "content": content,
        "timestamp": "2026-04-27T12:00:00+00:00",
    }


@patch("tir.engine.conversation.maybe_chunk_live")
@patch("tir.engine.conversation.save_message")
@patch("tir.engine.conversation.chat_completion")
@patch("tir.engine.conversation.get_conversation_messages")
@patch("tir.engine.conversation.build_system_prompt")
@patch("tir.engine.conversation.update_user_last_seen")
@patch("tir.engine.conversation.start_conversation")
@patch("tir.engine.conversation.get_user")
def test_handle_turn_normal_model_content_saves_assistant_message(
    mock_get_user,
    mock_start_conversation,
    mock_update_last_seen,
    mock_build_prompt,
    mock_get_messages,
    mock_chat_completion,
    mock_save_message,
    mock_maybe_chunk_live,
):
    mock_get_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_build_prompt.return_value = "system"
    mock_get_messages.return_value = [_fake_message("user", "Hello", "msg-user")]
    mock_chat_completion.return_value = {"message": {"content": "Hello back"}}
    mock_save_message.side_effect = [
        _fake_message("user", "Hello", "msg-user"),
        _fake_message("assistant", "Hello back", "msg-assistant"),
    ]

    response = handle_turn(user_id="user-1", text="Hello")

    assert response.content == "Hello back"
    assert response.message_id == "msg-assistant"
    assert response.error is False
    assert mock_save_message.call_count == 2
    assert mock_save_message.call_args_list[-1].kwargs["content"] == "Hello back"
    mock_maybe_chunk_live.assert_called_once_with("conv-1", "user-1")


@patch("tir.engine.conversation.maybe_chunk_live")
@patch("tir.engine.conversation.save_message")
@patch("tir.engine.conversation.chat_completion")
@patch("tir.engine.conversation.get_conversation_messages")
@patch("tir.engine.conversation.build_system_prompt")
@patch("tir.engine.conversation.update_user_last_seen")
@patch("tir.engine.conversation.start_conversation")
@patch("tir.engine.conversation.get_user")
def test_handle_turn_model_exception_returns_error_without_assistant_save(
    mock_get_user,
    mock_start_conversation,
    mock_update_last_seen,
    mock_build_prompt,
    mock_get_messages,
    mock_chat_completion,
    mock_save_message,
    mock_maybe_chunk_live,
):
    mock_get_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_build_prompt.return_value = "system"
    mock_get_messages.return_value = [_fake_message("user", "Hello", "msg-user")]
    mock_chat_completion.side_effect = RuntimeError("model unavailable")
    mock_save_message.return_value = _fake_message("user", "Hello", "msg-user")

    response = handle_turn(user_id="user-1", text="Hello")

    assert response.error is True
    assert response.message_id == ""
    assert "Something went wrong when I tried to respond" in response.content
    assert mock_save_message.call_count == 1
    assert mock_save_message.call_args.kwargs["role"] == "user"
    mock_maybe_chunk_live.assert_not_called()


@patch("tir.engine.conversation.maybe_chunk_live")
@patch("tir.engine.conversation.save_message")
@patch("tir.engine.conversation.chat_completion")
@patch("tir.engine.conversation.get_conversation_messages")
@patch("tir.engine.conversation.build_system_prompt")
@patch("tir.engine.conversation.update_user_last_seen")
@patch("tir.engine.conversation.start_conversation")
@patch("tir.engine.conversation.get_user")
def test_handle_turn_empty_model_content_returns_error_without_assistant_save(
    mock_get_user,
    mock_start_conversation,
    mock_update_last_seen,
    mock_build_prompt,
    mock_get_messages,
    mock_chat_completion,
    mock_save_message,
    mock_maybe_chunk_live,
):
    mock_get_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_build_prompt.return_value = "system"
    mock_get_messages.return_value = [_fake_message("user", "Hello", "msg-user")]
    mock_chat_completion.return_value = {"message": {"content": "   "}}
    mock_save_message.return_value = _fake_message("user", "Hello", "msg-user")

    response = handle_turn(user_id="user-1", text="Hello")

    assert response.error is True
    assert response.message_id == ""
    assert "couldn't generate a response" in response.content
    assert mock_save_message.call_count == 1
    assert mock_save_message.call_args.kwargs["role"] == "user"
    mock_maybe_chunk_live.assert_not_called()
