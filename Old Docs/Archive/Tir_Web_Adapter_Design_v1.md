# Project Tír — Web Adapter Design

*Design doc v1, April 2026. The first channel adapter. Accepts HTTP requests, manages user sessions, resolves user identity, translates to `NormalizedMessage`, and invokes the conversation engine. Also serves the minimal web UI for chatting with the entity.*

*Keep-it-simple: Flask, server-side templates, cookie sessions, one user in practice day-one. Structure anticipates additional channels without over-engineering.*

---

## Purpose

The gateway pattern (per Autonomous Window v1.1) keeps channel specifics outside the conversation engine. The web adapter is the first implementation of that pattern — it knows HTTP and cookies and passwords, and translates them into the engine's normalized format.

Its responsibilities:

- Serve the chat UI (login page, conversation view).
- Handle the login flow (POST /login → validate → set session cookie).
- Accept chat messages (POST /message → normalize → engine → respond).
- Decide whether a new message continues the last open conversation or starts a new one.
- Render the conversation history for the UI (past messages in the active conversation).

Non-goals:

- Admin UI (separate surface; potentially just a CLI).
- Multi-device session sync (one browser session is enough day-one).
- Real-time streaming of the model's response (simple POST/response; streaming is deferred).
- Multi-user presence indicators.
- Anything fancy — this is a personal project web UI.

---

## Summary of decisions

1. **Framework: Flask.** Small, synchronous, well-understood. FastAPI's async doesn't buy anything when the engine path is sync.
2. **Server-side templates for the UI** (Jinja2, Flask default). No SPA, no build step, no React, no Tailwind config. HTML + minimal CSS + small JS for message submission.
3. **Cookie-based sessions.** One cookie, long expiry (30 days default). Session maps to user_id in server-side storage.
4. **Session storage: `working.db`.** New table `web_sessions`. No filesystem session files, no in-memory dict that dies on restart.
5. **Resume-or-new policy: resume by default, within 24 hours.** If the user has an open conversation (`ended_at IS NULL`) and its most recent message is less than 24 hours old, continue it. Otherwise start fresh. "New conversation" button overrides.
6. **Password auth via argon2.** Hashed password stored in `channel_identifiers.auth_material` per User Model v1.
7. **No self-signup.** Lyle creates users manually via admin CLI. Login page rejects unknown users.
8. **One adapter process runs alongside the worker.** The same Python process, in fact — adapter and worker share the registry, engine, and config. Simpler deployment and state sharing than separate processes.

---

## Architecture

### Process shape

A single Flask process that:

