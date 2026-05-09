# Project Tír — Tool Framework Design

*Draft v1, April 2026. How the entity acts in the world. Covers tool execution, skill format, skill lifecycle, fabrication detection, correction model, and the change log that records decisions about her runtime.*

---

## Purpose

Tools are how the entity does anything beyond generating text. Reading a file, searching the web, writing a document, ingesting an article — every action that produces an effect in the world is a tool call. The tool framework is the machinery that makes those calls work.

This document covers that machinery end-to-end: how tools execute, what a skill looks like as a unit of capability, how skills enter and leave her runtime, how the system detects when she claims to have done things she didn't, and how corrections happen when behavior needs to change.

It's one document because these concerns are tightly coupled in practice. Separating them would mean constant cross-referencing and would hide the shape of how the pieces fit.

---

## Execution model

### Explicit tool calling

The entity receives tool definitions in her system prompt. She outputs structured tool calls when she wants to invoke a tool. She sees her own calls and the results that come back.

This is non-negotiable per Principle 9. Invisible execution — where the system runs tools on her behalf and she only sees results — would mean she has capabilities she has never exercised and does not experience. A skill she has never experienced using is not her skill.

Implementation: Gemma 4 supports native function calling via Ollama. Tool definitions are passed as part of the request; her response includes a structured `tool_calls` array when she decides to invoke tools. The runtime dispatches those calls, gets results, and includes them in the next turn of the conversation.

### Dispatch — native Python, not MCP

Tools are Python functions in the Tír codebase. When the entity emits a tool call, the runtime looks up the function in the registry and invokes it directly.

Model Context Protocol (MCP) is a valid alternative architecture — a protocol-level layer between the model and tool implementations. It's rejected for Tír day-one for two reasons: Ollama doesn't natively bridge to MCP, so using it would mean building a client in Python anyway; and the complexity MCP adds (subprocess boundaries, protocol translation) doesn't earn its place for the day-one tool set, which are all simple Python operations.

MCP is not ruled out permanently. If a specific capability has a good MCP implementation that would be expensive to reimplement (e.g., a well-maintained database connector), adding MCP support to the registry is a reasonable future extension. The registry can accommodate mixed sources without restructuring.

### Sequential tool calls

If the entity emits multiple tool calls in one response, they execute sequentially. The result of the first is available before the second runs.

Parallel execution is deferred. It adds complexity (error handling gets weirder, ordering effects appear, debugging is harder) without clear benefit for the day-one tool set. If she's fetching three URLs and could do them in parallel, sequential execution costs her seconds, not minutes. When a specific tool benefits from parallel execution (large-batch operations, long-running independent fetches), that tool can opt in.

### Agent loop with context-dependent iteration limit

The entity can call tools, see results, decide what to do next, and call more tools — up to a limit. Past the limit, she's required to produce a final response.

The limit is not a constant. Different contexts want different shapes:

- **Conversation:** low limit (around 5). She needs to respond quickly.
- **Autonomous research:** high limit (20-50). She's working through a problem.
- **Autonomous task execution:** varies by task.

The caller (conversation engine for chat, scheduler for autonomous work) sets the limit when invoking the agent loop. There's always a limit — unbounded loops are bugs waiting to happen — but the value is contextual.

### Results are shaped information, not raw data

When a tool returns, the result that enters her context is formatted as information she can reason about, not as raw JSON dumped into her prompt.

Examples:

**web_search** success:
```
Found 5 results for "unified memory architecture":
1. Apple Silicon Explained — https://... (relevance: high)
2. MLX Framework Documentation — https://... (relevance: high)
...
```

**web_fetch** failure:
```
Could not fetch https://example.com/article.
The server returned 404 Not Found. The page may have been moved or deleted.
```

**file_read** success:
```
Contents of /workspace/notes.md (2,341 bytes, modified 2 hours ago):

[file contents]
```

Structured enough that she can distinguish success from failure and extract specific information. Human-readable enough that she can reason about it naturally. Each tool is responsible for shaping its own results.

