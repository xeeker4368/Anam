# CC Task: Web UI Step 1 — Backend API

## What this is

A FastAPI backend that wraps the existing conversation engine with HTTP endpoints and streaming chat responses. This replaces the CLI as the primary way to interact with the entity. The CLI stays for quick testing.

## IMPORTANT: Current file state

The files on this Mac have Phase 2 Step 4 changes (retrieval integration, chunking integration). The zip used to create this spec was from before Step 4. **Do not revert any Phase 2 changes.** This spec only adds to existing files — it does not replace anything.

## Prerequisites

- Phase 2 complete (Steps 1-4 deployed and verified)
- Install new packages: `pip install fastapi uvicorn`

## Files to modify

- `tir/config.py` — add web server config
- `tir/memory/db.py` — add `list_conversations` function
- `tir/engine/ollama.py` — add streaming function

## Files to create

- `tir/api/__init__.py`
- `tir/api/routes.py`
- `run_server.py`

## Changes to `tir/config.py`

Add these lines at the end of the file, after the TIMEZONE line:

```python
# --- Web server ---
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
DEFAULT_USER = "Lyle"
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"
```

## Changes to `tir/memory/db.py`

Add this function after the existing `is_conversation_ended` function and before `save_message`:

```python
def list_conversations(limit: int = 50, offset: int = 0) -> list[dict]:
    """List conversations, most recent first, with summary if available.

    Returns dicts with: id, user_id, user_name, started_at, ended_at,
    message_count, summary.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.user_id, u.name as user_name,
                      c.started_at, c.ended_at, c.message_count,
                      s.content as summary
               FROM main.conversations c
               JOIN main.users u ON c.user_id = u.id
               LEFT JOIN main.summaries s ON c.id = s.conversation_id
               ORDER BY c.started_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
```

## Changes to `tir/engine/ollama.py`

Add `import json` at the top with the existing imports.

Add this function after the existing `chat_completion` function:

```python
def chat_completion_stream(
    system_prompt: str,
    messages: list[dict],
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
):
    """
    Stream chat completion from Ollama, yielding content strings.

    Same parameters as chat_completion, but yields individual tokens
    as they arrive instead of returning the full response.

    Yields:
        str: Individual content tokens from the model.

    Raises:
        requests.RequestException on network/server errors.
    """
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)

    payload = {
        "model": model,
        "messages": api_messages,
        "stream": True,
        "think": False,
    }

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            data = json.loads(line)
            content = data.get("message", {}).get("content", "")
            if content:
                yield content
            if data.get("done", False):
                return
```

## New file: `tir/api/__init__.py`

```python
```

(Empty file — just marks the directory as a package.)

## New file: `tir/api/routes.py`

```python
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
    DEFAULT_USER,
    FRONTEND_DIR,
    OLLAMA_HOST,
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
from tir.engine.ollama import chat_completion_stream
from tir.memory.chroma import get_collection_count

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
    logger.info("Tír API started")


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
        system_prompt = build_system_prompt(
            user_name=user_name,
            retrieved_chunks=retrieved_chunks,
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

        # --- Stream from Ollama ---
        full_content = []
        try:
            for token in chat_completion_stream(
                system_prompt=system_prompt,
                messages=model_messages,
            ):
                full_content.append(token)
                yield json.dumps({"type": "token", "content": token}) + "\n"
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            error_msg = f"Something went wrong when I tried to respond: {e}"
            full_content = [error_msg]
            yield json.dumps({"type": "error", "message": error_msg}) + "\n"

        # --- Save assistant message ---
        assistant_content = "".join(full_content)
        if not assistant_content:
            assistant_content = "I received your message but couldn't generate a response."

        assistant_msg = save_message(
            conversation_id, user_id, "assistant", assistant_content
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
```

## New file: `run_server.py`

```python
#!/usr/bin/env python3
"""
Tír Web Server

Start the FastAPI backend:
    python run_server.py

Options:
    --debug     Enable debug logging and auto-reload
    --port N    Override port (default: 8000)
"""

import argparse
import logging
import uvicorn

from tir.config import WEB_HOST, WEB_PORT


def main():
    parser = argparse.ArgumentParser(description="Tír Web Server")
    parser.add_argument("--debug", action="store_true", help="Debug mode with auto-reload")
    parser.add_argument("--port", type=int, default=WEB_PORT, help=f"Port (default: {WEB_PORT})")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    uvicorn.run(
        "tir.api.routes:app",
        host=WEB_HOST,
        port=args.port,
        reload=args.debug,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
```

## Update `requirements.txt`

Add these to the "Needed now" section:

```
# --- Needed for web UI (current) ---
fastapi
uvicorn
```

## Verify — install dependencies

```bash
cd /path/to/Tir
pip install fastapi uvicorn
```

## Verify — server starts

```bash
cd /path/to/Tir
python run_server.py --debug
```

Should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Tír API started
```

## Verify — health endpoint

In a new terminal:

```bash
curl http://localhost:8000/api/health
```

Should return JSON with ollama status, chunk count, conversation and message counts.

## Verify — users endpoint

```bash
curl http://localhost:8000/api/users
```

Should return the list of users including Lyle.

## Verify — conversations endpoint

```bash
curl http://localhost:8000/api/conversations
```

Should return past conversations (from your test sessions).

## Verify — streaming chat

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, how are you?"}'
```

Should stream back newline-delimited JSON:
1. First line: `{"type": "debug", ...}` with retrieval info
2. Multiple lines: `{"type": "token", "content": "..."}` with individual tokens
3. Last line: `{"type": "done", ...}` with message and conversation IDs

## Verify — conversation close

Using the conversation_id from the streaming response:

```bash
curl -X POST http://localhost:8000/api/conversations/CONVERSATION_ID_HERE/close
```

Should return `{"closed": true, "chunks_saved": N}`.

## What NOT to do

- Do NOT modify `conversation.py`, `context.py`, `chunking.py`, or `retrieval.py`
- Do NOT remove or change Phase 2 Step 4 changes in any file
- Do NOT add authentication — user resolution by name is sufficient for v1
- Do NOT add WebSocket — streaming via newline-delimited JSON over HTTP is simpler and sufficient
- Do NOT create the `frontend/dist` directory — that comes in the next spec
- Do NOT change the existing `chat_completion` function in ollama.py — the new `chat_completion_stream` is added alongside it

## What comes next

After verifying the backend works:
- Step 2: React frontend (chat interface + debug panel + conversation list + dashboard)
