# Remaining Doc Edits — From 2026-04-20 Audit Session

*Precise edit instructions for the six docs not yet updated. Schema v1.4 and User Model v1.1 are already written to disk. Apply these changes in order.*

---

## 1. Task Queue Design v1 → v1.1

**File:** `Tir_Task_Queue_Design_v1.md`

### Change A: Close open question (a)

**Find:**
```
**a. Progress_note accumulation vs. replacement.** Day-one replaces on each yield. If a task yields 3 times, only the last yield's context survives. For long multi-yield tasks, earlier context gets lost. Alternative: append timestamp-prefixed lines so the progress_note grows into a small log. Text field, no schema change; just caller-side behavior. Revisit based on observed usefulness.
```

**Replace with:**
```
**a. Progress_note accumulation vs. replacement.** CLOSED. Append with timestamps. Replacing on yield loses earlier context, violating Principle 6 (never delete, only layer). On each yield, the caller appends a timestamp-prefixed line to progress_note rather than replacing it. The field grows into a small log of the task's history across yield/resume cycles. No schema change — same text field, caller-side behavior only.
```

### Change B: Update field notes for progress_note

**Find:**
```
- **`progress_note`** — updated on yield with a continuation context; updated on completion/abandonment with a final note. Accumulates — if a task yields 3 times, the progress_note is the most recent yield's context (or appended, caller's choice — day-one just replaces).
```

**Replace with:**
```
- **`progress_note`** — updated on yield with a continuation context; updated on completion/abandonment with a final note. Accumulates via append — each yield adds a timestamp-prefixed line so the full history of the task's yield/resume cycles is preserved. Per Principle 6 (never delete, only layer).
```

### Change C: Update close writeback code for yield case

**Find:**
```python
    progress_note = yield_context  # e.g., "Was researching X; still need to check Y"
```

**Replace with:**
```python
    progress_note = (existing_progress_note or "") + f"\n[{iso_now()}] {yield_context}"
```

### Change D: Update cross-references

**Find:** `User Model Design v1` → **Replace with:** `User Model Design v1.1`
**Find:** `Schema Design v1.3` → **Replace with:** `Schema Design v1.4`

### Change E: Update version in footer

**Find:** `*Project Tír Task Queue Design · v1 · April 2026*`
**Replace with:** `*Project Tír Task Queue Design · v1.1 · April 2026*`

---

## 2. Autonomous Chunking Design v1 → v1.1

**File:** `Tir_Autonomous_Chunking_Design_v1.md`

### Change A: Close open question (a)

**Find:**
```
**a. Should autonomous session traces be archive-grade?** Day-one posture says no: the canonical record is ChromaDB chunks + the task row. If a session crashes mid-run, the in-memory trace for the current (not-yet-chunked) window is gone. If that's a real problem — if we want every autonomous second to be as irrecoverable as conversation messages — add an `autonomous_traces` table in archive.db with one row per iteration. Decision defers until we see real behavior.
```

**Replace with:**
```
**a. Should autonomous session traces be archive-grade?** CLOSED. No. Conversations are archive-grade because they contain someone else's input — irreplaceable. Autonomous sessions are task execution — if a crash loses an in-progress trace, the task resets to pending and reruns. Session outputs (journals, research documents) go through document ingestion and get their own persistence. The session trace is process, not product. Archive.db's scope is frozen at two tables (users and messages) and will not be expanded.
```

### Change B: Update the honest trade-off paragraph

**Find:**
```
This is a honest trade-off: autonomous sessions are NOT as archive-protected as conversations. The archive's sacredness (Principle 5) applies fully to conversations, and to session outputs (documents ingested via the document path), but not to the raw session trace itself.

**If that posture is wrong — if we want session traces to be archive-grade** — the fix is to introduce an `autonomous_traces` archive table. Flagged as open question (a).
```

**Replace with:**
```
This is a deliberate design choice: autonomous sessions are NOT archive-protected. The archive's sacredness (Principle 5) applies to conversations (which contain irreplaceable input from other people). Autonomous session traces are process — if lost, the task reruns. Session outputs (documents ingested via the document path) get their own archive-grade persistence through the ingestion pipeline.
```

---

## 3. Conversation Engine Design v1 → v1.1

**File:** `Tir_Conversation_Engine_Design_v1.md`

### Change A: Add `think: false` to ollama_call