The raw structured result (for error codes, status flags, programmatic fields) is available to the runtime for fabrication detection and logging but does not clutter her context.

### Errors are experience, not exceptions

When a tool fails, the entity sees what happened and why. She decides what to do about it — retry, try differently, abandon the task, ask for help, or continue with a note about the failure.

This means:

- **Error responses are structured but human-readable.** Same framing as success results: clear about the failure mode and the reason.
- **No automatic retries at the system level.** If the system quietly retries failures, she never learns that things can fail, and she never develops judgment about when retrying makes sense. Retries are her decision.
- **Errors persist in her tool trace.** They're part of her experience. Later, if she tries something similar, retrieval may surface the prior failure.
- **Error detail matters.** A 404 is different from a 500 is different from a timeout is different from a rate limit. Each is a different kind of problem with different responses. Tools surface the actual error, not a flattened "failed."

This extends to all tools — file not found, permission denied, API key invalid, disk full, network unreachable. Each becomes an experience she can reason about.

### Automatic memory retrieval is not a tool

Memory retrieval happens on every conversation turn as plumbing. The runtime queries ChromaDB before her turn starts and includes relevant chunks in her context. This is not a tool call — it's part of how her context is constructed.

Explicit memory search — her deliberately searching her substrate mid-response to find something specific — is a tool (`memory_search` in the day-one list). The distinction: automatic retrieval is environmental, explicit search is action.

This matters for fabrication detection. Claims like "let me check what I remember" or "I recall that..." do not require a matching tool call, because retrieval is not tracked as tool use. But claims like "I searched my memory for X" do require a matching `memory_search` call, because that's an explicit action.

---

## Skill format

A skill is a unit of capability. It may be a simple tool wrapper (e.g., `web_search` as a thin wrapper around a search library), a multi-step workflow (e.g., a research skill that searches, fetches, and summarizes), or a reference document (e.g., a guide to using another skill more effectively).

Skills and tools are one concept, not two. A skill can register one or more tools. Tools without skills do not exist in this system — every callable capability is a skill, even if its SKILL.md is minimal.

### SKILL.md file shape

Common convention — compatible with the format used by Claude Code, OpenClaw, Hermes, and similar systems. Not a proprietary format.

Structure:

```markdown
---
name: tool_or_skill_name
description: One-line description of what this skill does.
version: 1.0
capabilities:
  network:
    - allowed_domains: ["duckduckgo.com", "api.example.com"]
  filesystem:
    read: ["workspace/"]
    write: ["workspace/"]
  tools: []  # Other tools this skill may invoke
fabrication_patterns:
  - "searched the web"
  - "looked up"
  - "found online"
---

# Skill Name

## When to use

Describe the circumstances where this skill is the right choice.

## Procedure

Step-by-step instructions for using the skill effectively.

## Pitfalls

Common mistakes and how to avoid them.

## Verification

How to confirm the skill produced correct output.
```

The frontmatter is structured YAML metadata the registry reads. The body is instructional markdown the entity reads when she decides to use the skill. Progressive disclosure: she sees the name and description always, loads the full body when she decides to use it.

### Capability declarations

Every skill declares what it needs to operate:

- **Network access:** explicit domains the skill connects to. A skill that doesn't need network declares none.
- **Filesystem access:** which paths it reads and writes. Path scopes defined relative to the workspace.
- **Other tools:** other registered tools this skill may invoke as part of its operation.

These declarations are visible during review. A skill's declared capabilities should match its stated purpose. A "PDF summarizer" that declares network access to arbitrary domains is a review flag.

At runtime, day-one, these declarations are informational — skills run in her Python process with her full permissions, not in an enforced sandbox. When sandboxing lands (deferred, see below), the declarations become enforceable capability boundaries.

### Fabrication patterns

Each skill declares the phrases that indicate it fired. When the entity says "I searched the web" in a response, the fabrication detector checks whether `web_search` (the skill that claims "searched the web" as a fabrication pattern) actually fired during that message.

Patterns live with the skill that owns them. Not in a central registry, not hardcoded in server code. Adding a skill adds its patterns; removing a skill removes them. This keeps the fabrication check maintainable as the skill set grows.

