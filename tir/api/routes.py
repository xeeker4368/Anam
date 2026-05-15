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
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from tir.api.auth import (
    API_SECRET_HEADER,
    is_api_secret_configured,
    is_public_api_path,
    verify_api_secret,
)
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
    get_connection,
    update_user_last_seen,
    save_message,
    start_conversation,
    end_conversation,
    get_conversation,
    get_conversation_messages,
    list_conversations,
)
from tir.memory.retrieval import retrieve
from tir.memory.chunking import checkpoint_conversation, chunk_conversation_final
from tir.engine.context import build_system_prompt_with_debug
from tir.engine.agent_loop import run_agent_loop
from tir.engine.context_budget import (
    AUTO_RETRIEVAL_RESULTS,
    PROMPT_BUDGET_WARNING_CHARS,
    RETRIEVED_CONTEXT_CHAR_BUDGET,
    budget_retrieved_chunks,
)
from tir.engine.context_debug import build_context_debug
from tir.engine.artifact_context import (
    RECENT_ARTIFACT_LIMIT,
    build_recent_artifacts_context,
    has_recent_artifact_intent,
)
from tir.engine.journal_context import (
    PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET,
    build_primary_journal_context,
)
from tir.engine.retrieval_policy import classify_retrieval_policy
from tir.engine.tool_trace_context import build_moltbook_selection_context
from tir.engine.url_prefetch import get_url_prefetch_candidate
from tir.memory.chroma import get_collection_count
from tir.tools.registry import SkillRegistry
from tir.tools.rendering import render_tool_result
from tir.artifacts.service import (
    ArtifactValidationError,
    get_artifact,
    list_artifacts,
)
from tir.artifacts.ingestion import (
    ArtifactIngestionError,
    MAX_INGEST_BYTES,
    ingest_artifact_file,
)
from tir.open_loops.service import (
    OpenLoopValidationError,
    get_open_loop,
    list_open_loops,
)
from tir.ops.status import (
    build_capabilities_status,
    build_memory_status,
    build_system_health,
)
from tir.review.service import (
    ReviewValidationError,
    create_review_item,
    list_review_items,
    update_review_item_status,
)
from tir.behavioral_guidance.service import (
    BehavioralGuidanceValidationError,
    list_behavioral_guidance_proposals,
    update_behavioral_guidance_proposal_status,
)

logger = logging.getLogger(__name__)


