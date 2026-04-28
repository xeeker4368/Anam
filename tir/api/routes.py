"""
Tír API — FastAPI backend

HTTP endpoints wrapping the conversation engine. The streaming chat
endpoint is the primary interface for the web UI.

Endpoints:
    POST /api/chat/stream   — send message, stream response back
    GET  /api/users          — list all users
    GET  /api/conversations  — list conversations with summaries
    GET  /api/conversations/{id}/messages — get messages for a conversation
    POST /api/conversations/{id}/close   — close a conversation
    GET  /api/health         — system health check
"""

import json
import logging

import requests as http_requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tir.config import (
    CONVERSATION_ITERATION_LIMIT,
    DEFAULT_USER,
    FRONTEND_DIR,
    OLLAMA_HOST,
    SKILLS_DIR,
)
from tir.memory.db import (
    init_databases,
    get_user,
    get_user_by_name,
    get_all_users,
    update_user_last_seen,
    save_message,
    start_conversation,
    end_conversation,
    get_conversation,
    get_conversation_messages,
    list_conversations,
)
from tir.memory.retrieval import retrieve
from tir.memory.chunking import maybe_chunk_live, chunk_conversation_final
from tir.engine.context import build_system_prompt
from tir.engine.agent_loop import run_agent_loop
from tir.memory.chroma import get_collection_count
from tir.tools.registry import SkillRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Tír")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_databases()
    app.state.registry = SkillRegistry.from_directory(SKILLS_DIR)
    tool_count = len(app.state.registry.list_tools())
    logger.info(f"Tír API started — {tool_count} tools loaded")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    text: str
    conversation_id: str | None = None
    user_id: str | None = None


# ---------------------------------------------------------------------------
# Greeting detection (matches context.py)
# ---------------------------------------------------------------------------

_GREETING_PATTERNS = {
    "hi", "hello", "hey", "yo", "sup", "hiya", "heya",
    "good morning", "good afternoon", "good evening",
    "morning", "evening", "afternoon",
    "what's up", "whats up", "howdy",
}


def _is_greeting(text: str) -> bool:
    cleaned = text.strip().lower().rstrip("!?.,'\"")
    return cleaned in _GREETING_PATTERNS


# ---------------------------------------------------------------------------
# Resolve user helper
# ---------------------------------------------------------------------------

def _resolve_user(user_id: str | None) -> dict:
    """Resolve user from user_id or fall back to DEFAULT_USER."""
    if user_id:
        user = get_user(user_id)
        if user:
            return user

    user = get_user_by_name(DEFAULT_USER)
    if user:
        return user

    users = get_all_users()
    if users:
        return next((u for u in users if u["role"] == "admin"), users[0])

    raise HTTPException(status_code=500, detail="No users exist")


# ---------------------------------------------------------------------------
# Streaming chat
# ---------------------------------------------------------------------------

