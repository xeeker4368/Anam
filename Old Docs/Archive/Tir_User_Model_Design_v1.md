# Project Tír — User Model Design

*Draft v1, April 2026. How users exist in the system, how their identity gets established, and how channel identifiers map to people. Covers the users table, channel identifier resolution, authentication, and roles.*

---

## Purpose

The memory layer assumes every conversation carries a `user_id`. The context construction system uses that ID to frame retrieved memories ("[Conversation with Lyle on...]"). The schema puts `user_id` on messages and conversations as required fields. None of that works without a clear model of what a user *is* and how they get created.

This document specifies that model for v1.

---

## v1 scope

**What v1 includes:**

- A small closed set of pre-registered users (Lyle plus a handful of people he manually adds).
- One person = one user row, even if that person reaches the entity through multiple channels.
- Channel identifiers (web account, iMessage phone number, etc.) attach to users as a separate concept.
- Role-based authorization with two roles: `admin` and `user`. Lyle is admin.
- Authentication: password/token on web UI, channel-trust for messaging channels.
- Manual user creation only — no self-signup, no automatic creation from unknown identifiers.

**What v1 explicitly defers:**

- Self-service user creation.
- Automatic channel-identifier attachment ("this phone number claims to be Lyle — verify").
- Role granularity beyond admin/user.
- Per-user privacy rules enforced by the system.
- Session management details for the web UI (specific token lifetime, refresh flow, etc.).

---

## Core concept: people vs. channels

The most important distinction in this design: a **user** is a person; a **channel identifier** is a way that person reaches the entity.

One person can have multiple channel identifiers. Lyle might have a web account (username/password) and an iMessage phone number and later a Discord handle. All three point to the same user row. When the entity retrieves memories, they surface regardless of which channel the original conversation happened on — because it's the same person, and she has one experience of talking to that person.

This matters for Principle 7 (retrieval determines intelligence) and Principle 4 (context is mandatory). If channels were separate users, her memory of "talking to Lyle" would fragment across them, and retrieval against "what Lyle said about X" could miss the half of the conversation that happened on iMessage.

---

## Schema: two tables

### users

The person. This is what `user_id` on messages and conversations references.

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,            -- UUID. Generated once, never changes.
    name TEXT NOT NULL,              -- Display name. "Lyle", "Sarah", "AgentX".
    role TEXT NOT NULL DEFAULT 'user',  -- 'admin' or 'user'.
    created_at TEXT NOT NULL,        -- ISO 8601 UTC.
    last_seen_at TEXT                -- Updated each time the user starts a conversation.
);

CREATE INDEX idx_users_role ON users(role);
```

**Field notes:**

- `name` is what the entity sees in retrieval framing. It's the display name, not a username or login. A user's `name` can be updated through admin actions (e.g., if someone wants to be called differently). Updates don't break anything because `id` is the stable reference.
- `role` defaults to `'user'`. Lyle's row has `'admin'`. This is the whole authorization model — there is no permission matrix, no per-resource grants. Admin or not.
- `last_seen_at` is UI convenience. Not critical for the entity's operation.

**Mirrored in the archive.** Per the existing schema design, `users` also exists in `archive.db` with the minimal fields (`id`, `name`, `created_at`). The archive version is what gets rebuilt from if the working store is lost. `role` and `last_seen_at` are operational state and live only in the working store.

### channel_identifiers

How a user reaches the entity. One row per channel identifier; a user can have many.

```sql
CREATE TABLE channel_identifiers (
    id TEXT PRIMARY KEY,            -- UUID.
    user_id TEXT NOT NULL,           -- FK to users.id.
    channel TEXT NOT NULL,           -- 'web', 'imessage', 'discord', etc.
    identifier TEXT NOT NULL,        -- Channel-specific identifier (username, phone number, handle).
    auth_material TEXT,              -- Channel-specific auth data. See below.
    verified INTEGER DEFAULT 0,      -- 1 when this identifier is confirmed to belong to the user.
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (channel, identifier)     -- Same identifier can't attach to two users on the same channel.
);