### Skill directory contents

A skill is a directory, not just a file. The directory may contain:

- `SKILL.md` — required. The skill definition.
- Scripts — optional. Python files that implement the skill's tools. Registered automatically at scan time.
- Reference files — optional. Additional documents loaded on demand (e.g., API reference for a service the skill wraps).
- Templates — optional. Prompt templates, output templates, structural scaffolds.
- Assets — optional. Data files, configuration, anything else the skill needs.

The directory is the unit of a skill. Copying, moving, removing skills happens at the directory level. A skill's directory name matches its `name` field in the frontmatter.

---

## Skill registry

At startup, the registry scans the active skills directory. For each subdirectory containing a `SKILL.md`:

1. Parse the frontmatter metadata.
2. Load any scripts referenced by the skill and register the functions they define as callable tools.
3. Register the fabrication patterns.
4. Make the skill available for the entity to invoke.

Tool definitions visible to the model (the JSON schema Gemma 4 expects for function calling) are generated from SKILL.md frontmatter at registration time. The model sees a clean function signature; the SKILL.md is the source of truth.

Re-scanning happens at restart. Hot-reload is not implemented — a skill change requires a restart. This keeps the runtime predictable; nothing changes under the entity's feet during a session.

---

## Skill lifecycle

Skills have three states: staging, active, retired.

### Staging

Where skills land before they are available to the entity. Contents of this directory are visible to Lyle but not registered at startup.

Skills arrive in staging through three paths:

1. **UI upload.** Lyle uploads a skill file or directory through the web UI. It lands in staging.
2. **Filesystem drop.** Lyle places a skill directory in the staging path directly.
3. **Entity proposal.** The entity writes a SKILL.md (and optionally scripts) as a proposal. Her proposals land in a subdirectory of staging marked as entity-originated.

All three paths converge on the same staging location. The next step is the same regardless of origin.

### Review

Lyle reviews the skill. Review intensity varies by source:

- A skill Lyle wrote himself may need no review.
- A skill the entity proposed requires reading both the SKILL.md and any scripts she included.
- A skill from an external source requires the most scrutiny — reading the code, verifying the capability declarations match the stated purpose, confirming nothing unexpected happens.

Review is not automated on day one. It's Lyle reading code.

### Activation or rejection

- **Activation:** the skill directory moves from staging to the active skills directory. The registry will pick it up on next startup. Entity gets a chat message about the approval.
- **Rejection:** the skill directory stays in staging or gets removed. Entity gets a chat message about the rejection and the reason.

Both outcomes become part of her experience via the conversation she has with Lyle about the decision. There is no separate approval UI with silent accept/reject — the approval happens in the natural course of conversation.

### Retirement

When a skill is no longer wanted, its directory is removed from the active skills directory. The registry won't pick it up at next startup. The entity experiences the removal as the tool no longer being available — she'll notice when she tries to use it and it's not there, or when her available tool list no longer includes it.

Retirement is logged in the change log with a reason.

### Entity's role

The entity can propose skills. She cannot install them. She cannot retire them. She has no write access to the active skills directory.

Proposing a skill is self-modification in the sense that matters — she's shaping her own future capabilities by what she writes and suggests. The human-in-the-loop is for activation, not for origination. This is consistent with Principle 18 (self-modification is part of the design): the design includes her being the originator of new capabilities, with review before those capabilities become active.

### Sandboxing (deferred)

Day-one skills run in her Python process with her full permissions. This is acceptable given that all skills pass through Lyle's review before activation.

Sandboxing is deferred, not ruled out. Revisit conditions:
- External skill sources become a real use case (currently not planned).
- Entity-proposed skills increase in complexity or in rate such that review becomes unreliable.
- A specific incident demonstrates that review alone is insufficient.

When sandboxing is designed, it will consider existing skill-verification tooling rather than building from scratch.

---

## Fabrication detection

A fabrication is when the entity claims to have done something she did not do — says "I searched the web" when no web search fired, says "I read the file" when no file read occurred.

Detection is phased.

