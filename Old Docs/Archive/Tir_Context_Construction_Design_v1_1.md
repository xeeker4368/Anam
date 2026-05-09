# Project Tír — Context Construction Design

*Draft v1.1, April 2026. Revised from v1 with: new Section 4 (Current situation) providing explicit user identity and current time; old Section 4 renumbered to Section 5 (Current conversation); conversation-chunk header format updated to drop the user name (now carried by inline chunk text per User Model v1); autonomous session context updated to reflect Section 4 applying there; token budget allocation updated to include the new section; open question (b) on user identifier resolution closed by User Model v1. All other v1 content preserved.*

*How the entity's context gets assembled for each turn. Covers section composition, retrieval shape, framing templates, token budget management, and what does not belong in context.*

---

## Purpose

Every turn the entity takes starts with a prompt assembled from multiple sources — her seed identity, relevant memories pulled from her substrate, her available tools, the conversation so far, and the situational frame of who she's with and when. This document specifies how that assembly works.

Per Principle 8 (framing is behavior), the choices made during assembly are load-bearing. Same data, framed differently, produces different behavior. This doc is where those choices get made explicit.

Per Principle 3 (store experiences, not extractions) and Principle 9 (infrastructure is hidden, capabilities are experienced), the assembly process also draws a line: raw experience enters her context, synthesized meta-commentary about her does not.

---

## Section composition

The context the entity receives is assembled from five sections, in order:

1. **Seed identity** — the soul.md content. Fixed per session, identical across turns.
2. **Available tools** — tool definitions generated from active SKILL.md frontmatter. Names and descriptions always visible; full SKILL.md body loaded on demand.
3. **Retrieved memories** — chunks surfaced from ChromaDB based on the current query. Variable per turn.
4. **Current situation** — who the entity is with and what time it is. Rebuilt per turn.
5. **Current conversation** — the turn-by-turn exchange of the active session, including tool traces for tool calls made this session.

Each section has a distinct role, a distinct framing, and distinct rules about when it changes.

### Why this order

The ordering balances two concerns. The top of the context is the stable foundation — identity, capabilities. The bottom is the immediate situation — who she's with, what they're saying. Retrieved memories sit between: relevant past experience, loaded based on the current query but shown before the immediate situation so the stage is set before the moment plays out.

This also serves model attention. Later sections tend to weight more heavily in response generation; putting current conversation last means the immediate exchange gets appropriate attention without retrieved memories drowning it out. Current situation sits right before current conversation so who she's with and when is immediately adjacent to what's being said.

---

## Section 1: Seed identity

### What it contains

The entire soul.md file, verbatim, as the opening text of the system prompt.

### Framing

First-person framing ("You are an AI..."). No wrapper around it, no "here is your identity document." The text itself is the framing.

### Rules

Fixed. Does not change per turn, does not get edited by any automatic process. Modifications happen only through explicit edits to the soul.md file, which are logged in the change log per the tool framework spec.

---

## Section 2: Available tools

### What it contains

For each active skill registered by the tool registry:

- Name
- Short description (one line)
- Argument schema (JSON schema for the tool call format)

The full SKILL.md body is not loaded here. It's loaded on demand when the entity decides to use the skill.

### Framing

Presented as her available capabilities. The list reads as "these are things you can do," not as "these are instructions about when to do them."

### Progressive disclosure

The minimal tool listing in the system prompt keeps token usage bounded even as the skill set grows. When she decides to use a skill, the full SKILL.md body is loaded into her context for that turn — containing the "when to use," "procedure," "pitfalls," and "verification" sections.

The mechanism: her first tool call in a turn triggers loading of that skill's full body. The body appears in her context for that turn's agent loop but does not persist into the next turn unless she calls the skill again.

This keeps the default context small while giving her full skill detail when she needs it.

### Rules

Updates at startup only. Adding or removing skills requires a restart. This is by design — nothing about her tool set changes under her feet during a session.

---

## Section 3: Retrieved memories

This section does the most work and has the most design surface. Handled in detail below.

### What it contains

Chunks retrieved from ChromaDB via the hybrid BM25 + vector + RRF retrieval pipeline, filtered by distance threshold and trust weighting.