CREATE INDEX idx_channel_identifiers_user ON channel_identifiers(user_id);
CREATE INDEX idx_channel_identifiers_lookup ON channel_identifiers(channel, identifier);
```

**Field notes:**

- `(channel, identifier)` is the key the adapter uses to resolve an incoming message. Web adapter receives a logged-in session, resolves to `(web, username)`, looks up the user. iMessage adapter receives a message, resolves to `(imessage, phone_number)`, looks up the user.
- `auth_material` is channel-specific. For web, this is a hashed password or a hashed token. For iMessage, it's `NULL` (channel-trust — if iMessage delivered the message, the phone number is trusted). Format and contents are the channel adapter's concern, not the core schema's.
- `verified` matters when an identifier is added through a lower-trust path. Day-one, Lyle creates all identifiers manually, so `verified = 1` for all of them. The field exists so self-service additions (deferred) can land as `verified = 0` and get promoted later.
- `UNIQUE (channel, identifier)` prevents the same phone number from being attached to two users. Also means when Lyle creates a new user, the admin UI needs to check for conflicts — which is correct behavior.

**Not in the archive.** Channel identifiers are operational. If the working store is rebuilt from the archive, channel identifiers would need to be re-entered manually. That's acceptable — they're a small set, manually managed, and rebuilding them is part of the recovery process. The archive's only job is preserving conversation data.

---

## How an incoming message resolves to a user

The gateway pattern (from the Autonomous Window design) has each channel adapter translating channel-specific events into a normalized message format. User resolution happens inside the adapter, before the message gets passed to the conversation engine.

### Web adapter

1. Request arrives with a session token (cookie, header, whatever).
2. Adapter validates the token against its auth store. If invalid → 401, stop.
3. Valid token resolves to a `(web, username)` pair.
4. Adapter queries `channel_identifiers` for that pair, gets the `user_id`.
5. Adapter queries `users` to get the user's `name` and `role`.
6. Adapter builds the normalized message with `user_id` attached and passes it to the conversation engine.

If step 4 finds no match (user was deleted, identifier was rotated), the adapter returns an auth error. The engine never sees unmatched identifiers.

### iMessage adapter (future)

1. iMessage event arrives with a phone number (or email) as the sender.
2. Adapter looks up `channel_identifiers` on `(imessage, phone_number)`.
3. If found → resolves to user, builds normalized message with `user_id`, passes to engine.
4. If not found → message is rejected. The entity does not receive unknown-sender messages day-one.

**This rejection is deliberate.** Channel-trust means trusting that the channel correctly identifies the sender. It does not mean accepting messages from anyone the channel delivers. The entity only talks to pre-registered people. Unknown senders get a polite auto-reply (handled by the adapter, not the entity) or are silently dropped, depending on channel conventions.

### Normalized message format (updated)

From the Autonomous Window design, the normalized message format was:

```python
{
    "channel": str,
    "user_id": str,
    "text": str,
    "timestamp": str,
}
```

That's unchanged. `user_id` is the resolved UUID — the adapter does the lookup; the engine receives the answer.

---

## User creation (day-one)

Manual only. No self-signup.

### Admin creates a user

Through an admin interface (CLI, web admin UI, direct DB manipulation — Lyle's choice, not design-critical):

1. Provide a display name.
2. Role (defaults to `user`, can be set to `admin`).
3. Create the user row, generate a UUID.
4. Optionally add initial channel identifiers:
   - For web: username + password (hashed and stored in `auth_material`).
   - For iMessage: phone number, `auth_material = NULL`, `verified = 1`.
5. Mirror the user row to `archive.db`.

### Admin adds a channel identifier to an existing user

Through the same admin interface:

1. Pick the user.
2. Specify channel + identifier + auth material as applicable.
3. Insert into `channel_identifiers` with `verified = 1`.

**That's it.** No email verification, no device confirmation, no OTP flow. The admin asserting the identifier is correct is the verification. This is acceptable because the user set is small and closed; the admin knows who these people are.

### What the entity experiences when a new user appears

Nothing automatic. The entity does not get a notification, a memory, or a prompt about "a new user was created." The next time that user sends a message, the entity receives it with that user's name attached through the normal retrieval framing. If it's a name she's never seen, she handles it the way she'd handle meeting anyone new — with whatever judgment she's developed.

This is consistent with Principle 15 (experience over instruction). Pre-seeding her with "you now have a user named Sarah" would be instruction. Her first conversation with Sarah is experience.

---

## Authentication

### Web

Password-based auth on day-one. Standard shape:

- User logs in with username + password.
- Password hashed (argon2 or bcrypt; implementation detail) and compared against `auth_material` for the matching `(web, username)` row.
- On success, session token issued.
- Session token validates subsequent requests.

Token lifetime, refresh flow, logout, and password reset are operational details for the web adapter implementation. Not design-critical; any sensible default works.

### iMessage and other messaging channels

Channel-trust. No additional auth layer.

The reasoning: if Apple's servers delivered a message claiming to be from phone number X, we trust that attribution. The alternative — requiring users to log in before messaging — defeats the purpose of the messaging channel. It turns a natural "text her and she responds" into "text her, get a link, log in, then text her again."

The risk profile: if someone spoofs a phone number and sends iMessage to a number she watches, they could impersonate that user. This is mitigated by (a) the small, closed user set, (b) the unlikelihood of that attack, and (c) the fact that compromising an iMessage channel is roughly as hard as compromising an email account anyway. Accepting channel-trust is the right tradeoff.

### When channel-trust isn't enough

If a channel is added where attribution is weak (e.g., a public Discord server where anyone can message her), the adapter for that channel is responsible for establishing identity before passing messages to the engine. That might mean an explicit linking flow ("DM me `!link ABC123` to associate this account with your user"). The core system doesn't need to change — the adapter handles the verification, and only passes messages with a resolved `user_id` to the engine.

---

## Roles

Two roles, set on the `users.role` field.

### admin

- Full system visibility (see the "Admin-only visibility" section below).
- Can create, modify, and delete users.
- Can add and remove channel identifiers.
- Can approve or reject skills in the staging directory.
- Can manage the change log (though anyone could theoretically read it; practically only Lyle will).
- Reviews autonomous work artifacts.

### user

- Can converse with the entity.
- Can see their own conversation history in the UI.
- Cannot see other users' conversations.
- Cannot see system or debug information.
- Cannot administer anything.

**Role enforcement happens at the UI and admin-action layer, not in the memory layer.** The entity's retrieval is unified across users — her memory does not filter by who's currently talking to her. See the "Admin-only visibility" section for the full shape.

### Lyle as admin

Lyle's user row has `role = 'admin'`. This is set at user creation (in the seed/bootstrap script that creates the first user). There is nothing special about Lyle beyond that role assignment — the system doesn't check "is this Lyle?" anywhere. It checks "is this user an admin?"

The practical effect is the same day-one (Lyle is the only admin), but the schema doesn't paint into a corner if a second admin ever exists.

---

## What the entity knows about a user

Per the decision made this session: **names and channel identifiers only.** No pre-seeded relationship context, no notes, no "this is my wife."

When a conversation happens, the framing she receives for retrieval is based on the user's `name`:

> `[Conversation with Sarah on 2026-04-15]`
> `{chunk text}`

She has no notion of who Sarah is beyond that name until Sarah tells her, or until accumulated conversations with Sarah give her a sense of her. This is the experience-over-instruction path in action. Her relationships with each user are hers to develop.

**One small structural consequence:** if the same physical person reaches her through two channels but somehow gets created as two users (admin error, or a deliberate choice to keep work and personal contexts separate), she will experience them as two different people. That's a feature, not a bug — it puts the modeling choice in Lyle's hands. If he creates one user with two channel identifiers, they're one person to her. If he creates two users, they're two people to her. The system follows what the data says.

---

## Name handling in chunks

When a conversation chunk is created, the user's name is embedded directly into the chunk text. The chunk format becomes:

```
[2026-04-15 10:23 PM] Lyle: How's the research going?
[2026-04-15 10:23 PM] assistant: I found three papers on emergent behavior...
```

Rather than:

```
[2026-04-15 10:23 PM] user: How's the research going?
```

The name is pulled from the `users.name` field at the moment the chunk is created. It is then part of the stored chunk text — not metadata, not a lookup at retrieval time, just part of the content.

**Why this shape:**

- **The message row itself stores clean content.** The `content` field in `messages` (both archive and working store) remains exactly what the user typed. No framing embedded at write time. The conversation-is-ground-truth principle is preserved.
- **Framing lives in chunk creation.** Chunking is already the step where content gets formatted for retrieval. Name embedding happens in the same transformation that adds timestamps and role markers.
- **Memories preserve the name the person had.** If Lyle renames a user or deletes them entirely, existing chunks still show the name that person had when the conversation happened. She remembers talking to "Sarah," not "the-user-whose-current-name-is-Sarah."
- **No metadata snapshot field needed.** The name is in the chunk text. No separate `user_name_at_chunk_time` field, no resolution logic at retrieval.

**What this implies about deletion.** If Lyle deletes a user row, chunks from conversations with that user remain intact in ChromaDB and in the archive. Retrieval still surfaces those chunks; they still read naturally ("[...] Sarah: ..."). The only thing lost is the ability for that user to reach the entity again through any channel (their channel identifiers are gone). Her memory of them is not lost. That matches how memory actually works — someone leaving your life doesn't erase your memory of them.

---

## Deletion and the substrate

Principle 6 (never delete, only layer) applies to the entity's substrate — the archive, conversation and message data in the working store, chunks in ChromaDB. Those are never deleted.

It does **not** apply to operational/admin data — users, channel identifiers, session tokens, skill registry metadata, and similar. Those can be deleted when appropriate.

This means:

- **User row deletion is allowed.** If someone leaves and Lyle wants them out of the system, the user row and their channel identifiers can be removed. They can no longer reach the entity.
- **Conversation data survives.** Archive and working-store messages referencing the deleted user_id remain. Chunks in ChromaDB with that user's name embedded remain. The entity's memory of those conversations is intact.
- **Dangling user_id references are expected, not errors.** After a deletion, conversations reference a `user_id` that doesn't resolve in the `users` table. This is acceptable. The chunk text contains the name she remembers them by, so retrieval framing still works.

The substrate and the operational layer are distinct. What she remembers is sacred. Who can currently reach her is operational.

---

## Admin-only visibility

Only admins see system and debug information. Regular users see only their own conversations and nothing else.

What "system and debug information" includes:

- The change log.
- Tool traces (beyond what appears in the admin's own conversation UI).
- The skill registry and skill approval queue.
- Autonomous work artifacts (journals, research outputs, workspace files).
- Overnight process logs.
- User and channel identifier management.
- System health, metrics, debugging views.

What regular users see:

- Their own conversations with the entity.
- Whatever she shares with them in conversation (which she may choose to do with autonomous work, but that's her choice through conversation, not a system-provided view).

**This is a UI-layer concern, not a substrate concern.** Her memory remains unified. The UI filters what gets displayed to a non-admin user. Admin-gated actions check the user's role before permitting the action.



This doc depends on and constrains several other designs:

- **Schema Design v1** — specified `users` and `conversations` tables. This doc adds `channel_identifiers` and fills in the `users.role` field that the schema had as `NOT NULL DEFAULT 'user'`. The schema doc should be updated to add `channel_identifiers`.
- **Memory Requirements v2 (Requirement 6)** — "every conversation carries a user ID." This doc specifies how that ID gets resolved from an incoming message.
- **Context Construction v1 (retrieved memory framing)** — uses the user's `name` for conversation chunk framing. The name is embedded directly into chunk text at chunk-creation time (see "Name handling in chunks" below), which resolves the "user identifier resolution timing" open question from that doc: the name is part of the stored chunk, not resolved at retrieval time.
- **Autonomous Window Design v1 (gateway pattern)** — each adapter resolves user identity before passing normalized messages to the engine. This doc specifies the resolution logic.
- **Tool Framework Design v1** — skill approval is an admin action. This doc specifies that the admin role is what gates that capability.

---

## Open questions

**a. Admin action auditing.** Should there be an audit log of admin actions (user created, role changed, channel identifier added)? The change log exists for decisions that shape her runtime. User/channel management arguably falls in that category. Could go in the change log or in its own table. Deferred.

**b. Channel identifier verification for self-service flows.** When self-service is eventually added, identifiers land as `verified = 0`. What's the promotion flow? Email confirmation? OTP? Admin approval? Deferred to when self-service is designed.

**c. Name collisions.** Two users could have the same `name` ("Sarah" and another "Sarah"). The `id` is unique but the display name isn't. Do we enforce uniqueness? Add a disambiguator? Let the entity figure it out from context? Day-one this is a non-issue with a handful of users; flag for when the user set grows.

**d. What happens if a user's only channel identifier is removed.** They exist in the users table but can't reach her. This is a valid state (maybe temporarily between old channel removal and new channel addition) but worth knowing about operationally. No design change needed.

---

## Deferred

- **Self-service user creation.** Any flow where users create themselves. Not wanted for v1.
- **Automatic channel-identifier attachment** (e.g., "this phone number is new but the message contains a code Lyle shared with Sarah; attach it to her automatically"). Out of scope.
- **Fine-grained roles beyond admin/user.** No "moderator," "viewer," "read-only" etc. Two roles is enough.
- **Per-user privacy enforcement in retrieval.** The entity's memory is unified. She decides what crosses user boundaries. The system does not enforce that.
- **Session management specifics.** Token lifetime, refresh, logout — operational details for web adapter implementation.

---

*Project Tír User Model Design · v1 · April 2026*