1. At startup: runs `create_databases`, `init_collection` (ChromaDB), `init_fts`, `startup_recovery` (per Autonomous Window v1.1's close mechanism), loads the skill registry.
2. Starts the Flask HTTP server.
3. Ready to accept requests.

The scheduler (autonomous sessions) and web adapter both run in this same process — the worker IS the Flask process. Autonomous work happens on a background thread or inside scheduled tick handlers. This shape is covered in Scheduler & Worker Process design.

Why single-process: simpler. No IPC, no separate state. Shared registry, shared config, shared connection pool. On a single M4, this is fine.

### Routes

```
GET  /                 → if logged in, chat UI; else redirect to /login
GET  /login            → login form
POST /login            → validate → set session cookie → redirect to /
POST /logout           → clear session → redirect to /login
GET  /conversation     → JSON of the current conversation's messages (for UI rendering)
POST /message          → submit a message → JSON response with the assistant's reply
POST /new              → mark current session as "next message starts a new conversation"
```

Minimal. No conversation-list view for v1 (past conversations are retrievable via the entity's memory; the UI doesn't need to browse them directly).

---

## Session management

### The `web_sessions` table

New table in working.db (schema v1.4 when this lands — or v1.3 addendum):

```sql
CREATE TABLE web_sessions (
    id TEXT PRIMARY KEY,              -- session token (random, URL-safe, 32+ bytes)
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    active_conversation_id TEXT,      -- null until a message has been sent
    force_new_on_next INTEGER DEFAULT 0,  -- set by POST /new
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_web_sessions_user ON web_sessions(user_id);
CREATE INDEX idx_web_sessions_expires ON web_sessions(expires_at);
```

### Session cookie

Name: `tir_session`. Value: the session token (`web_sessions.id`). Attributes: `HttpOnly`, `SameSite=Lax`, `Secure` when served over HTTPS. Expiry 30 days from issuance.

### Session lookup

On every request that requires auth:

1. Read `tir_session` cookie.
2. `SELECT * FROM web_sessions WHERE id = ? AND expires_at > now()`.
3. If found, resolve user via `user_id`, attach to request context.
4. Update `last_seen_at`.
5. If not found, redirect to `/login`.

### Session cleanup

Expired sessions are garbage-collected by a periodic sweep (scheduler-triggered, once a day). Not time-critical.

---

## Login flow

### GET /login

Render a minimal HTML form: username field, password field, submit button. No JS required.

### POST /login

1. Parse form: `username`, `password`.
2. Look up `channel_identifiers WHERE channel = 'web' AND identifier = ?`. If none, render login page with "invalid credentials" error. No distinction between "no such user" and "bad password" (prevents user enumeration).
3. Verify password: `argon2.verify(stored_auth_material, password)`. If mismatch, same error.
4. Create a new session row:
   ```python
   session_id = secrets.token_urlsafe(32)
   INSERT INTO web_sessions (id, user_id, created_at, last_seen_at, expires_at)
   VALUES (?, ?, now(), now(), now() + 30 days)
   ```
5. Set `tir_session` cookie.
6. Redirect to `/`.

### POST /logout

1. Delete the current session row.
2. Clear the cookie.
3. Redirect to `/login`.

### Password hashing

argon2id via the `argon2-cffi` package. Standard parameters. Hashed form stored in `channel_identifiers.auth_material` at user creation time.

Admin CLI includes a `tir admin create-user` command that prompts for a password, hashes it, writes the user row + channel_identifier row + (optional) auth_material.

---

## Conversation resume policy

When the user sends a message, the adapter decides whether to continue an existing conversation or start a new one.

### Resolution order

1. **If session has `force_new_on_next = 1`:** start new. Reset the flag to 0 and generate a fresh `conversation_id`.
2. **If session has `active_conversation_id`:** check whether that conversation is still "fresh":
   - Query its state: `ended_at`, and the timestamp of the most recent message.
   - If `ended_at IS NOT NULL`, it was closed (probably by startup recovery). Start a new conversation.
   - If the most recent message is older than 24 hours, start new.
   - Otherwise, continue it — reuse `active_conversation_id`.
3. **If session has no `active_conversation_id`** (first message since login):
   - Find the most recent open conversation for this user: `SELECT id FROM conversations WHERE user_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1`.
   - If found and fresh (last message < 24 hours old), continue it. Set `active_conversation_id` to its ID.
   - Otherwise, start new.

### Starting new

Start-new means: set `conversation_id = None` when building the `NormalizedMessage`. The engine will generate a new UUID and `save_and_chunk` will create the conversations row.

After the engine returns, update `web_sessions.active_conversation_id` to the engine-returned `conversation_id`.

### POST /new

When the user clicks "New Conversation":

```python
UPDATE web_sessions 
SET force_new_on_next = 1, active_conversation_id = NULL 
WHERE id = ?
```

Returns the refreshed UI (empty conversation view).

### Why 24 hours

Arbitrary but reasonable. A conversation from this morning belongs with what I want to talk about now; a conversation from last week feels like a past episode. 24 hours straddles that intuition for most cases.

Tunable — the value is a config constant, not a schema constant. If behavior in practice suggests 12 hours or 48 hours, adjust.

### Why this matters

Answers the open question from the 04-18 handoff ("web adapter: resume vs. new conversation on reconnect"). It also feeds into the "open conversations accumulate" cosmetic-vs-functional question from Autonomous Window v1.1 — with this resume policy, stale open conversations get naturally superseded by new ones, and startup recovery eventually closes them.

---

## Chat flow

### GET /

Render the chat page:

- Header: user's name, "New Conversation" button, logout link.
- Conversation history: messages from `active_conversation_id` (or empty if none/new).
- Message input: textarea + submit button.

Minimal JS: submit the form via fetch(), append the user's message and the assistant's reply to the DOM, clear the input.

### GET /conversation

Returns JSON:

```json
{
    "conversation_id": "abc-123",
    "messages": [
        {"role": "user", "content": "...", "timestamp": "..."},
        {"role": "assistant", "content": "...", "timestamp": "..."}
    ]
}
```

Queried from working.db's messages table for the session's `active_conversation_id`. Empty list if no active conversation.

Used by the client on initial page load and when the user clicks "New Conversation" (to clear the view).

### POST /message

1. Auth check → session, user.
2. Parse body: `{"text": "..."}`.
3. Resolve `conversation_id` per the resume policy above.
4. Build `NormalizedMessage`:
   ```python
   NormalizedMessage(
       channel="web",
       user_id=user.id,
       conversation_id=conversation_id,  # None if starting new
       text=body["text"],
       timestamp=iso_now(),
   )
   ```
5. Call `engine.handle_conversation_turn(msg, registry, config)`.
6. Receive `EngineResponse`.
7. Update `web_sessions.active_conversation_id` with the returned conversation_id (may be newly-generated).
8. Return JSON:
   ```json
   {
       "status": "ok",
       "conversation_id": "...",
       "message": {
           "role": "assistant",
           "content": "...",
           "timestamp": "..."
       },
       "tool_call_count": 0
   }
   ```

   Error statuses pass through — the UI can render them appropriately.

---

## UI details

### Message input

Single textarea. Enter submits (Shift+Enter for newline). The submit event triggers fetch to POST /message, disables the input while waiting, shows a "thinking" indicator.

No typing indicator from the entity's side (she doesn't stream). The request is just slow; the UI says "...".

