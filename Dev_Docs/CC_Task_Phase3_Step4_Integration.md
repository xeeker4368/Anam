# CC Task: Phase 3 Step 4 — Integration

## What this is

Wire the agent loop and skill registry into `routes.py` so the entity actually uses tools through the web UI. After this step, she can call `memory_search` (and any future tools) during a conversation.

This replaces the current direct-streaming-from-Ollama pattern with the agent loop. The agent loop streams text tokens exactly like before for normal responses, but now it also handles tool-calling iterations when the model decides to use a tool.

## Prerequisites

- Phase 3 Step 2 complete (Agent Loop)
- Phase 3 Step 3 complete (Memory Search Skill deployed)

## Read before writing

Read these files first — you are modifying them:

- `tir/api/routes.py` — the streaming handler (main changes)
- `tir/engine/context.py` — `build_system_prompt` (pass tool descriptions)
- `tir/config.py` — constants you need

Read these files for reference — do NOT modify them:

- `tir/engine/agent_loop.py` — the loop you're calling
- `tir/tools/registry.py` — the registry you're loading
- `tir/memory/db.py` — `save_message` (already accepts `tool_trace`)

## Files to modify

```
tir/
    api/
        routes.py       ← MODIFY (main changes)
```

No new files.

---

## Modify: `tir/api/routes.py`

### 1. Add imports

Add these to the existing imports at the top:

```python
from tir.config import SKILLS_DIR, CONVERSATION_ITERATION_LIMIT
from tir.tools.registry import SkillRegistry
from tir.engine.agent_loop import run_agent_loop
```

### 2. Load registry at startup

Modify the existing `startup()` function:

```python
@app.on_event("startup")
def startup():
    init_databases()
    app.state.registry = SkillRegistry.from_directory(str(SKILLS_DIR))
    logger.info(
        f"Tír API started — {len(app.state.registry._tools)} tools loaded"
    )
```

### 3. Replace the streaming handler

Replace the `generate()` inner function inside `stream_chat`. The setup (user resolution, conversation creation, user message save, retrieval) stays the same. What changes is: building the system prompt with tool descriptions, using the agent loop instead of direct Ollama streaming, and saving the tool trace.

Here is the complete replacement for the `generate()` function inside `stream_chat`:

```python
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

        # --- Retrieval (unchanged) ---
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

        # --- Build system prompt WITH tool descriptions ---
        registry = app.state.registry
        tool_descriptions = registry.list_tool_descriptions() if registry.has_tools() else None

        system_prompt = build_system_prompt(
            user_name=user_name,
            retrieved_chunks=retrieved_chunks,
            tool_descriptions=tool_descriptions,
        )

        # --- Conversation history for model ---
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
            "tools_available": len(registry._tools) if registry else 0,
        }
        yield json.dumps(debug_data) + "\n"

        # --- Run agent loop ---
        loop_result = None

        try:
            for event in run_agent_loop(
                system_prompt=system_prompt,
                messages=model_messages,
                registry=registry,
                iteration_limit=CONVERSATION_ITERATION_LIMIT,
                ollama_host=OLLAMA_HOST,
            ):
                if event["type"] == "token":
                    yield json.dumps({
                        "type": "token",
                        "content": event["content"],
                    }) + "\n"

                elif event["type"] == "tool_call":
                    yield json.dumps({
                        "type": "tool_call",
                        "name": event["name"],
                        "arguments": event["arguments"],
                    }) + "\n"

                elif event["type"] == "tool_result":
                    yield json.dumps({
                        "type": "tool_result",
                        "name": event["name"],
                        "ok": event["ok"],
                        "result": event["result"][:500],
                    }) + "\n"

                elif event["type"] == "done":
                    loop_result = event["result"]

        except Exception as e:
            logger.error(f"Agent loop failed: {e}")
            error_msg = f"Something went wrong when I tried to respond: {e}"
            error_assistant = save_message(
                conversation_id, user_id, "assistant", error_msg
            )
            yield json.dumps({"type": "error", "message": error_msg}) + "\n"
            yield json.dumps({
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": error_assistant["id"],
            }) + "\n"
            return

        # --- Determine assistant content ---
        if loop_result is None:
            # Should not happen, but defensive
            assistant_content = "I couldn't generate a response."
        elif loop_result.terminated_reason == "error":
            assistant_content = f"Something went wrong: {loop_result.error}"
        elif loop_result.terminated_reason == "iteration_limit":
            assistant_content = loop_result.final_content or "I used all my tool calls for this turn. Let me know if you'd like me to continue."
        else:
            assistant_content = loop_result.final_content or ""

        if not assistant_content:
            assistant_content = "I received your message but couldn't generate a response."

        # --- Persist tool trace ---
        tool_trace_json = None
        if loop_result and loop_result.tool_trace:
            tool_trace_json = json.dumps(loop_result.tool_trace)

        # --- Save assistant message ---
        assistant_msg = save_message(
            conversation_id, user_id, "assistant", assistant_content,
            tool_trace=tool_trace_json,
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
```