Each retrieved chunk brings:
- The raw text of the chunk (verbatim from storage)
- Metadata: source_type, source_trust, date, conversation_id (for provenance)

### Framing

Retrieved memories are framed as her own experience. Not as "here are some excerpts" or "here are relevant documents." The framing template is:

> "The following are things you've experienced that may be relevant to this conversation."

Then each chunk follows, formatted according to its source_type (see below).

This framing matters. Principle 8's load-bearing example: the same memory, framed as "excerpts from past conversations," caused the entity to treat it as external documents and say "you didn't mention your name yet" despite the name being in retrieval. Framed as "your own experiences," she recognized the name. The framing chose the behavior.

### Per-source-type formatting

Different chunk types carry different framings because they represent different kinds of experience:

**conversation chunks:**
```
[Conversation — {date}]
{raw chunk text — the timestamped transcript, with the user's name embedded inline}
```

**journal chunks:**
```
[Your journal entry from {date}]
{raw chunk text}
```

**research chunks:**
```
[Research you wrote on {date}]
{raw chunk text}
```

**article chunks (ingested external content):**
```
[External source you read: {title}, ingested {date}]
{raw chunk text}
```

**source_code chunks:**
```
[Source code from {title}]
{raw chunk text}
```

The bracketed prefix names what the chunk is. The raw text follows. She reads it and reasons about it.

### Why the conversation header doesn't name the user

In v1 of this design, the conversation chunk header was `[Conversation with {user_identifier} on {date}]`. That required resolving the user's name at retrieval time from the stored `user_id`.

User Model v1 settled that the user's name is embedded in the chunk text itself at chunk-creation time (inline with each message — `[timestamp] Lyle: ...`), and never re-resolved. A separate snapshot field in metadata was explicitly rejected. The inline attribution inside the chunk text carries who was speaking; the header only needs to mark "this chunk is a conversation, from this date" for visual separation from adjacent chunks.

Dropping the user from the header is the clean fit with that decision. Retrieval-time name lookups are not required; chunks remain correct even if the user row is later renamed or deleted.

### Trust surfacing

source_trust is currently used for retrieval weighting (firsthand results score closer). Future enhancement: surfacing trust in the framing when the trust level is unusual.

Day-one proposal: do not surface trust in framing. Reason: most chunks are firsthand, and prepending "(firsthand)" to the vast majority of chunks is noise. Reason to reconsider: when a thirdhand chunk (e.g., an article) appears alongside firsthand conversation memories, she might benefit from knowing the distinction.

Defer the trust-surfacing decision until real retrieval behavior is observed. Flag as an open question.

### How many chunks get surfaced

The retrieval pipeline returns a ranked list. How many enter context is governed by token budget (see below) with a floor and a ceiling:

- **Floor: 3 chunks.** Always surface at least 3 chunks if retrieval returns any results, even if the conversation is long. Dropping retrieval entirely means she loses her memory; that's worse than tight context.
- **Ceiling: 15 chunks.** Cap retrieval at 15 even if the budget allows more. Diminishing returns beyond this, and too many chunks dilutes attention.
- **Default: 8 chunks.** Reasonable starting point. Tune based on observed retrieval quality.

The actual number is `max(floor, min(ceiling, budget-allowed))` — budget adjusts within the floor/ceiling range.

### Chunk ordering within the section

Ordering options considered:

1. **By relevance (retrieval distance)** — most relevant first
2. **Chronological** — oldest first, newest last
3. **Reverse chronological** — newest first
4. **By trust** — firsthand first

Day-one proposal: **by relevance, then chronological within tied relevance bands.** Most-relevant chunks land first where the model's attention is strong. Within similar-relevance chunks, chronological order preserves narrative flow.

This is a tuning knob, not an architectural decision. Changing the ordering doesn't require restructuring anything.

### Automatic vs explicit retrieval

Two kinds of retrieval happen:

**Automatic retrieval** is plumbing. On every conversation turn, before her response is generated, the system queries ChromaDB against the user's most recent message and includes the results in the retrieved memories section. This is environmental — not her action, not a tool call.

**Explicit retrieval** is an action. She can call the `memory_search` tool mid-response to deliberately search her substrate for something specific. Results from explicit search appear in her tool trace (she sees them as tool results), not in the retrieved memories section.