def _render_tool_envelope(envelope: dict) -> tuple[bool, str]:
    """Render a registry dispatch envelope for stream/model tool context."""
    if envelope.get("ok"):
        value = envelope.get("value")
        effective_ok = not (isinstance(value, dict) and value.get("ok") is False)
        return effective_ok, render_tool_result(value)

    return False, f"Error: {envelope.get('error', 'unknown tool error')}"

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


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Return the approved upload error envelope for malformed upload requests."""
    if request.url.path == "/api/artifacts/upload":
        return _error_response(400, "Invalid artifact upload request")

    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def api_secret_middleware(request: Request, call_next):
    """Protect non-public API routes with ANAM_API_SECRET when configured."""
    path = request.url.path
    if (
        request.method == "OPTIONS"
        or not path.startswith("/api")
        or is_public_api_path(path)
        or not is_api_secret_configured()
    ):
        return await call_next(request)

    provided = request.headers.get(API_SECRET_HEADER)
    if not verify_api_secret(provided):
        return _error_response(401, "unauthorized")

    return await call_next(request)


@app.on_event("startup")
def startup():
    init_databases()
    app.state.registry = SkillRegistry.from_directory(SKILLS_DIR)
    tool_count = len(app.state.registry.list_tools())
    if not is_api_secret_configured():
        logger.warning("ANAM_API_SECRET is not configured; API routes are unauthenticated.")
    logger.info(f"Tír API started — {tool_count} tools loaded")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    text: str
    conversation_id: str | None = None
    user_id: str | None = None


class ReviewCreateRequest(BaseModel):
    title: str
    description: str | None = None
    category: str = "other"
    priority: str = "normal"
    source_type: str | None = None
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    source_artifact_id: str | None = None
    source_tool_name: str | None = None
    created_by: str = "operator"
    metadata: dict | None = None


class ReviewUpdateRequest(BaseModel):
    status: str


class BehavioralGuidanceProposalUpdateRequest(BaseModel):
    status: str
    reviewed_by_user_id: str | None = None
    reviewed_by_role: str = "admin"
    review_decision_reason: str | None = None


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


def _error_response(status_code: int, error: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": error,
        },
    )


def _validate_artifact_upload_provenance(
    *,
    user_id: str,
    source_conversation_id: str | None,
    source_message_id: str | None,
) -> tuple[str | None, str | None] | JSONResponse:
    """Validate conversation/message provenance for artifact uploads."""
    if source_conversation_id:
        conv = get_conversation(source_conversation_id)
        if conv is None:
            return _error_response(404, "Source conversation not found")
        if conv["user_id"] != user_id:
            return _error_response(403, "Source conversation does not belong to user")

    if source_message_id:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT m.id as message_id,
                          m.conversation_id as conversation_id,
                          c.user_id as user_id
                   FROM main.messages m
                   JOIN main.conversations c ON c.id = m.conversation_id
                   WHERE m.id = ?""",
                (source_message_id,),
            ).fetchone()

        if row is None:
            return _error_response(404, "Source message not found")
        if row["user_id"] != user_id:
            return _error_response(403, "Source message does not belong to user")
        if source_conversation_id and row["conversation_id"] != source_conversation_id:
            return _error_response(
                403,
                "Source message does not belong to source conversation",
            )
        source_conversation_id = source_conversation_id or row["conversation_id"]

    return source_conversation_id, source_message_id