**Find:**
```python
def ollama_call(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    host: str,
    model: str = "gemma4",
) -> dict:
    """Call Ollama's /api/chat endpoint with tools support.
    
    Returns a dict with keys:
        "content": str   # the assistant's text content
        "tool_calls": list[dict]  # [] if no tools called
    """
```

**Replace with:**
```python
def ollama_call(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    host: str,
    model: str = "gemma4",
) -> dict:
    """Call Ollama's /api/chat endpoint with tools support.
    
    IMPORTANT: Every request MUST include "think": false in the payload.
    Without it, gemma4:26b generates 800+ reasoning tokens and 40s+
    response times. With it, responses are ~1s with 18 eval tokens.
    This cannot be baked into the Modelfile (verified: Ollama does not
    support think/nothink as a Modelfile parameter as of April 2026).
    
    Returns a dict with keys:
        "content": str         # the assistant's text content (empty string during tool calls)
        "tool_calls": list     # [] if no tools called
    
    Verified Ollama response shape (from gemma4:26b smoke test):
        tool_calls entries have the form:
        {
            "id": "call_xxxx",           # unique call ID
            "function": {
                "index": 0,              # position among multiple calls
                "name": "web_search",    # tool name
                "arguments": {...}       # parsed dict, not a string
            }
        }
    
    When feeding tool results back to the model, use:
        {"role": "tool", "tool_name": "<name>", "content": "<result text>"}
    """
```

### Change B: Close open question (a), move to closed questions

**Find:**
```
**a. Ollama's exact tool-call response shape.** Gemma 4 via Ollama should produce tool_calls similar to OpenAI's format, but the exact structure needs verification against the model + Ollama version actually installed on the M4. Smoke test before full implementation.
```

**Replace with:**
```
**a. Ollama's exact tool-call response shape.** CLOSED. Verified by smoke test (2026-04-19, gemma4:26b, 5/5 clean). Response shape documented in the `ollama_call` docstring above. Key details: tool_calls include an `id` field and `function.index` field; arguments are returned as a parsed dict (not a JSON string); content is empty string during tool calls; the `thinking` field is absent when `think: false` is sent. Tool results feed back as `{"role": "tool", "tool_name": "...", "content": "..."}` per Ollama docs.
```

### Change C: Update open question (c) — remove WAL reference

**Find:**
```
**c. Concurrent turn handling.** Per Autonomous Window v1.1, the worker is single-threaded at the turn level — one turn at a time. Two messages arriving at the same time queue up. The engine itself doesn't enforce this; the worker does. But if the engine is called from two threads concurrently (programming error), what happens? SQLite WAL handles concurrent reads and serializes writes. The engine's operations would mostly just work with some write contention. Not tested, not guaranteed. Document that the engine is single-threaded-per-turn and the caller is responsible.
```

**Replace with:**
```
**c. Concurrent turn handling.** Per Autonomous Window v1.1, the worker is single-threaded at the turn level — one turn at a time. Two messages arriving at the same time queue up. The engine itself doesn't enforce this; the worker does. But if the engine is called from two threads concurrently (programming error), what happens? SQLite with rollback journaling serializes writes via exclusive locks. The engine's operations would mostly just work with some write contention. Not tested, not guaranteed. Document that the engine is single-threaded-per-turn and the caller is responsible.
```

### Change D: Update cross-references

**Find:** `Schema Design v1.3` → **Replace with:** `Schema Design v1.4`

---

## 4. Skill Registry & Dispatch Design v1 → v1.1

**File:** `Tir_Skill_Registry_Design_v1.md`

### Change A: Fix list_tools() to include type wrapper

**Find:**
```python
    def list_tools(self) -> list[dict]:
        """Return tool definitions in the shape the model expects.

        Shape matches Ollama's tools parameter for Gemma 4 function
        calling: a list of {name, description, parameters} dicts.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema,
            }
            for t in self._tools.values()
        ]
```

**Replace with:**
```python
    def list_tools(self) -> list[dict]:
        """Return tool definitions in the shape Ollama expects.

        Shape matches Ollama's tools parameter: a list of
        {"type": "function", "function": {name, description, parameters}}
        dicts. The outer wrapper is required by Ollama's /api/chat endpoint.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.args_schema,
                },
            }
            for t in self._tools.values()
        ]
```

---

## 5. Web Adapter Design v1 → v1.1

**File:** `Tir_Web_Adapter_Design_v1.md`

### Change A: Fix engine_lock to use SharedState and add yield signal

**Find:**
```python
engine_lock = threading.Lock()

@app.post("/message")
def post_message():
    # ... auth, parse ...
    with engine_lock:
        response = engine.handle_conversation_turn(msg, registry, config)
    # ... persist session updates ...
    return response_json
```

