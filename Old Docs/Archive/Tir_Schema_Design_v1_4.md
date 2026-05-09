# Project Tír — Memory Layer Schema Design

*v1.4, April 2026. Changes from v1.3: switched both databases from WAL to rollback journaling to restore ATTACH-based atomic dual-write (WAL breaks cross-database atomicity per SQLite docs); removed `content` column from documents table (ChromaDB holds the chunks, documents table is metadata only); added explicit archive.db scope freeze; updated concurrency and rebuild references. Previous: v1.3 added chunks_fts. v1.2 added channel_identifiers, role, name-embedding-in-chunks.*

---

## Three stores, three jobs

The memory layer has three stores. Each one has a single purpose and a clear reason to exist as a separate thing.

| Store | What it is | Who reads it | Changes? |
|-------|-----------|-------------|----------|
| **Archive** (archive.db) | Permanent record of every conversation. Your insurance policy. | Only you (the developer) and rebuild scripts. The entity never sees it. | Never. Append-only. Schema never changes. |
| **Working Store** (working.db) | Operational database. Everything the UI, overnight processes, and developer tools need — including the lexical retrieval index. | You, the UI, processing scripts, retrieval. The entity never sees it directly. | Constantly. New tables, new columns, migrations — all expected. |
| **ChromaDB** | The entity's searchable semantic memory. Used by retrieval together with the FTS5 index in working.db. | Retrieval, during context construction and `memory_search`. | Append-only during normal operation. Wipe-and-rebuild when chunking strategy changes. Derived data — entirely rebuildable from the archive (for conversation chunks) or by re-ingestion (for document chunks). |

The archive exists because the working store will get beaten up. Schema migrations, experimental features, bug fixes — all of that churn happens in the working store. The archive sits untouched through all of it. If the working store is destroyed, everything in it can be rebuilt from the archive. The reverse is not true — conversations cannot be recreated.

**Archive scope is frozen.** Archive.db contains exactly two tables: `users` and `messages`. This is by design, not by accident. Conversations are irreplaceable because they contain someone else's input. Everything else — documents, tasks, autonomous work — is either re-runnable or goes through document ingestion for its own persistence. No future design should expand archive.db's scope.

**On retrieval:** semantic retrieval runs against ChromaDB. Lexical retrieval runs against `chunks_fts` in working.db. They are two indexes over the same chunk content, fused at query time. See Retrieval Design v1 for the query pipeline; see "chunks_fts" below for the index itself.

---

## Store 1: The Archive (archive.db)

The simplest store. Two tables. Designed to never need a schema change.

### users

Every person (or entity) who talks to her. This is in the archive so a rebuild from archive alone knows who user IDs refer to.

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,        -- UUID. Generated once, never changes.
    name TEXT NOT NULL,          -- Display name. "Lyle", "AgentX", etc. Immutable after creation.
    created_at TEXT NOT NULL     -- ISO 8601 UTC. When this user was first added.
);
```

**Why so minimal:** The archive version of a user is just "this ID means this name." Everything else about a user (preferences, roles, metadata) lives in the working store where it can evolve.

### messages

Every message ever exchanged. One row per message. Never modified, never deleted.

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,                -- UUID.
    conversation_id TEXT NOT NULL,      -- Groups messages into conversations.
    user_id TEXT NOT NULL,              -- Who the entity was talking to in this conversation.
    role TEXT NOT NULL,                 -- "user" or "assistant". Who said this message.
    content TEXT NOT NULL,              -- The full message text, verbatim. Exactly what was said.
    tool_trace TEXT,                    -- JSON. What tools the entity called during this message, if any. 
                                       -- NULL for user messages and assistant messages with no tool use.
                                       -- Stored here because tool calls are runtime events that can't be recreated.
    timestamp TEXT NOT NULL             -- ISO 8601 UTC. When this message was sent.
);

CREATE INDEX idx_archive_conversation ON messages(conversation_id);
CREATE INDEX idx_archive_timestamp ON messages(timestamp);
CREATE INDEX idx_archive_user ON messages(user_id);
```