def _validate_artifact_revision_target(
    *,
    user_id: str,
    revision_of: str | None,
) -> str | None | JSONResponse:
    """Validate an optional artifact revision target for uploads."""
    if revision_of is None:
        return None

    normalized = revision_of.strip()
    if not normalized:
        return _error_response(400, "revision_of cannot be empty")

    artifact = get_artifact(normalized)
    if artifact is None:
        return _error_response(404, "Revision artifact not found")

    metadata = artifact.get("metadata") or {}
    artifact_user_id = metadata.get("user_id") if isinstance(metadata, dict) else None
    if artifact_user_id and artifact_user_id != user_id:
        return _error_response(403, "Revision artifact does not belong to user")

    return normalized


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

        supplied_conversation_id = req.conversation_id
        conversation_id = supplied_conversation_id
        conversation_started_reason = "reused"
        user_id = user["id"]
        user_name = user["name"]

        phase_start = time.perf_counter()
        update_user_last_seen(user_id)

        # --- Resolve or create conversation ---
        if conversation_id is None:
            conversation_id = start_conversation(user_id)
            conversation_started_reason = "new_request"
            logger.info(f"Started conversation {conversation_id[:8]} for {user_name}")
        else:
            conv = supplied_conversation
            if conv is None:
                conversation_id = start_conversation(user_id)
                conversation_started_reason = "missing_supplied_conversation"
                logger.warning(f"Conversation not found, started new: {conversation_id[:8]}")
            elif conv.get("ended_at"):
                previous_id = conversation_id
                conversation_id = start_conversation(user_id)
                conversation_started_reason = "ended_supplied_conversation"
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
        retrieval_budget = {
            "input_chunks": 0,
            "included_chunks": 0,
            "skipped_chunks": 0,
            "skipped_empty_chunks": 0,
            "skipped_budget_chunks": 0,
            "truncated_chunks": 0,
            "max_chars": RETRIEVED_CONTEXT_CHAR_BUDGET,
            "used_chars": 0,
        }
        retrieval_policy = classify_retrieval_policy(req.text)
        artifact_intent = has_recent_artifact_intent(req.text)
        retrieval_skipped = (
            _is_greeting(req.text)
            or retrieval_policy["mode"] == "skip_memory"
        )

        if not retrieval_skipped:
            try:
                retrieved_chunks = retrieve(
                    query=req.text,
                    active_conversation_id=conversation_id,
                    max_results=AUTO_RETRIEVAL_RESULTS,
                    artifact_intent=artifact_intent,
                )
                retrieved_chunks, retrieval_budget = budget_retrieved_chunks(
                    retrieved_chunks
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
        system_prompt, prompt_breakdown = build_system_prompt_with_debug(
            user_name=user_name,
            retrieved_chunks=retrieved_chunks,
            tool_descriptions=tool_descriptions,
        )
        prompt_budget_warning = (
            "prompt_chars_over_budget"
            if len(system_prompt) > PROMPT_BUDGET_WARNING_CHARS
            else None
        )
        timings["context_build_ms"] = elapsed_ms(phase_start)

        # --- Conversation history ---
        phase_start = time.perf_counter()
        all_messages = get_conversation_messages(conversation_id)
        history_db_message_count = len(all_messages)
        history_user_message_count = sum(1 for m in all_messages if m["role"] == "user")
        history_assistant_message_count = sum(1 for m in all_messages if m["role"] == "assistant")
        model_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in all_messages
        ]
        conversation_history_chars = sum(
            len(m.get("content") or "")
            for m in model_messages
        )
        current_user_index = next(
            (
                index
                for index, message in enumerate(all_messages)
                if message.get("id") == user_msg["id"]
            ),
            len(model_messages),
        )
        previous_assistant = next(
            (
                message
                for message in reversed(all_messages[:current_user_index])
                if message.get("role") == "assistant"
            ),
            None,
        )
        previous_assistant_chars = (
            len(previous_assistant.get("content") or "")
            if previous_assistant
            else 0
        )
        history_injected_system_message_count = 0
        recent_artifact_context = None
        recent_artifact_context_meta = {
            "included": False,
            "artifact_count": 0,
            "limit": RECENT_ARTIFACT_LIMIT,
            "chars": 0,
            "truncated": False,
        }
        journal_primary_context = None
        journal_primary_context_meta = {
            "included": False,
            "journal_date": None,
            "artifact_id": None,
            "path": None,
            "chars": 0,
            "truncated": False,
            "budget_chars": PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET,
            "reason": "no_journal_date_intent",
            "year_inferred": False,
            "duplicate_count": 0,
        }
        journal_primary_context, journal_primary_context_meta = build_primary_journal_context(
            req.text
        )
        if journal_primary_context:
            model_messages.insert(
                current_user_index,
                {"role": "system", "content": journal_primary_context},
            )
            current_user_index += 1
            history_injected_system_message_count += 1

        if artifact_intent:
            recent_artifact_context, recent_artifact_context_meta = (
                build_recent_artifacts_context(
                    user_id=user_id,
                    limit=RECENT_ARTIFACT_LIMIT,
                )
            )
            if recent_artifact_context:
                model_messages.insert(
                    current_user_index,
                    {"role": "system", "content": recent_artifact_context},
                )
                current_user_index += 1
                history_injected_system_message_count += 1

        moltbook_selection_context = build_moltbook_selection_context(all_messages)
        selection_context_chars = len(moltbook_selection_context or "")
        if moltbook_selection_context:
            model_messages.insert(
                current_user_index,
                {"role": "system", "content": moltbook_selection_context},
            )
            history_injected_system_message_count += 1
        timings["history_load_ms"] = elapsed_ms(phase_start)
        journal_primary_context_chars = len(journal_primary_context or "")
        primary_context_chars = journal_primary_context_chars
        recent_artifact_context_chars = len(recent_artifact_context or "")
        artifact_context_chars = recent_artifact_context_chars
        prompt_breakdown = {
            **prompt_breakdown,
            "conversation_history_chars": conversation_history_chars,
            "journal_primary_context_chars": journal_primary_context_chars,
            "primary_context_chars": primary_context_chars,
            "artifact_context_chars": artifact_context_chars,
            "recent_artifact_context_chars": recent_artifact_context_chars,
            "selection_context_chars": selection_context_chars,
        }
        prompt_breakdown["total_chars"] = (
            prompt_breakdown["system_prompt_chars"]
            + conversation_history_chars
            + primary_context_chars
            + artifact_context_chars
            + selection_context_chars
        )
        prompt_breakdown["other_chars"] = max(0, prompt_breakdown.get("other_chars", 0))
        context_debug = build_context_debug(
            prompt_breakdown=prompt_breakdown,
            retrieval_skipped=retrieval_skipped,
            retrieval_policy=retrieval_policy,
            query=req.text,
            retrieved_chunks=retrieved_chunks,
            retrieval_budget=retrieval_budget,
            primary_context={
                "journal": journal_primary_context_meta,
            },
        )

        # --- Emit debug event ---
        timings["debug_emit_elapsed_ms"] = elapsed_ms(request_start)
        debug_data = {
            "type": "debug",
            "conversation_id": conversation_id,
            "supplied_conversation_id": supplied_conversation_id,
            "effective_conversation_id": conversation_id,
            "conversation_started_reason": conversation_started_reason,
            "user_message_id": user_msg["id"],
            "retrieval_skipped": retrieval_skipped,
            "retrieval_policy": retrieval_policy,
            "artifact_intent": artifact_intent,
            "retrieval_budget": retrieval_budget,
            "chunks_retrieved": len(retrieved_chunks),
            "retrieved_chunks": [
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "text": c.get("text", "")[:300],
                    "vector_distance": c.get("vector_distance"),
                    "vector_rank": c.get("vector_rank"),
                    "bm25_rank": c.get("bm25_rank"),
                    "adjusted_score": c.get("adjusted_score"),
                    "artifact_boost": c.get("artifact_boost"),
                    "artifact_exact_match": c.get("artifact_exact_match"),
                    "artifact_match_field": c.get("artifact_match_field"),
                    "source_type": (
                        c.get("metadata", {}).get("source_type")
                        or c.get("source_type", "unknown")
                    ),
                }
                for c in retrieved_chunks
            ],
            "system_prompt_length": len(system_prompt),
            "prompt_budget_warning": prompt_budget_warning,
            "prompt_breakdown": prompt_breakdown,
            "context_debug": context_debug,
            "journal_primary_context": journal_primary_context_meta,
            "recent_artifact_context": recent_artifact_context_meta,
            "history_db_message_count": history_db_message_count,
            "history_user_message_count": history_user_message_count,
            "history_assistant_message_count": history_assistant_message_count,
            "history_injected_system_message_count": history_injected_system_message_count,
            "model_message_count": len(model_messages),
            "previous_assistant_included": previous_assistant is not None,
            "previous_assistant_chars": previous_assistant_chars,
            "history_message_count": len(model_messages),
            "timings": timings,
        }
        yield json.dumps(debug_data) + "\n"

        # --- Deterministic URL-content prefetch ---
        tool_call_count = 0
        prefetch_tool_trace = []
        url_prefetch_ms = 0.0
        prefetch_url = get_url_prefetch_candidate(req.text)
        if prefetch_url:
            phase_start = time.perf_counter()
            tool_name = "web_fetch"
            tool_args = {"url": prefetch_url}

            yield json.dumps({
                "type": "tool_call",
                "name": tool_name,
                "arguments": tool_args,
            }) + "\n"
            tool_call_count += 1

            if registry is not None and hasattr(registry, "dispatch"):
                envelope = registry.dispatch(tool_name, tool_args)
            else:
                envelope = {
                    "ok": False,
                    "error": "web_fetch tool unavailable",
                }

            effective_ok, rendered = _render_tool_envelope(envelope)
            trace_args = (
                envelope.get("normalized_args", tool_args)
                if envelope.get("ok")
                else tool_args
            )

            yield json.dumps({
                "type": "tool_result",
                "name": tool_name,
                "ok": effective_ok,
                "result": rendered,
            }) + "\n"

            model_messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": tool_name, "arguments": trace_args}}
                ],
            })
            model_messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": rendered,
            })

            prefetch_tool_trace.append({
                "iteration": -1,
                "phase": "url_prefetch",
                "tool_calls": [
                    {"name": tool_name, "arguments": trace_args}
                ],
                "tool_results": [
                    {
                        "tool_name": tool_name,
                        "ok": effective_ok,
                        "rendered": rendered[:500],
                    }
                ],
            })
            url_prefetch_ms = elapsed_ms(phase_start)

        # --- Stream from agent loop ---
        loop_result = None
        agent_loop_start = time.perf_counter()
        first_token_ms = None
        first_token_at = None
        last_token_at = None
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
            combined_tool_trace = prefetch_tool_trace + (loop_result.tool_trace or [])
            if should_persist_assistant and combined_tool_trace:
                tool_trace = json.dumps(combined_tool_trace)
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

        # --- Active conversation checkpointing ---
        phase_start = time.perf_counter()
        if should_persist_assistant:
            try:
                checkpoint_conversation(conversation_id, user_id)
            except Exception as e:
                logger.warning(f"Conversation checkpointing failed: {e}")
        chunking_ms = elapsed_ms(phase_start)

        post_model_timings = {
            "agent_loop_total_ms": agent_loop_total_ms,
            "tool_call_count": tool_call_count,
            "url_prefetch_ms": url_prefetch_ms,
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

@app.post("/api/artifacts/upload")
async def api_upload_artifact(
    file: UploadFile = File(...),
    user_id: str | None = Form(None),
    title: str | None = Form(None),
    description: str | None = Form(None),
    authority: str | None = Form(None),
    origin: str | None = Form(None),
    source_role: str | None = Form(None),
    status: str = Form("active"),
    source_conversation_id: str | None = Form(None),
    source_message_id: str | None = Form(None),
    revision_of: str | None = Form(None),
):
    """Upload a file as an artifact and index it as source material."""
    try:
        user = _resolve_user(user_id)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "User resolution failed"
        return _error_response(exc.status_code, detail)

    provenance = _validate_artifact_upload_provenance(
        user_id=user["id"],
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
    )
    if isinstance(provenance, JSONResponse):
        return provenance
    source_conversation_id, source_message_id = provenance

    revision_target = _validate_artifact_revision_target(
        user_id=user["id"],
        revision_of=revision_of,
    )
    if isinstance(revision_target, JSONResponse):
        return revision_target

    content = await file.read(MAX_INGEST_BYTES + 1)
    await file.close()
    if len(content) > MAX_INGEST_BYTES:
        return _error_response(400, "Uploaded file exceeds 10485760 byte limit")

    try:
        result = ingest_artifact_file(
            filename=file.filename or "",
            content=content,
            user_id=user["id"],
            title=title,
            description=description,
            authority=authority,
            origin=origin,
            source_role=source_role,
            status=status,
            source_conversation_id=source_conversation_id,
            source_message_id=source_message_id,
            revision_of=revision_target,
        )
    except (ArtifactIngestionError, ArtifactValidationError, ValueError) as exc:
        return _error_response(400, str(exc))
    except Exception:
        logger.exception("Artifact upload failed")
        return _error_response(500, "Artifact upload failed")

    return {
        "ok": True,
        "artifact": result["artifact"],
        "file": result["file"],
        "indexing": result["indexing"],
    }


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
# Review queue
# ---------------------------------------------------------------------------

@app.get("/api/review")
def api_list_review_items(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List operator review queue items."""
    try:
        return {
            "ok": True,
            "items": list_review_items(
                status=status,
                category=category,
                priority=priority,
                limit=limit,
                offset=offset,
            ),
        }
    except ReviewValidationError as exc:
        return _error_response(400, str(exc))
    except Exception:
        logger.exception("Review list failed")
        return _error_response(500, "Review list failed")


@app.post("/api/review")
def api_create_review_item(req: ReviewCreateRequest):
    """Create an operator review queue item."""
    try:
        return {
            "ok": True,
            "item": create_review_item(
                title=req.title,
                description=req.description,
                category=req.category,
                priority=req.priority,
                source_type=req.source_type,
                source_conversation_id=req.source_conversation_id,
                source_message_id=req.source_message_id,
                source_artifact_id=req.source_artifact_id,
                source_tool_name=req.source_tool_name,
                created_by=req.created_by,
                metadata=req.metadata,
            ),
        }
    except ReviewValidationError as exc:
        return _error_response(400, str(exc))
    except Exception:
        logger.exception("Review create failed")
        return _error_response(500, "Review create failed")


@app.patch("/api/review/{item_id}")
def api_update_review_item(item_id: str, req: ReviewUpdateRequest):
    """Update only a review queue item's status."""
    try:
        item = update_review_item_status(item_id, req.status)
    except ReviewValidationError as exc:
        return _error_response(400, str(exc))
    except Exception:
        logger.exception("Review update failed")
        return _error_response(500, "Review update failed")

    if item is None:
        return _error_response(404, "Review item not found")

    return {
        "ok": True,
        "item": item,
    }


# ---------------------------------------------------------------------------
# Behavioral guidance proposals
# ---------------------------------------------------------------------------

_BEHAVIORAL_GUIDANCE_REVIEW_STATUSES = {"proposed", "approved", "rejected", "archived"}


@app.get("/api/behavioral-guidance/proposals")
def api_list_behavioral_guidance_proposals(
    status: str | None = None,
    proposal_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List AI-proposed behavioral guidance proposals for admin review."""
    try:
        return {
            "ok": True,
            "proposals": list_behavioral_guidance_proposals(
                status=status,
                proposal_type=proposal_type,
                limit=limit,
                offset=offset,
            ),
        }
    except BehavioralGuidanceValidationError as exc:
        return _error_response(400, str(exc))
    except Exception:
        logger.exception("Behavioral guidance proposal list failed")
        return _error_response(500, "Behavioral guidance proposal list failed")


@app.patch("/api/behavioral-guidance/proposals/{proposal_id}")
def api_update_behavioral_guidance_proposal(
    proposal_id: str,
    req: BehavioralGuidanceProposalUpdateRequest,
):
    """Update behavioral guidance proposal review status only."""
    if req.status not in _BEHAVIORAL_GUIDANCE_REVIEW_STATUSES:
        return _error_response(
            400,
            "Behavioral guidance proposal status is not exposed by this review API",
        )

    try:
        proposal = update_behavioral_guidance_proposal_status(
            proposal_id,
            req.status,
            reviewed_by_user_id=req.reviewed_by_user_id,
            reviewed_by_role=req.reviewed_by_role,
            review_decision_reason=req.review_decision_reason,
        )
    except BehavioralGuidanceValidationError as exc:
        return _error_response(400, str(exc))
    except Exception:
        logger.exception("Behavioral guidance proposal update failed")
        return _error_response(500, "Behavioral guidance proposal update failed")

    if proposal is None:
        return _error_response(404, "Behavioral guidance proposal not found")

    return {
        "ok": True,
        "proposal": proposal,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/system/health")
def api_system_health():
    """Read-only runtime health status."""
    return build_system_health(getattr(app.state, "registry", None))


@app.get("/api/system/memory")
def api_system_memory():
    """Read-only memory integrity status."""
    return build_memory_status()


@app.get("/api/system/capabilities")
def api_system_capabilities():
    """Read-only capability status."""
    return build_capabilities_status(getattr(app.state, "registry", None))


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