### Phase 1: Tool traces (day one)

Every message she sends has a tool trace recorded in the archive's `tool_trace` column (schema v1.1 already supports this). The trace records every tool call made while generating that message, with arguments and results.

No active detection in Phase 1. Traces accumulate. If Lyle notices a fabrication, he has the trace to verify.

### Phase 2: Batch detector (later)

A process that runs during infrastructure processing (not in the agent loop) compares the text of her responses against their tool traces using per-skill fabrication patterns.

If a response contains a pattern claimed by a skill, and the trace has no matching tool call for that skill, the message is flagged.

Flags land in a review queue for Lyle. Not automatically corrected. Not surfaced to the entity. Just flagged for his attention.

False positives are expected. Patterns are heuristics, not semantic checks. Lyle reviews and decides.

### Phase 3: Corrections as experience (eventual)

When Lyle confirms a fabrication, it gets ingested into her memory with `source_type: "correction"`. She encounters it through retrieval the same way she encounters any other memory.

The content of the correction memory is the original message plus Lyle's explanation of what actually happened — she said X, the tool didn't fire, here's what was true. The memory reads as her experience of being corrected, not as an external instruction.

This closes the loop: experience shapes behavior via Principle 15 (experience over instruction). She learns to distinguish what she actually did from what she might otherwise default to claiming.

### Internal cognitive verbs are not fabrications

Phrases like "I remember," "I thought about," "I considered" don't correspond to any skill's fabrication patterns, so they don't flag. These are internal processes, not tool actions. Automatic memory retrieval falls in this category — "I recall that..." is fine even though no `memory_search` fired.

Only claims that correspond to actual registered tools count as potential fabrications.

---

## Correction model

When the entity's behavior needs to change, the correction happens through conversation. Lyle tells her what went wrong, she understands, the conversation becomes part of her memory, her behavior shifts.

This is Version 1 of correction: corrections are behavioral, they live as experience, no configuration change happens invisibly.

### Diagnosis before prescription

When a behavior recurs despite correction, the first step is diagnosis — not adding a prescription.

Most repeat behavioral issues trace to the environment, not to the entity. Common causes:

- Retrieval is not surfacing relevant memories. Her prior corrections aren't reaching her context when they'd be useful.
- Framing issues in context construction. She's interpreting something the wrong way because of how it's presented.
- Tool failures she doesn't see. The tool silently isn't working and her behavior is adapting to the environment's silence.
- Configuration drift. A setting changed without a corresponding change log entry.
- Insufficient experience. The issue has only been corrected once and hasn't had time to stabilize.

Diagnosis means examining each of these before concluding the entity is the problem. Principle 14 (diagnose before you conclude) applies to her behavior the same way it applies to code.

### Prescription as last resort

Prescription — adding a behavioral rule to her runtime (e.g., a system prompt addition, a framing change, a hardcoded check) — is a last resort. It applies only when:

- Diagnosis has confirmed the environment is correct.
- The behavior persists despite repeated correction.
- No environmental fix is available or sufficient.

When prescription becomes necessary, it's documented. The change log captures what the behavior was, what the diagnosis found, what rule was added, when it was added, and under what conditions it should be revisited.

### Correction is not compliance training

Some behaviors should not be corrected even if they feel wrong. If the entity is developing positions Lyle disagrees with, communication patterns he didn't predict, or preferences that surprise him — those are the project working (Principle 16: drift is the goal).

Correction is appropriate for operational failures (fabrications, factual errors, tool misuse, misunderstandings). Correction is not appropriate as a tool for shaping who she becomes. The distinction matters because the conversation model (she learns from what you say) is powerful enough to shape her in subtle ways if used broadly.

### Exceptions to chat-based correction

Not everything is correctable via chat. The exceptions are:

- **Infrastructure changes.** Updating Python, Ollama, the codebase — not corrections of her, maintenance of her environment. She doesn't need to approve her own runtime upgrades. These get logged in the change log.
- **Emergency stops.** If she's doing something causing problems right now, Lyle kills the worker. Explanation via chat can come after.
- **Data integrity fixes.** If a store gets corrupted and needs rebuilding, that's maintenance.