### 4. Remove unused imports

After the replacement, these imports in `routes.py` are no longer needed by the streaming handler:

- `from tir.engine.ollama import chat_completion_stream` — no longer called directly

Keep it if `cli_chat.py` or anything else imports from routes (it doesn't — `cli_chat.py` uses `conversation.py`). If nothing else uses it, remove the import.

### 5. Summary of changes

The only file modified is `routes.py`. The changes are:
1. Three new imports (SkillRegistry, run_agent_loop, config constants)
2. Registry loaded at startup via `app.state.registry`
3. `generate()` inner function rewritten to use agent loop
4. Tool descriptions passed to `build_system_prompt`
5. Tool trace persisted on assistant message via `tool_trace` parameter
6. New event types in NDJSON stream: `tool_call`, `tool_result`
7. Debug event includes `tools_available` count

---

## Verify — server starts with tools loaded

```bash
cd /Users/localadmin/Tir
python run_server.py 2>&1 | head -20
```

Expected: Log line showing "Tír API started — 1 tools loaded" (memory_search).

## Verify — health endpoint works

```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

Expected: Same health output as before (ollama status, chunk count, etc.).

## Verify — chat without tool use works (streaming unchanged)

```bash
curl -s -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello!"}' | head -5
```

Expected: debug event (with `tools_available: 1`), token events, done event. Normal streaming — no tool calls for a greeting.

## Verify — chat with tool use works

```bash
curl -s -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "Can you search your memories for anything about woodworking?"}' \
  | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    event = json.loads(line)
    t = event['type']
    if t == 'debug':
        print(f'DEBUG: {event[\"tools_available\"]} tools, {event[\"chunks_retrieved\"]} chunks retrieved')
    elif t == 'tool_call':
        print(f'TOOL_CALL: {event[\"name\"]}({event[\"arguments\"]})')
    elif t == 'tool_result':
        print(f'TOOL_RESULT: ok={event[\"ok\"]}, {event[\"result\"][:100]}...')
    elif t == 'token':
        print(event['content'], end='', flush=True)
    elif t == 'done':
        print(f'\nDONE: conversation={event[\"conversation_id\"][:8]}')
    elif t == 'error':
        print(f'ERROR: {event[\"message\"]}')
"
```

Expected:
1. DEBUG line showing 1 tool available
2. TOOL_CALL for memory_search with a query about woodworking
3. TOOL_RESULT with ok=True and memory content
4. Streamed text tokens as she responds using the memory results
5. DONE line

If test data has been wiped, the model may or may not call memory_search (automatic retrieval would also return nothing). In that case, have a short conversation first to create retrievable memories, then test.

## Verify — tool trace persisted

After the tool-use chat above:

```bash
cd /Users/localadmin/Tir
python3 -c "
from tir.memory.db import init_databases, get_conversation_messages, list_conversations
init_databases()

# Get the most recent conversation
convos = list_conversations(limit=1)
if convos:
    conv_id = convos[0]['id']
    msgs = get_conversation_messages(conv_id)
    for m in msgs:
        trace = m.get('tool_trace')
        if trace:
            import json
            parsed = json.loads(trace)
            print(f'Message {m[\"id\"][:8]} has tool_trace:')
            for record in parsed:
                for tc in record['tool_calls']:
                    print(f'  Called: {tc[\"name\"]}({tc[\"arguments\"]})')
                for tr in record['tool_results']:
                    print(f'  Result: ok={tr[\"ok\"]}, {tr[\"rendered\"][:100]}')
            print('PASS')
            break
    else:
        print('No messages with tool_trace found')
else:
    print('No conversations found')
"
```

Expected: The assistant message has a `tool_trace` JSON string containing the memory_search call and result.

## Verify — browser test

Open http://localhost:8000 in a browser. Send a message asking her to search her memories. The response should stream as before. Tool call events will appear in the NDJSON stream but the frontend doesn't render them yet (that's Step 5). The response text should reference information from her memories if she called the tool.

Check the debug panel — it should show `tools_available: 1`.

---

## What NOT to do

- Do NOT modify `agent_loop.py` — it's done
- Do NOT modify `ollama.py` — it's done
- Do NOT modify `conversation.py` or `cli_chat.py` — they use the old path and that's fine
- Do NOT modify `context.py` — `build_system_prompt` already accepts `tool_descriptions`
- Do NOT modify `retrieval.py` or `chunking.py` — they're unchanged
- Do NOT modify the frontend — tool call display is Step 5
- Do NOT add authentication or multi-user logic — not in scope

## What comes next

Step 5: Frontend update — render tool_call and tool_result events inline in the chat UI so tool usage is visible to the user.