**Replace with:**
```python
# engine_lock and yield_signal are part of SharedState, constructed at
# startup and shared between the web adapter and the scheduler thread.
# See Scheduler & Worker Process Design v1 for the full coordination model.

@app.post("/message")
def post_message():
    # ... auth, parse ...
    # Signal autonomous work to yield BEFORE acquiring the lock.
    # Without this, we'd block until the entire autonomous session
    # finishes naturally — potentially minutes instead of seconds.
    shared.yield_signal.set()
    shared.last_chat_activity.update()
    with shared.engine_lock:
        shared.yield_signal.clear()
        response = engine.handle_conversation_turn(msg, registry, config)
    # ... persist session updates ...
    return response_json
```

### Change B: Update the explanation paragraph

**Find:**
```
Crude but correct. For one user this is a non-issue. For multiple users, all their turns go through the one lock — worst case a user waits for another user's turn to complete, which is a tens-of-seconds delay at most. Acceptable for a personal project.
```

**Replace with:**
```
The yield signal is critical: it tells the autonomous agent loop to exit cleanly at the next iteration boundary, releasing the engine lock so the chat turn can proceed. Without it, the web adapter would block on the lock until the entire autonomous session finishes — potentially minutes. With it, the wait is bounded by the longest single tool call (typically seconds, worst case 60s for a web_fetch timeout). See Scheduler & Worker Process Design v1 for the full coordination model including SharedState, yield mechanics, and the scheduler's matching yield-signal handling.
```

---

## 6. Document Ingestion Design v1 → v1.1

**File:** `Tir_Document_Ingestion_Design_v1.md`

### Change A: Update decision 8

**Find:**
```
8. **Documents table stores the extracted text, not raw HTML.** Extraction happens once, at ingestion; the extracted text is the rebuild-safety-net content.
```

**Replace with:**
```
8. **Documents table is metadata only — no content column.** ChromaDB holds the chunks. The documents table stores title, URL, source_type, chunk_count, and processing flags. The URL is preserved so the original source can be re-fetched if re-ingestion is ever needed. Storing extracted text alongside the chunks would be redundant writes for a re-chunking scenario that can be handled by re-fetching.
```

### Change B: Update Step 4 (persist the document)

**Find:**
```sql
INSERT INTO documents (
    id, title, url, source_type, source_trust,
    chunk_count, content, created_at
) VALUES (?, ?, ?, ?, ?, 0, ?, ?);
```

`id` is a fresh UUID. `url` is null for path/content ingests. `chunk_count` is 0 for now — updated after chunking. `content` is the extracted text (not raw HTML; the extraction already happened).

**Replace with:**
```sql
INSERT INTO documents (
    id, title, url, source_type, source_trust,
    chunk_count, created_at
) VALUES (?, ?, ?, ?, ?, 0, ?);
```

`id` is a fresh UUID. `url` is null for path/content ingests. `chunk_count` is 0 for now — updated after chunking. No content column — the documents table is metadata only; ChromaDB holds the actual content as chunks.

### Change C: Clarify Requirement 28 satisfaction

In the "What this design does NOT decide" or "Open questions" section, add or update:

**Add to closed questions or a new "Settled questions" section:**
```
**Requirement 28 (original content preserved alongside chunks).** For URL ingestion, the extracted text lives in ChromaDB as chunks and the source URL is preserved in the documents table for re-fetching. For path-based ingestion, the caller retains the source file. For content-based ingestion, the caller provided the text directly. In all cases, the combination of chunks + source reference satisfies the requirement's intent without storing redundant full text in working.db.
```

---

## Cross-reference updates needed across all remaining docs

Any doc referencing `Schema Design v1.3` should be updated to `Schema Design v1.4`.
Any doc referencing `User Model Design v1` should be updated to `User Model Design v1.1`.

These appear in the cross-references section of each doc. The specific docs affected:
- Conversation Engine (Schema v1.3 → v1.4)
- Skill Registry (Schema v1.3 → v1.4)
- Document Ingestion (Schema v1.3 → v1.4)
- Task Queue (Schema v1.3 → v1.4, User Model v1 → v1.1)
- Autonomous Chunking (Schema v1.3 → v1.4)
- Retrieval Design (Schema v1.3 → v1.4)
- Context Construction (User Model reference)
- Chunking Strategy (Schema reference)

---

*Changes documented · 2026-04-20 · Project Tír*