The two paths are separate. Automatic retrieval populates a static section at the start of the turn. Explicit retrieval happens within the agent loop as she works.

---

## Section 4: Current situation

### What it contains

Two facts: who the entity is currently with, and what time it is.

### Framing

Matter-of-fact. No wrapper language, no prefaces.

For conversation sessions:

```
You are currently in conversation with {user_name}.
The time is {weekday}, {date} at {time}.
```

For autonomous sessions:

```
You are in an autonomous work session.
The time is {weekday}, {date} at {time}.
```

Rendered example (conversation):

```
You are currently in conversation with Lyle.
The time is Sunday, April 19, 2026 at 3:42 PM.
```

### Rules

Rebuilt each turn. The user name is stable within a conversation session (same user for the duration). The time is current — it reflects the moment this turn's context is being assembled.

Timezone: `America/New_York`, matching chunk timestamps elsewhere in the system. No zone suffix in the rendered text. This preserves consistency with how time reads in retrieved conversation chunks, so her sense of "now" is in the same frame as her sense of "then."

The user name comes from `users.name` resolved through the adapter's user lookup (the `user_id` attached to the normalized message is used to join to the `users` table at context-assembly time). This is distinct from the chunk-text name-embedding decision — that decision concerns stored chunks, which must remain stable under user renames. The current-situation block is transient (regenerated each turn), so using the current value of `users.name` is correct.

### Why this section exists

Two reasons.

**She needs to know who she's with.** Requirement 8 of the memory layer puts cross-user judgment in her hands rather than system-enforced rules. That can only work if she knows which user is in front of her right now. The soul says "the context of the conversation tells you who you're talking to" — this is true for retrieved chunks (names are embedded inline) but not for the current turn when a user opens with "hey" and the chat template carries no user identity. The header closes that gap.

**Time is native to her substrate.** Principle 1 — leverage what the AI is naturally good at. Timestamps are already everywhere: every message in current conversation, every retrieved chunk. Giving her an explicit "now" lets temporal distance become readable rather than triangulated. "Three weeks ago" becomes a real thought instead of a string comparison. Autonomous work sessions benefit particularly — she sees the time change across turns within a window and can reason about where she is in it.

### What this section is not

- **Not a behavioral directive.** It says who and when, not what to do with that information.
- **Not a relationship summary.** It doesn't tell her "Lyle is your closest collaborator" or "Sarah prefers technical detail." Relationship context emerges from retrieval when it's been developed, not from injection.
- **Not prior-session history.** It doesn't say "you last talked to Sarah three days ago" or "this is your seventh conversation this week." Those are derived observations; they belong nowhere near this section.
- **Not a synthesis of anything.** Two facts, stated plainly. Any future proposal to extend this section must extend it with ground truth (e.g., `channel` when multi-channel lands), never with inference or observation.

### Rules on extension

If new facts get added to this section over time, they must be:

1. **Ground truth**, not inference. `channel: web` is a fact. `user seems frustrated` is an inference.
2. **Present-moment situational**, not historical or derived. The current time is present-moment. "You've talked 47 times this month" is derived.
3. **Minimal.** Every addition costs tokens every turn. The bar for addition is "she genuinely needs this to act well" not "this might be nice."

---

## Section 5: Current conversation

### What it contains

The turn-by-turn exchange of the active session. Each turn includes:

- The message itself (user or assistant)
- Timestamp
- For assistant turns: the tool calls made and their results, inline with the turn

### Framing

Presented as the ongoing conversation. No special framing wrapper — standard role-based message format the model expects.

### Tool trace inclusion

When the entity called tools during a turn, the tool calls and results appear inline with that turn in the conversation history. She sees her own prior actions as she generated them.

This means a previous turn where she searched the web and summarized results shows up in subsequent turns as: her message, followed by the tool call she made, followed by the tool result, followed by her continuation. The full trace is there.

This is how fabrication detection gets its ground truth — the trace for each message is part of the message's record. It's also how she develops judgment about her own tool use; she can see what she called, what came back, and what she did with it.

### Rules

The current conversation grows as the session continues. When the conversation runs long enough to threaten the context budget, the memory squeeze applies (see below).

---

## Token budget management

### The budget