**Why user_id is on messages, not on a separate conversations table:** Keeping the archive to two tables means there is no conversations table to maintain, no lifecycle state to track, nothing that might tempt someone to add "just one more column." The user_id is denormalized — every message in a conversation carries the same user_id — but that's the right tradeoff for a store that must never change shape. A conversation can be reconstructed by grouping messages on conversation_id.

**Why tool_trace is here:** Tool traces record what actually happened when the entity generated a response — which tools fired, with what arguments, what came back. This is runtime data. If it's lost, it's gone. Summaries and chunks can be rebuilt from conversations; tool traces cannot. So they belong in the archive alongside the message content.

**Pragmas:**

```sql
PRAGMA journal_mode = DELETE;   -- Rollback journaling. Required for ATTACH-based atomic
                                -- dual-write across archive.db and working.db. WAL breaks
                                -- cross-database atomicity (per SQLite docs: "if the
                                -- journal_mode is WAL, then transactions continue to be
                                -- atomic within each individual database file" only).
PRAGMA foreign_keys = ON;
```

That's the entire archive. Two tables, three indexes, done.

---

## Store 2: The Working Store (working.db)

The operational database. Same conversation data (dual-write), plus everything needed for the UI, overnight processes, system management, and lexical retrieval. This store will evolve — new tables, new columns, schema migrations are expected and normal.

### users

More detailed than the archive version. This is where user metadata lives.

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,            -- Same UUID as in archive.
    name TEXT NOT NULL,              -- Immutable after creation. Same value as archive.
    role TEXT NOT NULL DEFAULT 'user',  -- 'admin' or 'user'. See User Model doc.
    created_at TEXT NOT NULL,
    last_seen_at TEXT               -- Updated each time the user starts a conversation. UI convenience.
);

CREATE INDEX idx_users_role ON users(role);
```

**Why `role` is here and not in the archive:** The archive is for the sacred conversation record. Role is operational state — it governs who can do what at any given moment and may change over time. Operational state lives in the working store.

### channel_identifiers

How a user reaches the entity. One row per channel identifier; a user can have many.

```sql
CREATE TABLE channel_identifiers (
    id TEXT PRIMARY KEY,                -- UUID.
    user_id TEXT NOT NULL,              -- FK to users.id.
    channel TEXT NOT NULL,              -- 'web', 'imessage', 'discord', etc.
    identifier TEXT NOT NULL,           -- Channel-specific identifier (username, phone number, handle).
    auth_material TEXT,                 -- Channel-specific auth data (hashed password for web, NULL for iMessage, etc.).
    verified INTEGER DEFAULT 0,         -- 1 when this identifier is confirmed to belong to the user.
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (channel, identifier)        -- Same identifier can't attach to two users on the same channel.
);

CREATE INDEX idx_channel_identifiers_user ON channel_identifiers(user_id);
CREATE INDEX idx_channel_identifiers_lookup ON channel_identifiers(channel, identifier);
```

**Why this lives in the working store, not the archive:** Channel identifiers are purely operational. If a user rotates a phone number or changes their web password, the archive doesn't need to know. A rebuild from archive would need channel identifiers to be re-entered manually — that's acceptable because they're a small manually-managed set.

### conversations

Tracks each conversation's lifecycle and processing state. One row per conversation.

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,                    -- UUID.
    user_id TEXT NOT NULL,                  -- Who the entity was talking to.
    started_at TEXT NOT NULL,               -- When the conversation began.
    ended_at TEXT,                          -- NULL while the conversation is active. Set when it ends.
    message_count INTEGER DEFAULT 0,        -- Running count. Used to trigger live chunking.
    chunked INTEGER DEFAULT 0,              -- 1 when the final end-of-conversation chunk is done.
    consolidated INTEGER DEFAULT 0,         -- 1 when overnight summary has been generated.
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_conversations_user ON conversations(user_id);
CREATE INDEX idx_conversations_started ON conversations(started_at);
CREATE INDEX idx_conversations_ended ON conversations(ended_at);
```

