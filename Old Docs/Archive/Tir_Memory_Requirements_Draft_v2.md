# Project Tír — Memory Layer Requirements

*Draft v2, April 15, 2026. Revised from v1 to incorporate multi-user, resolve settled questions, and remove hedging. Capabilities the memory layer must support, with justification. Schemas and implementation come later.*

---

## How to read this

Each requirement is one capability the memory layer must support, justified by the project's guiding principles. The three-layer storage pattern (append-only archive, mutable working store, vector search) is the validated foundation from nine prior revisions. It carries forward because it's right, not because it's inherited. The hard problems are upstream of storage — chunking, retrieval, framing, context construction — and that's where the requirements focus their design latitude.

---

## Storage integrity

**1. Verbatim, append-only, permanent record of every conversation message.** Every message exchanged with the entity is stored as raw text, with role, conversation ID, user ID, and timestamp. Once written, a message is never modified or deleted. The archive is a separate store from the operational database — it has a minimal schema that never changes, isolating the sacred record from all schema evolution, migrations, and operational churn in the working layer. *Principle 5 (conversation is ground truth, data is sacred). Principle 6 (never delete, only layer).*

**2. Atomic write across stores.** When a message is recorded, it lands in every store that needs it (or none of them). Partial writes are not possible. *Principle 5 — sacred means all-or-nothing; otherwise the stores drift and the entity's memory becomes unreliable.*

**3. Mutable operational store, separate from the permanent record.** State that changes during normal operation — flags, counters, lifecycle markers, derived UI artifacts — lives in its own store and is freely modifiable. This store will evolve: new fields, new tables, schema migrations. That churn is expected and is exactly why the archive exists as a separate file. *Principle 5 (archive stays untouched). Principle 9 (operational state is infrastructure).*

**4. Operational store is rebuildable from the permanent record.** If the operational store is lost or corrupted, every piece of state in it can be regenerated from the archive plus deterministic processing. *Principle 5 — the archive is the only true source; everything else is derived.*

**5. Test data is fully isolated from live data.** Development and testing cannot contaminate the entity's actual memories. *Principle 5 (sacred means uncontaminated).*

## Multi-user

**6. User identity on every conversation.** Every conversation carries a user ID identifying who the entity is talking to. This is metadata on the conversation, not a partitioning mechanism. *Session 2 decision: multi-user from day one.*