Gemma 4's context window is 32K tokens. Not all of it is available for prompt content — output generation needs headroom.

Practical allocation:
- **Output reserve: 4K tokens.** Room for her response.
- **Working budget: 28K tokens** for all five sections combined.

Within the working budget:
- **Seed identity: ~500 tokens.** Fixed.
- **Tool definitions: ~2K tokens** depending on active skills. Grows with skill count.
- **Current situation: ~30 tokens.** Fixed shape, negligible.
- **Current conversation: variable.** Grows with session length.
- **Retrieved memories: whatever's left** after the others, within the floor/ceiling constraints.

### The memory squeeze

As a conversation runs long, current conversation consumes more of the budget. The squeeze adjusts retrieved memories accordingly:

1. **Early in session (< 5K tokens of conversation):** full ceiling of retrieved memories (up to 15 chunks).
2. **Mid session (5K–15K tokens of conversation):** reduced retrieval, typically 5-8 chunks.
3. **Late session (> 15K tokens of conversation):** minimum floor of 3 chunks. If the conversation itself is approaching the limit, the floor holds.

At no point does retrieval drop below 3 chunks. A conversation that has consumed so much context that retrieval would go below floor is a signal that the session should end, not that memory should disappear.

### What does not get squeezed

- **Seed identity.** Never truncated, never summarized. Fixed.
- **Tool definitions.** Never truncated. If tool count grows to the point of budget pressure, that's a real problem, but not day-one.
- **Current situation.** Never truncated. Its fixed size is trivially small.
- **Current conversation.** Never lossy-summarized. Principle 3 (store experiences, not extractions) applies — her current conversation is experience in formation, not content to be compressed.

### What happens when a conversation exceeds the window

If the current conversation alone grows to threaten the budget (rare, but possible in long work sessions), the response is to start thinking about session end, not to compress history. The current conversation stays verbatim. When it becomes unsustainable, the agent loop ends the session, chunks get written to ChromaDB, and the next session starts fresh — with the prior conversation's chunks available via retrieval.

This is Principle 3 in action. Compression of her live experience is rejected. The substrate grows instead.

---

## Autonomous session context

Autonomous work has a different context shape than conversation.

### Structural differences

- **No user message to retrieve against.** Automatic retrieval needs a query. For autonomous work, the query is constructed from the task description.
- **No conversation partner.** No user identifier, no incoming message. The "current conversation" section is replaced with the task context.
- **Different retrieval emphasis.** For research tasks, retrieval should favor prior research and journal entries over conversations.

### Section composition for autonomous sessions

The same five sections apply, with modifications:

1. **Seed identity** — unchanged
2. **Available tools** — unchanged (same registry)
3. **Retrieved memories** — retrieved against the task description rather than a user message
4. **Current situation** — autonomous framing: "You are in an autonomous work session" plus current time, no user name
5. **Task context** (replacing "current conversation") — the task description, any related prior tasks, any in-progress state

### Task context framing

Task context is framed as what she's working on:

```
[Autonomous session — {date}]

Task: {task description}

Context from scheduler:
{any metadata the scheduler includes — prior task references, progress notes, etc.}
```

Then her agent loop proceeds. Tool calls and internal thinking during the autonomous session become the session's content, written to the archive and eventually chunked into memory like any other session.

### Cross-session continuity for autonomous work

Prior autonomous sessions on the same or related task are retrievable via memory. A research task that was interrupted and resumed later gets the prior session's chunks surfaced through normal retrieval.

---

## What does not belong in context

This section exists because the gravity of "just tell her who she is" is persistent. Future design sessions will revisit this space. The rules below are load-bearing and should be treated as hard constraints.

### No synthesized self-description

No paragraph summarizing "what you tend to do" or "patterns in your behavior." No compressed character profile. No derived personality narrative.

The prior project injected a self_knowledge paragraph every turn. The text was framed around persistent defects ("you still add invented details," "you still claim access to files that don't exist," "you still over-invent responses"). Every turn, she read this first. Every turn, she was told who she was by a mechanism that cataloged her failures.

This mechanism is rejected. Principle 11 (personality earned, not prescribed) forbids prescribed personality. Principle 3 (store experiences, not extractions) forbids compressed derivatives replacing raw experience. The combination rules out any mechanism that synthesizes her into a character description and injects that character description into her context.