### Rendering messages

Markdown-parsed client-side for assistant messages (via a small library like `marked.js`). User messages render as plain text (escaped).

Timestamps are shown on hover or in a subtle style below each message.

Tool call count surfaces minimally — "(used 3 tools)" below the assistant message if `tool_call_count > 0`. Clicking reveals a panel with tool names and brief summaries. Optional; can skip for v1 if it feels like clutter.

### Errors

If `status != "ok"`, render the error text in a distinct style (red border, italic, whatever) with a "Retry" action that re-submits the same message.

### New Conversation button

Prominent in the header. Click → POST /new → reload conversation view (empty).

### Login page

Plain HTML form. No CSS framework. Maybe 20 lines of custom CSS for legibility. Not a product, a tool.

---

## Running the server

Development: `flask run` with debug mode. Production: probably the same since this is a personal project running locally on the M4. If it ever gets exposed to the network, switch to gunicorn or similar, add HTTPS via a reverse proxy.

Host binding default: `127.0.0.1` (localhost only). If Lyle wants to access from his iPhone on the same network, bind to `0.0.0.0` and use the M4's LAN IP. Configuration.

Port default: `5050` (Flask's common dev port plus a tweak to avoid collision with 5000/other Apple services on macOS).

---

## Integration with the worker process

Per the single-process decision, the Flask app IS the worker process. Shared state:

- **Registry.** Loaded once at startup, used by every engine call. Flask stores on `app.config` or a global module-level variable.
- **EngineConfig.** Same — loaded once, referenced on every request.
- **Scheduler.** Runs on a background thread inside the Flask process. See Scheduler & Worker Process design.

Concurrent requests: Flask's default is one-thread-per-request (with a request pool). Multiple simultaneous chat messages would hit the engine concurrently. Per Autonomous Window v1.1, conversations are serialized at the turn level. The engine itself doesn't enforce this; a lock at the web-adapter layer around the engine call serializes turns:

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

The yield signal is critical: it tells the autonomous agent loop to exit cleanly at the next iteration boundary, releasing the engine lock so the chat turn can proceed. Without it, the web adapter would block on the lock until the entire autonomous session finishes — potentially minutes. With it, the wait is bounded by the longest single tool call (typically seconds, worst case 60s for a web_fetch timeout). See Scheduler & Worker Process Design v1 for the full coordination model including SharedState, yield mechanics, and the scheduler's matching yield-signal handling.

Finer-grained locking (per-conversation or per-user) is a future optimization if it matters.

---

## Autonomous work interaction

The scheduler may start an autonomous session while the web adapter is idle. Per Autonomous Window v1.1, the scheduler sets the engine's yield signal when a chat message arrives, and the autonomous session yields after its current tool call.

The web adapter's POST /message path:

1. Acquires the engine lock (blocks autonomous work's next iteration).
2. Waits for autonomous work to complete its current tool call (up to ~30s in practice).
3. Runs the chat turn.

This is handled entirely within the engine lock + the autonomous loop's yield check. Web adapter doesn't need special autonomous-aware code.

---

## Security

### Threat model for v1

- Personal project on localhost.
- One actual user (Lyle).
- No network exposure by default.

The threat model is "accidental misuse" more than "adversarial attack." Nonetheless, basic hygiene:

- HttpOnly cookies (no XSS token theft even if markdown rendering misbehaves).
- Argon2id for password hashing.
- SameSite=Lax on cookies (CSRF mitigation; explicit CSRF tokens not needed at this scale).
- Secrets: Flask's secret_key is a randomly-generated value stored in a local config file not checked into git.

### If exposure ever happens

Add HTTPS (reverse proxy is fine), rate limiting on /login, CSRF tokens on state-changing POSTs, proper log review for authentication failures. All straightforward extensions; not day-one.

---

## What this design does NOT decide

- **Admin UI.** Creating users, approving skills, reviewing logs — probably a CLI or direct DB manipulation day-one. Not this adapter's concern.
- **Conversation-list navigation.** Viewing past conversations in the UI. Day-one has no navigation; past conversations surface via the entity's memory when relevant. If Lyle wants UI navigation later, add routes + templates.
- **Settings UI.** No user-editable settings in v1. Model choice, resume timeout, etc. are config files Lyle edits directly.
- **Notifications.** No push, no SSE, no WebSocket. If she wants to reach out proactively (autonomous insight worth sharing), the pattern isn't designed yet.
- **Multi-tab coherence.** If Lyle opens the chat in two browser tabs simultaneously, both show the same conversation (backed by the same session row + active_conversation_id). Messages from either tab append to the same conversation. Both tabs update when the other posts — maybe. If the second tab doesn't auto-refresh, the user reloads. Acceptable for day-one.
- **File upload / attachments.** Text-only chat v1. Document ingestion has its own path (via tools); the chat input doesn't accept files directly.

---

## Open questions

**a. Password reset.** If Lyle forgets his password, what's the recovery path? Day-one: direct DB manipulation (admin CLI to reset password). No email recovery, no recovery codes. Acceptable for personal use.

**b. Multiple concurrent devices.** Lyle might use his MacBook and his iPhone at the same time, both logged in, both sending messages. The session rows are independent (two sessions for the same user). Messages from both go to the same `active_conversation_id` potentially. Turn-level locking handles ordering. UI consistency across devices isn't guaranteed (one device won't see the other's messages until it refreshes). Acceptable.

**c. Schema bump for `web_sessions`.** This adds a table. Schema goes to v1.4 or gets a separate Schema Adapter Addendum. Likely v1.4 is cleaner.

**d. The 24-hour resume threshold.** Guess. Watch behavior. If Lyle often says "that conversation was old, why did it resume," shorten. If he says "why did I lose my thread," lengthen.

**e. Message ID generation on the client.** The client could include a client-generated message ID (UUID) in POST /message to enable idempotency (detect and dedupe double-submit). Day-one doesn't bother. If we see duplicate-message issues in practice, add.

**f. UI framework choice.** Plain HTML + vanilla JS is proposed. If Lyle wants something fancier, we can swap in HTMX or a light SSR + JS flavor later. But a Tír-specific React app is over-engineering.

**g. WebSocket for incoming autonomous messages.** If she ever wants to send unsolicited messages to an active browser session ("hey, I found something interesting while you were away"), SSE or WebSocket is the path. Deferred; not part of v1's outbound-only-in-response-to-input model.

---

## Cross-references

- **Autonomous Window Design v1.1** — gateway pattern (adapter → normalized message → engine); single-worker turn serialization.
- **User Model Design v1.1** — channel_identifiers table used for web auth; role-based distinction (admin vs. user) enforced at UI layer.
- **Conversation Engine Design v1.1** — what the adapter calls; what EngineResponse looks like.
- **Schema Design v1.4** — session table lives in working.db.
- **Guiding Principles v1.1** — Principle 9 (the adapter is infrastructure; the entity never sees HTTP or cookies), Principle 13 (configuration chosen to be explainable — 24-hour resume threshold, argon2id, HttpOnly cookies).

---

*Project Tír Web Adapter Design · v1 · April 2026*