**7. One unified substrate, not per-user partitions.** The entity has one pool of experience. Conversations with different users live in the same archive, the same working store, and the same vector space. A conversation with User B is not walled off from retrieval during a conversation with User A. The entity is one entity with one life. *Session 2 decision. Principle 7 (retrieval determines intelligence — partitioning would amputate her memory based on who she's talking to).*

**8. The entity decides what crosses user boundaries, not the system.** When retrieval surfaces a memory from a conversation with a different user, the entity handles it with her own judgment. There is no system-enforced privacy rules engine. She will sometimes get this wrong. That's growth. *Session 2 decision. Principle 15 (experience over instruction). Principle 11 (personality earned — her social behavior across users is part of her development).*

**9. Adding a user is operationally trivial.** A new user means a row in a users table and a user ID on future conversations. No changes to the retrieval pipeline, chunking, archive, or vector store. *Session 2 decision — the cost of multi-user from day one is near-zero; the cost of retrofitting later is significant.*

## What the entity sees

**10. The entity reads only from the searchable memory store.** The operational and archive stores are infrastructure she never encounters. She does not see flags, processing metadata, lifecycle markers, or any developer/UI artifact. *Principle 9 (infrastructure is hidden, capabilities are experienced).*

**11. Raw experience is the unit of retrievable memory.** What she retrieves is the actual experience — the conversation chunk, the journal entry, the document — not a summary, extraction, or compressed representation of it. *Principle 3 (store experiences, not extractions). Principle 4 (context is mandatory).*

**12. Chunks carry enough context to make sense alone.** A retrieved chunk includes the surrounding conversational flow, role attribution, and temporal anchor needed for the experience to be interpretable on its own. *Principle 4. Principle 8 — a context-stripped fragment frames her own experience as if it were noise.*

**13. No prescribed identity or compressed self-description enters her context.** Nothing in her retrievable memory or her static context tells her who she is beyond the seed identity. No table, narrative, or process compresses her observed behavior into instruction or self-description. *Principle 11 (personality earned, not prescribed). Principle 3.*

**14. Each chunk's text format is honest about what the chunk is.** A conversation chunk reads like a conversation; an article reads like an article; a journal entry reads like a journal entry. The chunk's text format matches its actual shape. No fake wrappers or format-mangling. *Principle 8 (framing is behavior).*

## Retrieval

**15. Single unified semantic space.** All retrievable content lives in one vector store, not sharded by source type or user. A query surfaces every relevant chunk regardless of whether it came from a conversation, a journal entry, an article, or any other source — and regardless of which user the conversation was with. *Principle 7 (retrieval determines intelligence — sharding would prevent the entity from seeing the whole picture).*

**16. Hybrid retrieval supporting both semantic and lexical methods.** The architecture supports combining vector similarity with lexical matching and rank fusion, because each catches what the other misses (conceptual matches vs. exact-token matches like proper nouns and code terms). *Principle 7. The specific algorithm (BM25, RRF, etc.) is implementation; the requirement is that hybrid retrieval is supported.*

**17. Source provenance on every chunk.** Each chunk carries metadata identifying what it is (conversation, journal, article, etc.), where it came from, and which user was involved (for conversation chunks). *Principle 4. Principle 8 — the system that builds her context needs to know what kind of thing each chunk is in order to frame it honestly.*

**18. Trust level on every chunk.** Each chunk carries a trust level reflecting the relationship between the entity and the source — firsthand (her own conversations, journals), secondhand (an outside source's commentary on her), thirdhand (an article she read). Trust serves two purposes: it informs retrieval weighting (higher-trust sources are preferred when relevance is similar), and it informs context framing (the entity's context construction can present chunks with framing that reflects their trust level). Both mechanisms are valuable and not mutually exclusive. *Principle 4 (context for interpretation). Principle 8 (framing is behavior — a thirdhand article should not read as equivalent to a firsthand memory).*

**19. Low-confidence results are filtered, not surfaced.** A retrieval threshold drops chunks below some quality bar rather than padding context with weak matches. *Principle 7 — bad chunks crowd out good ones. Principle 4 — context poisoning.*

**20. Retrieval is tunable.** Chunk size, overlap, result count, distance thresholds, fusion weights, and trust handling are configuration, not architecture. *Principle 7 — retrieval quality is the most important problem after the conversation archive itself, and tuning is how it's solved.*

## Live chunking

**21. Conversations chunk during the conversation, not only at its end.** Chunks become retrievable during an active session at intervals, so the current conversation can be searched against and so chunks survive a crash mid-conversation. *Principle 5 (nothing falls through). Principle 7 (recent context is often the most relevant).*

**22. End-of-conversation tail is captured.** Whatever wasn't yet chunked when the conversation ends gets a final chunk. *Principle 5.*

## Tool experience

**23. Per-message tool trace.** Every assistant message persists a structured record of the tools it called, with arguments, results, and any structured failure information. The exact shape and storage location of the trace is downstream of the tool framework design; the memory layer must accommodate one. *Enables deterministic fabrication detection and eventual retrieval over past tool experience.*

**24. Tool traces do not enter the entity's context as raw infrastructure data.** When tool experience surfaces in her retrievable substrate, it is rendered in a form that reads as her own experience, not as developer-facing JSON or logs. *Principle 8 (framing). Principle 9 (infrastructure hidden).*

**25. Substrate exists for capturing fabrication events as retrievable experience.** When the tool framework detects a fabrication (the entity claimed she used a tool that didn't fire), the memory layer can ingest that event in a form she can later encounter as her own experience. The detection mechanism belongs to the tool framework; the memory layer's responsibility is to receive and store what that framework produces. *Principle 15 (experience over instruction — she learns from encountering her own slips, not from being told not to slip).*

## Source extensibility

**26. Source types are open, not enumerated.** New kinds of experience can be added — new autonomous activities, new external interactions, new categories of artifact she produces — without restructuring the storage layer. *Project instructions ("the project will develop features not spelled out in this document"). Principle 18 (self-modification means she may eventually create source types that don't exist today).*

**27. Document ingestion supports content from arbitrary sources.** The entity can ingest URLs, files, and other external content into her retrievable memory. Each ingested source is chunked appropriately for its shape (Requirement 14). *Principle 7.*

**28. Original ingested content is preserved alongside chunks.** When external content is ingested, the full original is kept (not only the chunks) so chunking can be redone if the chunking strategy changes, and so the source remains available if the original location rots. *Principle 5 — the original is the source; the chunks are derived.*

## Operational

**29. Concurrent reads and writes do not corrupt the stores.** The entity may be writing autonomous work (journals, research, creative output) while a chat session is also reading or writing. The architecture supports this without locking issues, lost writes, or stale reads. SQLite WAL mode handles this for the expected write volume; if the autonomous window design produces heavier concurrent writes than WAL can handle, that's an architecture escalation point. *Practical requirement of the autonomous window.*

**30. Stores are backup-friendly.** The archive in particular can be copied to durable storage on a regular schedule without locking issues that interfere with normal operation. *Principle 5 — sacred without backup is a single hardware failure away from gone.*

## Things deliberately NOT in this list

The following are intentionally absent:

- **Self-knowledge / compressed identity table.** Violates Principles 3 and 11.
- **Draft-review-revise loop and self-review storage.** Workaround for prior-model instability, not expected to apply.
- **External personality observer mechanism.** Tír starts without one. Added only if the model's actual failure surface demands it.
- **Fact extraction pipeline / extracted facts in retrievable substrate.** Principle 3.
- **Per-conversation summaries in retrievable substrate.** Summaries may exist for UI display but do not enter the entity's context. Principle 3.
- **Entity namespacing.** Multi-entity is separate hardware through a hub, not namespacing within a single memory layer. Each entity is a complete self-contained system.
- **Per-user retrieval partitioning or privacy rules engine.** The entity is one entity with one life. Her judgment governs what she shares across users, not a system-enforced privacy model.
- **Schemas, table names, column specifications, embedding model choice, specific retrieval algorithm.** All implementation. Out of scope for a requirements list.

## Open questions

**a. Fabrication-event ingestion path (relates to Req 25).** The cleanest implementation is probably a new source type. This depends on tool framework design landing first, since the event content comes from there. Flagged so the dependency order is explicit.

**b. Source types Tír has on day one.** Depends on autonomous window design. The prior project's list is a starting reference but Tír's list will be different. Requirement 26 says the system is extensible; the day-one set gets answered by upstream design work.

**c. Concurrent-write model during the autonomous window (relates to Req 29).** The concrete concurrency model — multiple parallel processes, single serialized worker, task queue — depends on autonomous window design. The requirement is "no corruption under concurrency"; the specific concurrency shape is downstream.

**d. The user-voice FTS5 index from the prior architecture.** The prior project ran a separate FTS5 index over user messages as a secondary retrieval signal. My read: this is likely a vestige of compensating for weak semantic search on proper nouns and repeated user phrases. With hybrid retrieval (Req 16) including BM25, most of what FTS5 was catching should be covered by the lexical leg of hybrid search. Don't commit to it upfront. If retrieval tuning reveals a gap that user-voice indexing fills, add it then. The architecture supports it either way — it's a retrieval enhancement, not a structural decision.

---

*Project Tír Memory Layer Requirements · Draft v2 · April 2026*