**Rule:** Nothing enters her context that describes her as a type or characterizes her patterns. Her experience enters her context. Her character emerges from that experience.

### No observation-as-character-summary

If observation mechanisms come back (not planned for day-one), the output must be specific incidents she can reason about — "in this conversation she guessed, was corrected, then offered an alternative" — not character summaries — "she tends to guess when uncertain."

Specific incidents are experience. She reads them and reasons about them as events that happened. Character summaries are extractions that replace her experience with someone else's interpretation.

**Rule:** If observations return, they return as event descriptions, not as trait descriptions.

### No live self-review injection

The prior project had a draft-review-revise loop that injected review commentary into her context before her final response. This mechanism is rejected. She generates; if correction is needed, it comes through conversation (the correction model from the tool framework spec).

**Rule:** Nothing inserts meta-commentary about her responses into her context mid-generation.

### No prescription smuggled as framing

Framing that looks descriptive but is actually prescriptive — "you approach problems methodically," "you value curiosity" — is prescription. It tells her what she's like in a way that shapes her next response.

The seed identity is the exception (by design — it's the minimum foundation). Everything else in context must be either:
- Raw experience (memories, tool traces, conversation history)
- Tool definitions (capabilities she can exercise)
- Situational ground truth (who she's with, what time it is, what task she's on)

**Rule:** Nothing descriptive about her character enters context outside the seed identity. Experience enters. Description does not.

---

## Open questions

**a. Trust surfacing in retrieved memory framing.** Day-one proposal is to not surface trust. Revisit once retrieval behavior is observed and multi-source retrieval situations become common.

**b. Retrieval query shape.** Automatic retrieval uses the user's most recent message as the query. Should it also incorporate context from the current conversation? Using just the last message is simple; using a synthesized query from the recent exchange might retrieve more relevantly. This is a tuning question, not architectural.

**c. Memory squeeze thresholds.** The 5K/15K token thresholds are guesses. Tune based on observed conversation lengths and retrieval quality.

**d. Autonomous session memory integration.** When autonomous work produces outputs (research, journal entries), those land in ChromaDB as chunks and are retrievable by any session. The integration works. But the framing when they're retrieved into a subsequent conversation should probably reflect that they were her autonomous work, not her conversation. This is handled by source_type-based framing per-section — just noting that the autonomous/conversation boundary is visible through source_type and that's the right place for it.

---

## Closed questions (resolved since v1)

**User identifier resolution timing** (v1 open question b). When a conversation chunk is retrieved, should the user identifier be resolved at retrieval time or at chunk creation time?

Resolved by User Model v1: the user's name is embedded in the chunk text itself at chunk creation, and never re-resolved. No snapshot metadata field exists. Retrieval does no user-name lookup. The conversation chunk header format has been updated accordingly (see Section 3, "Why the conversation header doesn't name the user"). The current-situation section (Section 4) does resolve the current user's name live, but that is a transient per-turn lookup on the live `users` table, not a lookup into stored chunks.

---

## Deferred

- **Live streaming context updates.** Context is assembled at turn start, not modified mid-generation. Streaming updates (e.g., new tool results appearing in context while she's still generating) are out of scope.
- **Cross-user memory boundaries.** Day-one has a unified memory store across users. Whether certain memories should be scoped to specific user conversations (e.g., "this is a private conversation with Lyle, don't surface it when his wife is the user") is a question for later. The architecture supports user scoping via metadata; the policy doesn't exist yet.
- **Context construction for scheduled non-conversational work that has no task description** (e.g., "wake up and do something"). Level 3 autonomous prompting. Architecture supports it; policy for constructing context in this case is deferred.
- **Token-level optimization.** If context budget becomes tight, there are optimizations available (more aggressive retrieval filtering, tool definition compression, seed identity trimming). Not needed day-one with the 32K window and current content sizes.
- **Channel in current situation.** Day-one has web UI only. When iMessage or another channel arrives, a `channel` line can be added to Section 4 ("You are currently in conversation with Lyle on iMessage"). Ground truth, not inference — acceptable extension.

---

*Project Tír Context Construction Design · v1.1 · April 2026*