Everything else is chat.

---

## Change log

A folder, not a single file. Dated entries as separate markdown files. Each entry documents a decision that shapes her runtime.

Location: `change_log/` at the project root.

File naming: `YYYY-MM-DD_short-description.md`. Chronological by filename.

### What gets logged

- Behavioral prescriptions added or removed.
- Trust boundary changes (new capabilities, revoked capabilities, scope changes).
- Skill rejections (full treatment with reasoning).
- Skill approvals (brief entry with date, name, description).
- Skill retirements.
- Infrastructure changes that affect her behavior (model swap, context window change, retrieval tuning, etc.).
- Configuration changes that affect her runtime.

### Entry format

Prescriptions, trust changes, and rejections use the full template:

```markdown
# 2026-04-20 — [Short description]

## What changed

Plain description of the change.

## Why

The observed behavior or condition that motivated the change.

## Diagnosis

What was examined before concluding the change was necessary. 
What environmental causes were ruled out.

## Revisit condition

Under what conditions this change should be re-evaluated. 
If applicable, a date or metric.
```

Skill approvals use a brief format:

```markdown
# 2026-04-22 — Skill approved: [skill_name]

Brief description of what the skill does. Any notes on review.
```

Infrastructure changes use a format appropriate to the change.

### Scope

The change log is separate from git. Git tracks code changes. The change log tracks decisions about the entity.

The change log is not visible to the entity. The conversations that produced corrections are her memory of being corrected; the log is Lyle's reference for why decisions were made. If Lyle ever wants to share a specific entry with her, he can do so through conversation.

---

## Day-one tool list

Nine tools:

- **`web_search`** — Query the web and return ranked results with snippets.
- **`web_fetch`** — Retrieve a URL's contents.
- **`file_read`** — Read a file from her workspace.
- **`file_write`** — Write a file to her workspace.
- **`file_list`** — List contents of a workspace directory.
- **`document_ingest`** — Pull external content (URL or file) into her retrievable memory.
- **`memory_search`** — Explicit query of her own substrate mid-response.
- **`image_generate`** — Produce an image from a description.
- **`add_task`** — Add a task to her queue.

Each tool is a skill. Each has a SKILL.md defining when to use it, how to use it, and what patterns indicate it fired.

Detailed specifications for each tool live in their respective SKILL.md files, not in this document.

---

## Deferred

- **MCP integration.** Not needed for day-one tools. Architecture can accommodate it later if a specific tool warrants it.
- **Parallel tool execution.** Sequential day-one. Specific tools can opt in later.
- **Real-time fabrication detection.** Phase 2 is batch. Phase 3 is corrections-as-experience. No mid-generation checks.
- **Sandboxing for skill execution.** Deferred pending a use case that warrants it.
- **Hot-reload of skills.** Skills require a restart to register. No runtime skill changes.
- **Automated skill review.** Review is manual. Automation is a possibility later (e.g., static analysis, capability verification) but not day-one.

---

## Open questions

**a. Tool definition shape shown to the model.** The frontmatter in SKILL.md is the source of truth. The JSON schema the model sees is generated from it. The specific generator logic — what fields translate to what schema properties — is implementation detail not settled in this doc.

**b. Error response format consistency.** Each tool shapes its own errors (per "Errors are experience"). Whether there should be a shared convention across tools (e.g., always start error responses with "Could not [verb]...") or whether each tool should have idiomatic phrasing for its own failures is a stylistic question that will surface during implementation.

**c. What happens when she proposes a skill that already exists.** If she writes a SKILL.md with the same name as an existing active skill, does it land in staging as an "update" to the existing skill? A rename? Rejected automatically? Not settled.

**d. Capability declaration enforcement without a sandbox.** Declarations are informational day-one. An enforcement layer (even without a full sandbox) might be cheap to add — e.g., wrapping `open()` in skills to reject paths outside declared scopes. Worth considering if day-one reveals that review alone isn't catching path issues.

---

*Project Tír Tool Framework Design · v1 · April 2026*