**What "chunked" and "consolidated" mean:** These are processing flags so the system knows what work has been done. "Chunked" means the conversation's messages have been turned into searchable chunks in ChromaDB *and* indexed into chunks_fts. "Consolidated" means the overnight process has generated a summary for the UI. The entity never sees these flags — they're infrastructure (Principle 9).

### messages

Duplicate of archive messages, plus foreign key to conversations. Enables joins and queries that shouldn't touch the archive.

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,                    -- Same UUID as in archive.
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_trace TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX idx_working_conversation ON messages(conversation_id);
CREATE INDEX idx_working_timestamp ON messages(timestamp);
```

### summaries

One short summary per conversation, generated during overnight processing. Exists for the UI to show a conversation list with previews. The entity never sees these — they are not retrievable memory.

```sql
CREATE TABLE summaries (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,              -- 2-4 sentence summary of the conversation.
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### documents

Metadata for non-conversation material that's been ingested into ChromaDB (articles, files, URLs). This is a lookup table — the actual content lives in ChromaDB as chunks. The URL is preserved so the original source can be re-fetched if re-ingestion is ever needed.

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,                            -- UUID.
    title TEXT NOT NULL,
    url TEXT,                                       -- Source URL, if applicable. Preserved for re-fetching.
    source_type TEXT NOT NULL DEFAULT 'article',    -- What kind of thing this is.
    source_trust TEXT NOT NULL DEFAULT 'thirdhand', -- firsthand | secondhand | thirdhand.
    chunk_count INTEGER DEFAULT 0,                  -- How many chunks were created from this.
    summarized INTEGER DEFAULT 0,                   -- Processing flag for overnight summary.
    summary TEXT,                                   -- UI display only.
    created_at TEXT NOT NULL
);
```

**Why no `content` column:** ChromaDB holds the chunks. Storing the full extracted text here as well is a redundant write on every ingestion for a re-chunking scenario that can be handled by re-fetching from the URL. For path-based and content-based ingestion, the caller retains the source. Keeping this table lean as metadata only aligns with Principle 2 (simple is right).

### chunks_fts (new in v1.3)

FTS5 virtual table indexing all chunk text for BM25 lexical retrieval. Populated alongside ChromaDB writes. Queried by the retrieval layer as the lexical leg of hybrid retrieval (see Retrieval Design v1).

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id UNINDEXED,        -- Same chunk ID used in ChromaDB. The bridge.
    text,                      -- Chunk document text. Indexed for MATCH.
    conversation_id UNINDEXED, -- For conversation/journal chunks. NULL for documents.
    user_id UNINDEXED,         -- For conversation chunks. NULL otherwise.
    source_type UNINDEXED,     -- conversation, journal, article, research, etc.
    source_trust UNINDEXED,    -- firsthand | secondhand | thirdhand.
    created_at UNINDEXED,      -- ISO 8601 UTC, chunk creation time.
    tokenize = 'unicode61 remove_diacritics 2'
);
```

**Tokenizer:** `unicode61 remove_diacritics 2` — SQLite's Unicode tokenizer with diacritic folding. Handles typical text well; case-insensitive by default; strips accents so "café" matches "cafe."

**UNINDEXED columns:** stored so SQL WHERE clauses can filter (e.g., active-conversation exclusion), but not included in the BM25 index. Only `text` is MATCH-searchable.

**No separate SQL indexes needed.** FTS5 maintains its own internal index on `text`. Filtering on UNINDEXED columns happens on the FTS5-produced candidate set, not via a secondary B-tree — acceptable at top-K scales (BM25 pulls, say, top 30 candidates, and filtering 30 rows is free).

**Why this lives in working.db and not its own file:** Keeping it alongside the conversations and messages tables means one database file to open in a single connection for retrieval-adjacent queries. Matches the "mutable operational store" role — chunks_fts is derived data that can be rebuilt if wiped, which is the same posture as summaries and overnight processing artifacts.

**Consistency with ChromaDB.** The same chunk_id appears in both stores. A chunk is considered "indexed" when it exists in ChromaDB and in chunks_fts. The write path writes ChromaDB first, then chunks_fts; a partial failure leaves the chunk findable via vector search but not BM25 — degraded retrieval rather than lost data. The close-time rechunk-from-scratch operation (Chunking Strategy v1.1) re-writes to both stores, so any FTS5 drift gets reconciled at conversation close.

