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
import time

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
from tir.artifacts.service import (
    ArtifactValidationError,
    get_artifact,
    list_artifacts,
)
from tir.open_loops.service import (
    OpenLoopValidationError,
    get_open_loop,
    list_open_loops,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Tír")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],  # Vite dev server
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
        raise HTTPException(status_code=404, detail="User not found")

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
    supplied_conversation = (
        get_conversation(req.conversation_id)
        if req.conversation_id is not None
        else None
    )
    if supplied_conversation and supplied_conversation["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Conversation does not belong to user")

    def generate():
        request_start = time.perf_counter()
        timings = {}

        def elapsed_ms(start: float, end: float | None = None) -> float:
            if end is None:
                end = time.perf_counter()
            return round((end - start) * 1000, 2)

        conversation_id = req.conversation_id
        user_id = user["id"]
        user_name = user["name"]

        phase_start = time.perf_counter()
        update_user_last_seen(user_id)

        # --- Resolve or create conversation ---
        if conversation_id is None:
            conversation_id = start_conversation(user_id)
            logger.info(f"Started conversation {conversation_id[:8]} for {user_name}")
        else:
            conv = supplied_conversation
            if conv is None:
                conversation_id = start_conversation(user_id)
                logger.warning(f"Conversation not found, started new: {conversation_id[:8]}")
            elif conv.get("ended_at"):
                previous_id = conversation_id
                conversation_id = start_conversation(user_id)
                logger.info(
                    "Conversation %s was ended; started new conversation %s for %s",
                    previous_id[:8],
                    conversation_id[:8],
                    user_name,
                )
        timings["resolve_conversation_ms"] = elapsed_ms(phase_start)

        # --- Save user message ---
        phase_start = time.perf_counter()
        user_msg = save_message(conversation_id, user_id, "user", req.text)
        timings["save_user_message_ms"] = elapsed_ms(phase_start)

        # --- Retrieval ---
        phase_start = time.perf_counter()
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
        timings["retrieval_ms"] = elapsed_ms(phase_start)

        # --- Build system prompt ---
        phase_start = time.perf_counter()
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
        timings["context_build_ms"] = elapsed_ms(phase_start)

        # --- Conversation history ---
        phase_start = time.perf_counter()
        all_messages = get_conversation_messages(conversation_id)
        model_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in all_messages
        ]
        timings["history_load_ms"] = elapsed_ms(phase_start)

        # --- Emit debug event ---
        timings["debug_emit_elapsed_ms"] = elapsed_ms(request_start)
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
            "timings": timings,
        }
        yield json.dumps(debug_data) + "\n"

        # --- Stream from agent loop ---
        loop_result = None
        agent_loop_start = time.perf_counter()
        first_token_ms = None
        first_token_at = None
        last_token_at = None
        tool_call_count = 0
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
                    token_at = time.perf_counter()
                    if first_token_at is None:
                        first_token_at = token_at
                        first_token_ms = elapsed_ms(request_start, token_at)
                    last_token_at = token_at
                    yield json.dumps({
                        "type": "token",
                        "content": event["content"],
                    }) + "\n"
                elif event_type == "tool_call":
                    tool_call_count += 1
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
        agent_loop_total_ms = elapsed_ms(agent_loop_start)

        # --- Save assistant message ---
        tool_trace = None
        assistant_msg = None
        assistant_content = ""
        should_persist_assistant = False
        if loop_result is None:
            pass
        elif loop_result.terminated_reason == "complete":
            assistant_content = loop_result.final_content or ""
            should_persist_assistant = bool(assistant_content.strip())
            if should_persist_assistant and loop_result.tool_trace:
                tool_trace = json.dumps(loop_result.tool_trace)
            elif not should_persist_assistant:
                empty_message = "I received your message but couldn't generate a response."
                logger.warning("Agent loop completed with empty assistant content")
                yield json.dumps({"type": "error", "message": empty_message}) + "\n"
        elif loop_result.terminated_reason == "iteration_limit":
            error_message = "I hit the tool iteration limit before I could finish responding."
            yield json.dumps({"type": "error", "message": error_message}) + "\n"
        else:
            error_message = (
                "Something went wrong when I tried to respond: "
                f"{loop_result.error or 'unknown error'}"
            )
            yield json.dumps({"type": "error", "message": error_message}) + "\n"

        if should_persist_assistant:
            phase_start = time.perf_counter()
            assistant_msg = save_message(
                conversation_id,
                user_id,
                "assistant",
                assistant_content,
                tool_trace=tool_trace,
            )
            save_assistant_message_ms = elapsed_ms(phase_start)
        else:
            save_assistant_message_ms = 0.0

        # --- Live chunking ---
        phase_start = time.perf_counter()
        if should_persist_assistant:
            try:
                maybe_chunk_live(conversation_id, user_id)
            except Exception as e:
                logger.warning(f"Live chunking failed: {e}")
        chunking_ms = elapsed_ms(phase_start)

        post_model_timings = {
            "agent_loop_total_ms": agent_loop_total_ms,
            "tool_call_count": tool_call_count,
            "save_assistant_message_ms": save_assistant_message_ms,
            "chunking_ms": chunking_ms,
            "total_backend_ms": elapsed_ms(request_start),
        }
        if first_token_ms is not None:
            post_model_timings["first_token_ms"] = first_token_ms
        if first_token_at is not None and last_token_at is not None:
            post_model_timings["model_stream_ms"] = elapsed_ms(first_token_at, last_token_at)
        else:
            post_model_timings["model_total_ms"] = agent_loop_total_ms
        if loop_result is not None:
            post_model_timings["tool_loop_iterations"] = loop_result.iterations

        yield json.dumps({
            "type": "debug_update",
            "timings": post_model_timings,
        }) + "\n"

        # --- Done event ---
        yield json.dumps({
            "type": "done",
            "conversation_id": conversation_id,
            "message_id": assistant_msg["id"] if assistant_msg else None,
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
# Artifacts
# ---------------------------------------------------------------------------

@app.get("/api/artifacts")
def api_list_artifacts(
    artifact_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List artifact metadata records."""
    try:
        return list_artifacts(
            artifact_type=artifact_type,
            status=status,
            limit=limit,
            offset=offset,
        )
    except ArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/artifacts/{artifact_id}")
def api_get_artifact(artifact_id: str):
    """Get artifact metadata without reading workspace file contents."""
    artifact = get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


# ---------------------------------------------------------------------------
# Open loops
# ---------------------------------------------------------------------------

@app.get("/api/open-loops")
def api_list_open_loops(
    status: str | None = None,
    loop_type: str | None = None,
    priority: str | None = None,
    related_artifact_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List open-loop metadata records."""
    try:
        return list_open_loops(
            status=status,
            loop_type=loop_type,
            priority=priority,
            related_artifact_id=related_artifact_id,
            limit=limit,
            offset=offset,
        )
    except OpenLoopValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/open-loops/{open_loop_id}")
def api_get_open_loop(open_loop_id: str):
    """Get open-loop metadata by id."""
    open_loop = get_open_loop(open_loop_id)
    if not open_loop:
        raise HTTPException(status_code=404, detail="Open loop not found")
    return open_loop


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
