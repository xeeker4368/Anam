"""
Tír Conversation Engine

The runtime pipeline that turns a user message into an assistant response.
This is where "the entity" exists as a unified thing — everything below
is infrastructure, everything above is channels.

Phase 1: minimal pipeline.
- Receive message → persist → build context → call model → persist response → return.
- No tools, no retrieval, no agent loop iteration.
- Tools and retrieval plug in here in later phases.
"""

import logging
from dataclasses import dataclass

from tir.memory.db import (
    save_message,
    get_conversation_messages,
    start_conversation,
    get_conversation,
    get_user,
    update_user_last_seen,
)
from tir.engine.context import build_system_prompt
from tir.engine.ollama import chat_completion
from tir.memory.chunking import maybe_chunk_live

logger = logging.getLogger(__name__)


@dataclass
class ConversationResponse:
    """What the engine returns to the adapter."""
    content: str
    conversation_id: str
    message_id: str
    error: bool = False


def handle_turn(
    user_id: str,
    text: str,
    conversation_id: str | None = None,
) -> ConversationResponse:
    """
    Process one conversation turn.

    1. Resolve or create conversation
    2. Persist user message
    3. Build system prompt
    4. Get conversation history
    5. Call the model
    6. Persist assistant message
    7. Return response

    Args:
        user_id: UUID of the user sending the message.
        text: The user's message text.
        conversation_id: Existing conversation to continue, or None to start new.

    Returns:
        ConversationResponse with the assistant's reply.
    """
    # --- Resolve user ---
    user = get_user(user_id)
    if not user:
        return ConversationResponse(
            content="Error: unknown user.",
            conversation_id=conversation_id or "",
            message_id="",
            error=True,
        )

    update_user_last_seen(user_id)

    # --- Resolve or create conversation ---
    if conversation_id is None:
        conversation_id = start_conversation(user_id)
        logger.info(f"Started new conversation {conversation_id} for {user['name']}")
    else:
        conv = get_conversation(conversation_id)
        if conv is None:
            conversation_id = start_conversation(user_id)
            logger.warning(f"Conversation not found, started new: {conversation_id}")

    # --- Persist user message ---
    user_msg = save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="user",
        content=text,
    )
    logger.info(f"Saved user message {user_msg['id']}")

    # --- Build system prompt (now with retrieval) ---
    system_prompt = build_system_prompt(
        user_name=user["name"],
        user_message=text,
        active_conversation_id=conversation_id,
    )

    # --- Get conversation history for model ---
    all_messages = get_conversation_messages(conversation_id)
    model_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in all_messages
    ]

    # --- Call the model ---
    try:
        response = chat_completion(
            system_prompt=system_prompt,
            messages=model_messages,
        )
        assistant_content = response["message"].get("content", "") or ""

        if not assistant_content.strip():
            logger.warning("Empty response from model")
            return ConversationResponse(
                content="I received your message but couldn't generate a response.",
                conversation_id=conversation_id,
                message_id="",
                error=True,
            )

    except Exception as e:
        logger.error(f"Model call failed: {e}")
        assistant_content = f"Something went wrong when I tried to respond: {e}"
        return ConversationResponse(
            content=assistant_content,
            conversation_id=conversation_id,
            message_id="",
            error=True,
        )

    # --- Persist assistant message ---
    assistant_msg = save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="assistant",
        content=assistant_content,
    )
    logger.info(f"Saved assistant message {assistant_msg['id']}")

    # --- Live chunking check ---
    try:
        chunked = maybe_chunk_live(conversation_id, user_id)
        if chunked:
            logger.info(f"Live chunk created for conversation {conversation_id[:8]}")
    except Exception as e:
        logger.warning(f"Live chunking failed (non-fatal): {e}")

    return ConversationResponse(
        content=assistant_content,
        conversation_id=conversation_id,
        message_id=assistant_msg["id"],
    )