**Rebuild path.** If chunks_fts is wiped or corrupted, it can be rebuilt by iterating ChromaDB's collection and inserting every chunk back into FTS5. Standalone maintenance operation; not part of normal runtime.

### overnight_runs

Audit trail of what the overnight processing cycle did. One row per run. Intentionally minimal right now — the overnight process design isn't done, so this table captures the basics and will grow columns as overnight capabilities are built.

```sql
CREATE TABLE overnight_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds REAL,
    conversations_closed INTEGER DEFAULT 0,     -- How many conversations were marked ended.
    summary TEXT                                 -- Freeform notes on what happened. 
                                                -- Specific task columns will be added as overnight processes are designed.
);
```

**Pragmas:**

```sql
PRAGMA journal_mode = DELETE;   -- Rollback journaling. Must match archive.db for ATTACH atomicity.
PRAGMA foreign_keys = ON;
```

### Tables deliberately NOT included

These existed in the prior project and are intentionally dropped:

- **self_knowledge** — Compressed identity narrative injected into every turn. Violated Principles 3 and 11. Dropped.
- **self_reviews** — Draft-review-revise loop output. Mechanism for prior model's instability. Not expected to apply. Dropped.
- **observations** — Per-conversation behavioral observations. The overnight observer doesn't exist in Tír yet. When/if it's added, an observations table can be added trivially. No reason to pre-build it.
- **user_voice_fts** (from prior project's retrieval stack) — A narrow FTS5 index over user messages only. Memory Requirements open question (d) reads this as likely subsumed by general-purpose `chunks_fts`. Not pre-built; add if specific gaps appear on user-voice queries.

---

## Store 3: ChromaDB (vector store)

The semantic-retrieval half of the entity's searchable memory. Together with chunks_fts in working.db, covers what she can find when she thinks back.

### Collection

One collection: `tir_memory`

One unified semantic space. Not sharded by source type, not partitioned by user. Every chunk — conversation, journal, article, research, whatever comes next — lives in the same space so a single query can surface anything relevant.

ChromaDB is derived data. Conversation chunks are rebuildable from the archive's messages table. Document chunks are rebuildable by re-ingesting from the source URL or file. During normal operation, chunks are only added, never modified or deleted. During a rebuild (e.g., when chunking strategy changes during retrieval tuning), the collection is wiped and recreated from source. chunks_fts is similarly rebuildable from ChromaDB content. The "never delete" principle (Principle 6) protects the archive — derived stores are expendable by design.

- **Distance metric:** Cosine similarity.
- **Embedding model:** nomic-embed-text via Ollama, 768 dimensions. Matches the Aion foundation; validated working on M4 hardware in earlier Tír bootstrap testing. The schema doesn't depend on the embedding model — that's a configuration choice — but the embedding dimension is an implicit constraint that must match across the collection.

### Chunk ID format

Each chunk has a deterministic ID built from its source and position:

- Conversation chunks: `{conversation_id}_chunk_{chunk_index}`
- Document chunks: `{document_id}_chunk_{chunk_index}`

The same chunk ID is used as the `chunk_id` column in `chunks_fts`. This is the bridge between the two stores — retrieval uses chunk_id to associate vector search results with BM25 search results for fusion.

This means re-chunking the same source with the same boundaries produces the same IDs — useful for idempotent rebuilds.

### Chunk document text

The text stored in each chunk is the raw content, formatted honestly for what it is (Requirement 14):

**Conversation chunks** read like conversations, with the user's name embedded directly (per the User Model doc):
```
[2026-04-15 at 10:23 PM] Lyle: How's the research going?
[2026-04-15 at 10:23 PM] assistant: I found three papers on emergent behavior in multi-agent systems...
```

The name is pulled from `users.name` at chunk-creation time and embedded into the chunk text. This means chunks preserve the name the person had when the conversation happened — the name is immutable after user creation, so there is no drift between the users table and stored chunks. The raw `messages.content` field in both archive and working store remains clean (the actual text the person typed); name embedding happens only at the chunking step.

**Journal entries** read like journal entries (first-person reflective writing, not wrapped in conversation format).

**Articles and documents** read like articles (their original text, not wrapped in a fake `[unknown time] system:` prefix).

The format matches the thing. No fake wrappers.

**The same text goes into chunks_fts** as the `text` column value. BM25 operates on the same formatted chunk text the entity reads — so BM25 matches on "Lyle" match exactly the same chunks where her name appears in rendered form.

### Metadata per chunk

Every chunk carries metadata that the retrieval and context-construction systems use. The entity doesn't see raw metadata — it's used to inform how chunks are selected, ranked, and framed when building her context.

```python
{
    # Source identification
    "conversation_id": str,     # For conversation/journal chunks: which conversation.
    "document_id": str,         # For document chunks: which ingested document.
    "chunk_index": int,         # Position within the source (0, 1, 2...).

    # What kind of experience this is
    "source_type": str,         # "conversation", "journal", "article", "research", "creative", etc.
                                # Open-ended — new types added as new capabilities are built.

    # Trust level
    "source_trust": str,        # "firsthand" — her own conversations, journals, creative output.
                                # "secondhand" — outside commentary about her.
                                # "thirdhand" — articles, external content she consumed.

    # Who was involved (for conversations)
    "user_id": str,             # Which user she was talking to. NULL for non-conversation chunks.

    # Context
    "message_count": int,       # For conversation chunks: how many messages in this chunk.
    "created_at": str,          # ISO 8601 UTC. When this chunk was created.
}
```

**On source_type extensibility:** The metadata schema doesn't enumerate allowed source_types. It's a string field. When a new kind of experience is added to the system (a new autonomous activity, a new kind of artifact she produces, conversations through the multi-entity hub), it gets a new source_type value. No schema change needed.

**On user_id in chunk metadata:** This is how the retrieval system knows which user a conversation chunk came from. When building her context, this enables framing like "from your conversation with Lyle" vs. "from your conversation with AgentX." The entity's context construction uses this; the entity herself sees the framing, not the raw metadata.

**Mirrored into chunks_fts:** The same metadata fields (conversation_id, user_id, source_type, source_trust, created_at) are stored as UNINDEXED columns in chunks_fts so BM25 queries can filter on them in SQL. The subset stored in chunks_fts is what retrieval actually needs for filtering; fields like `chunk_index` and `message_count` live only in ChromaDB because they don't participate in retrieval decisions.

---

## The write path

What happens when a message is sent or received:

1. **Dual write.** The message is written to both archive.db and working.db in a single transaction. SQLite's ATTACH command opens both databases in one connection, so a single transaction spans both files — if either write fails, both roll back. Both databases use rollback journaling (`journal_mode = DELETE`), which is required for this cross-database atomicity to work. (SQLite's docs: cross-database atomicity via ATTACH requires non-WAL journaling.)
2. **Conversation state update.** working.db's conversations table gets its message_count incremented.
3. **Live chunk check.** If the turn count (assistant messages) has hit the chunking interval (5 turns per Chunking Strategy v1.1), a chunk is created from the recent messages.
4. **Chunk write to both indexes.** The chunk is embedded and upserted into ChromaDB with full metadata. Then the same chunk is inserted (or replaced) into chunks_fts with its text and filter metadata.
5. **Retrieval.** The entity's current message is used as a query against both ChromaDB (vector) and chunks_fts (BM25). Results are fused via RRF and trust-weighted. See Retrieval Design v1.
6. **Context construction.** Retrieved chunks are framed honestly and assembled into the entity's context alongside her seed identity.
7. **Response generation.** The model produces a response.
8. **Response write.** The assistant's message (with tool_trace if applicable) is dual-written to both databases.
9. **Live chunk check again.** The assistant's message counts toward the next chunk.