@app.post("/api/chat/stream")
def stream_chat(req: ChatRequest):
    """Stream a chat response with debug info.

    Response is newline-delimited JSON:
        {"type": "debug", ...}      — retrieval info, sent first
        {"type": "token", ...}      — individual tokens as they arrive
        {"type": "done", ...}       — final metadata after completion
        {"type": "error", ...}      — if something goes wrong
    """
    user = _resolve_user(req.user_id)

    def generate():
        conversation_id = req.conversation_id
        user_id = user["id"]
        user_name = user["name"]

        update_user_last_seen(user_id)

        # --- Resolve or create conversation ---
        if conversation_id is None:
            conversation_id = start_conversation(user_id)
            logger.info(f"Started conversation {conversation_id[:8]} for {user_name}")
        else:
            conv = get_conversation(conversation_id)
            if conv is None:
                conversation_id = start_conversation(user_id)
                logger.warning(f"Conversation not found, started new: {conversation_id[:8]}")

        # --- Save user message ---
        user_msg = save_message(conversation_id, user_id, "user", req.text)

        # --- Retrieval ---
        retrieved_chunks = []
        retrieval_skipped = _is_greeting(req.text)

        if not retrieval_skipped:
            try:
                retrieved_chunks = retrieve(
                    query=req.text,
                    active_conversation_id=conversation_id,
                )
            except Exception as e:
                logger.warning(f"Retrieval failed: {e}")

        # --- Build system prompt ---
        registry = getattr(app.state, "registry", None)
        tool_descriptions = (
            registry.list_tool_descriptions()
            if registry and registry.has_tools()
            else None
        )
        system_prompt = build_system_prompt(
            user_name=user_name,
            retrieved_chunks=retrieved_chunks,
            tool_descriptions=tool_descriptions,
        )

        # --- Conversation history ---
        all_messages = get_conversation_messages(conversation_id)
        model_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in all_messages
        ]

        # --- Emit debug event ---
        debug_data = {
            "type": "debug",
            "conversation_id": conversation_id,
            "user_message_id": user_msg["id"],
            "retrieval_skipped": retrieval_skipped,
            "chunks_retrieved": len(retrieved_chunks),
            "retrieved_chunks": [
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "text": c.get("text", "")[:300],
                    "vector_distance": c.get("vector_distance"),
                    "vector_rank": c.get("vector_rank"),
                    "bm25_rank": c.get("bm25_rank"),
                    "adjusted_score": c.get("adjusted_score"),
                    "source_type": (
                        c.get("metadata", {}).get("source_type")
                        or c.get("source_type", "unknown")
                    ),
                }
                for c in retrieved_chunks
            ],
            "system_prompt_length": len(system_prompt),
            "history_message_count": len(model_messages),
        }
        yield json.dumps(debug_data) + "\n"

        # --- Stream from agent loop ---
        loop_result = None
        try:
            for event in run_agent_loop(
                system_prompt=system_prompt,
                messages=model_messages,
                registry=registry,
                iteration_limit=CONVERSATION_ITERATION_LIMIT,
                ollama_host=OLLAMA_HOST,
            ):
                event_type = event.get("type")

                if event_type == "token":
                    yield json.dumps({
                        "type": "token",
                        "content": event["content"],
                    }) + "\n"
                elif event_type == "tool_call":
                    yield json.dumps({
                        "type": "tool_call",
                        "name": event["name"],
                        "arguments": event["arguments"],
                    }) + "\n"
                elif event_type == "tool_result":
                    yield json.dumps({
                        "type": "tool_result",
                        "name": event["name"],
                        "ok": event["ok"],
                        "result": event["result"],
                    }) + "\n"
                elif event_type == "done":
                    loop_result = event["result"]
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            error_msg = f"Something went wrong when I tried to respond: {e}"
            loop_result = None
            yield json.dumps({"type": "error", "message": error_msg}) + "\n"

        # --- Save assistant message ---
        tool_trace = None
        if loop_result is None:
            assistant_content = "Something went wrong when I tried to respond."
        elif loop_result.terminated_reason == "complete":
            assistant_content = loop_result.final_content or ""
            if loop_result.tool_trace:
                tool_trace = json.dumps(loop_result.tool_trace)
        elif loop_result.terminated_reason == "iteration_limit":
            assistant_content = "I hit the tool iteration limit before I could finish responding."
            if loop_result.tool_trace:
                tool_trace = json.dumps(loop_result.tool_trace)
            yield json.dumps({"type": "error", "message": assistant_content}) + "\n"
        else:
            assistant_content = (
                "Something went wrong when I tried to respond: "
                f"{loop_result.error or 'unknown error'}"
            )
            if loop_result.tool_trace:
                tool_trace = json.dumps(loop_result.tool_trace)
            yield json.dumps({"type": "error", "message": assistant_content}) + "\n"

        if not assistant_content:
            assistant_content = "I received your message but couldn't generate a response."

        assistant_msg = save_message(
            conversation_id,
            user_id,
            "assistant",
            assistant_content,
            tool_trace=tool_trace,
        )

        # --- Live chunking ---
        try:
            maybe_chunk_live(conversation_id, user_id)
        except Exception as e:
            logger.warning(f"Live chunking failed: {e}")

        # --- Done event ---
        yield json.dumps({
            "type": "done",
            "conversation_id": conversation_id,
            "message_id": assistant_msg["id"],
        }) + "\n"

    return StreamingResponse(generate(), media_type="text/plain")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/api/users")
def api_list_users():
    """List all users."""
    return get_all_users()


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@app.get("/api/conversations")
def api_list_conversations(limit: int = 50, offset: int = 0):
    """List conversations, most recent first."""
    return list_conversations(limit=limit, offset=offset)


@app.get("/api/conversations/{conversation_id}/messages")
def api_get_messages(conversation_id: str):
    """Get all messages in a conversation."""
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return get_conversation_messages(conversation_id)


@app.post("/api/conversations/{conversation_id}/close")
def api_close_conversation(conversation_id: str):
    """Close a conversation and run final chunking."""
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.get("ended_at"):
        return {"closed": True, "chunks_saved": 0, "already_closed": True}

    end_conversation(conversation_id)

    chunks_saved = 0
    try:
        chunks_saved = chunk_conversation_final(conversation_id, conv["user_id"])
    except Exception as e:
        logger.warning(f"Final chunking failed: {e}")

    return {"closed": True, "chunks_saved": chunks_saved}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def api_health():
    """System health check."""
    # Ollama
    try:
        resp = http_requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        ollama_status = "ok" if resp.status_code == 200 else "error"
    except Exception:
        ollama_status = "unreachable"

    # ChromaDB
    try:
        chunk_count = get_collection_count()
    except Exception:
        chunk_count = -1

    # Database stats
    from tir.memory.db import get_connection
    try:
        with get_connection() as conn:
            conv_count = conn.execute(
                "SELECT COUNT(*) FROM main.conversations"
            ).fetchone()[0]
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM main.messages"
            ).fetchone()[0]
    except Exception:
        conv_count = -1
        msg_count = -1

    return {
        "ollama": ollama_status,
        "chromadb_chunks": chunk_count,
        "conversations": conv_count,
        "messages": msg_count,
    }


# ---------------------------------------------------------------------------
# Static file serving (production — after frontend is built)
# ---------------------------------------------------------------------------

import os

if os.path.exists(str(FRONTEND_DIR)):
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