When a conversation ends:

1. Re-chunk the whole conversation from scratch — deterministic chunk IDs + upsert semantics mean existing chunks become no-ops, missing chunks get filled. Writes to both ChromaDB and chunks_fts.
2. working.db conversations row gets ended_at set and chunked = 1.
3. Overnight: summary generated and written to summaries table.

### Concurrency note

Rollback journaling means readers block during writes. At Tír's scale — single user, millisecond INSERT operations, turn-level serialization via engine_lock — this blocking is negligible. If concurrent access ever becomes a measured bottleneck (not anticipated), the mitigation is to move to a write-archive-first, write-working-second pattern with application-level compensation, trading cross-database atomicity for concurrency. That trade is not worth making until real data shows it's needed.

### FTS5 write ordering and failure handling

**Order:** ChromaDB write first, then chunks_fts insert. Rationale: ChromaDB's write is the bigger operation (embedding call, vector upsert); if it fails, we don't want an orphan FTS5 row pointing at a chunk_id that won't resolve when retrieval tries to pull its full content. With ChromaDB-first, a failure between steps leaves a chunk findable via vector only — degraded but coherent.

**FTS5 write failure:** if chunks_fts insert fails after ChromaDB succeeded, log a warning and continue. The conversation's subsequent rechunk-at-close will re-upsert both stores, catching the gap. Same asymmetric error handling as live chunking at the chunk-write-pipeline level (per Chunking Strategy v1.1): message persistence is sacred, chunking is derived, indexing within chunking is further derived still.

**In-transaction FTS5 writes:** chunks_fts is in working.db, so an FTS5 insert can participate in a working.db transaction if desired. But the ChromaDB write has no transactional relationship to working.db; it's a separate store with its own consistency model. So "transactional FTS5 write" only buys anything when paired with other working.db changes — which it isn't, during chunk writes. Straight insert outside any wrapping transaction is fine.

---

## Document ingestion path

When the entity ingests an article, file, or URL:

1. Metadata written to working.db documents table (title, URL, source_type, source_trust, chunk_count).
2. Content is chunked using document-appropriate chunking (not conversation chunking — chunk sizes and overlap may differ).
3. Each chunk is embedded and upserted to ChromaDB with the document's source_type and source_trust, then inserted into chunks_fts with its text and metadata.
4. Documents table chunk_count updated.
5. Overnight: optional summary generated for UI display.

Document chunks have `document_id` in their metadata but no `conversation_id`. The chunks_fts row has `NULL` in the conversation_id column for document chunks — retrieval's active-conversation filter handles this via `WHERE (conversation_id IS NULL OR conversation_id != ?)`.

---

## Schema migration from v1.3 to v1.4

Three changes from v1.3:

1. **Journal mode change.** Both databases switch from `PRAGMA journal_mode = WAL` to `PRAGMA journal_mode = DELETE`. This is a per-database setting that persists — set once, it sticks across connections. Existing databases need the pragma applied once; new databases get it at creation.

2. **Documents table `content` column removed.** For existing databases with data in this column, a migration drops the column (`ALTER TABLE documents DROP COLUMN content` — supported in SQLite 3.35.0+, macOS ships 3.39+). For pre-launch state with no production data, recreating the table is simpler.

3. **Archive scope freeze documented.** No schema change; this is a design constraint captured in the doc header and the Store 1 section.

---

## What this schema does NOT decide

These are deliberately left as implementation/configuration choices:

- **Embedding model.** nomic-embed-text is current; the schema doesn't care what produces the embeddings as long as the dimension is consistent across the collection.
- **Chunk sizes and overlap.** Configuration knobs, not schema. Chunking Strategy v1.1 specifies 5-turn conversation chunks, no overlap.
- **Retrieval algorithm specifics.** BM25 parameters (tokenizer is in-schema; stopwords, phrase handling, query rewrite are not), RRF k, trust weights, distance thresholds, result counts — all tunable configuration. See Retrieval Design v1.
- **Fabrication event source type and format.** Depends on the tool framework design. The schema supports it (source_type is open, ChromaDB accepts any chunk, chunks_fts indexes any text) — the specific shape lands when the tool framework lands.
- **Overnight process specifics.** The overnight_runs table is intentionally sparse. Columns get added as overnight capabilities are designed.

---

*Project Tír Memory Layer Schema · v1.4 · April 2026*
