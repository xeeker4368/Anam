# DECISIONS.md

## 1. Project Identity

### Decision
The project/substrate is named Project Anam. The AI entity remains unnamed.

### Alternatives Rejected
- Assigning the entity a name now.
- Treating “Anam” as the entity’s personal name.

### Why
The experiment depends on observing whether identity emerges through continuity rather than being assigned.

### Status
Locked for go-live. Revisit only through explicit later self-representation process.

---

## 2. Entity Personality

### Decision
Do not hardcode a personality. Observe behavior over time.

### Alternatives Rejected
- Designing a fixed assistant persona.
- Writing personality traits into runtime guidance.

### Why
The project is testing emergent behavior under persistent context.

### Status
Locked in principle.

---

## 3. Memory Architecture

### Decision
Use a dual-store model:
- archive DB = durable record
- working DB/Chroma/FTS = queryable operational memory

### Alternatives Rejected
- Single mutable memory DB.
- Pure vector database memory.
- Summary-only memory.

### Why
Archive must preserve source truth. Working memory can be rebuilt.

### Status
Locked.

---

## 4. Retrieval

### Decision
Use hybrid retrieval: Chroma vectors + SQLite FTS/BM25 + RRF fusion.

### Alternatives Rejected
- Vector-only retrieval.
- Keyword-only retrieval.
- Hidden source-trust ranking multiplier.

### Why
Hybrid retrieval improves recall. Source trust must remain visible metadata, not hidden ranking.

### Status
Locked, tunable.

---

## 5. Source Trust

### Decision
`source_trust` remains metadata/debug only. It is not a hidden retrieval multiplier.

### Alternatives Rejected
- Down/up-ranking memories invisibly by source type.

### Why
Hidden trust multipliers distort continuity and make debugging harder.

### Status
Locked.

---

## 6. Source Labels

### Decision
All durable information should retain source/type/context metadata.

### Alternatives Rejected
- Flattening user statements, research notes, traces, and reflections into undifferentiated memory.

### Why
Anam must distinguish “Lyle said X,” “research note proposed X,” “source trace contained X,” and “system verified X.”

### Status
Locked.

---

## 7. Source Traces

### Decision
Source traces are audit/provenance sidecars. They are not indexed as primary content.

### Alternatives Rejected
- Indexing raw source traces into Chroma/FTS.
- Treating source traces as guidance/instructions.

### Why
Source traces may contain prompt injection, errors, or low-quality source text.

### Status
Locked.

---

## 8. Research Notes

### Decision
Research notes may be indexed. Raw source traces may not.

### Alternatives Rejected
- Indexing all collected data.
- Keeping all research unindexed.

### Why
Research notes are synthesized artifacts; traces are provenance.

### Status
Locked.

---

## 9. Bounded Research

### Decision
Research is manual/bounded and open-loop based. Scheduler can run at most one bounded research action if explicitly enabled.

### Alternatives Rejected
- Open-ended autonomous research.
- Background daemon research.
- Unlimited nightly tasks.

### Why
The project needs continuity without broad autonomy.

### Status
Locked for v1.

---

## 10. Scheduler

### Decision
Scheduler v1 is a one-shot CLI command, not a daemon.

### Alternatives Rejected
- Always-running background worker.
- Full autonomous scheduler.

### Why
A one-shot CLI is testable, auditable, and launchd/cron-ready later.

### Status
Locked for v1.

---

## 11. Scheduler Scope

### Decision
Scheduler v1 supports heartbeat and optional one model-only bounded research action.

### Alternatives Rejected
- Scheduler image generation.
- Scheduler web crawling.
- Scheduler Moltbook collection.
- Scheduler governance/code/guidance mutation.

### Why
Avoid broad autonomy before live continuity is stable.

### Status
Locked for v1.

---

## 12. Guidance / Soul Loading

### Decision
`soul.md` and operational guidance may shape runtime behavior, but they must not assign a fixed name/avatar/personality.

### Alternatives Rejected
- No seed guidance.
- Highly prescriptive persona file.

### Why
The system needs philosophical/operational boundaries without forcing identity.

### Status
Open to careful wording review before go-live.

---

## 13. Behavioral Guidance

### Decision
AI-suggested guidance changes require admin approval. AI can propose; admin approves.

### Alternatives Rejected
- Direct AI mutation of behavioral guidance.
- User-created proposal-author metadata.

### Why
Preserve emergence while preventing uncontrolled self-modification.

### Status
Locked.

---

## 14. Admin/User Role Model

### Decision
Two roles: admin and user. Lyle is admin.

### Alternatives Rejected
- Complex role model for v1.
- No role boundary.

### Why
Self-modification, governance, and code changes require admin control.

### Status
Locked for v1.

---

## 15. Trusted Household User Mode

### Decision
Use trusted-client `user_id` source attribution for Lyle and wife on LAN/VPN.

### Alternatives Rejected
- Full login/session auth before go-live.
- Single undifferentiated user.

### Why
Wife must be able to shape early continuity; public auth is not required for trusted household LAN/VPN.

### Status
Locked for go-live under LAN/VPN only.

---

## 16. Real Auth

### Decision
Real login/session auth is deferred.

### Alternatives Rejected
- Implementing full auth before go-live.

### Why
Trusted household model is accepted for current threat model.

### Status
Deferred; required before broader exposure.

---

## 17. API Secret

### Decision
`ANAM_API_SECRET` is shared-secret API protection, not per-user identity.

### Alternatives Rejected
- Treating API secret as login/session identity.

### Why
Current model is LAN/VPN trusted household protection only.

### Status
Locked for v1.

---

## 18. Frontend LAN Design

### Decision
Expose Vite frontend on LAN; keep backend bound to localhost and reached through Vite proxy.

### Alternatives Rejected
- Expose backend directly on LAN.
- Public internet exposure.

### Why
Allows iPhone access while limiting backend exposure.

### Status
Locked for go-live; CORS/proxy-only assumption should be documented/tested.

---

## 19. Image Generation Backend

### Decision
Use local ComfyUI as first image generation backend.

### Alternatives Rejected
- Cloud image generation.
- Agent-first image generation before backend proof.

### Why
Local, controllable, provenance-friendly.

### Status
Locked for v1.

---

## 20. Image Generation Role

### Decision
Generated images are ordinary media artifacts unless explicitly part of a future avatar/self-representation workflow.

### Alternatives Rejected
- Treat every generated face/image as identity.
- Let tool output imply “this is me.”

### Why
Self-representation must be intentional and reviewed.

### Status
Locked for v1.

---

## 21. Chat-Callable Tools

### Decision
Go-live tools safe for explicit user use should be callable from chat.

### Alternatives Rejected
- UI-only image generation.
- Admin-only media reference.

### Why
The AI must be able to use live capabilities through conversation.

### Status
Locked.

---

## 22. Chat Image Tool Gate

### Decision
`image_generate` is available only when image generation and agent tool access are both enabled.

### Alternatives Rejected
- Enable chat image generation by default.
- Scheduler/autonomous image generation.

### Why
Avoid unexpected media generation.

### Status
Locked for v1.

---

## 23. Media Reference

### Decision
Add `media_search` and `media_get` as active read-only tools.

### Alternatives Rejected
- Image generation without later reference/search.
- Raw file access from chat.

### Why
Anam must reference generated/uploaded media by title/id/prompt safely.

### Status
Locked.

---

## 24. Model Selection

### Decision
Primary go-live model candidate is normal `gemma4:26b`.

### Alternatives Rejected
- `qwen3.5:27b`: too slow with Anam-sized prompts.
- `qwen3.5:27b-mlx`: faster than Qwen normal, still too slow.
- `qwen3.5:9b`: better but still sluggish.
- `mistral-small3.2`: too slow.
- `gemma4:26b-mlx`: faster load/huge context, but text-only and less useful for image understanding.

### Why
`gemma4:26b` is fast enough, supports image input later, and handles Anam prompt sizes well.

### Status
Open only for temperature tuning, likely 0.20–0.25.

---

## 25. Model Temperature

### Decision
Default was 0.35. Lower-temp test target is 0.20–0.25.

### Alternatives Rejected
- Switch model solely to reduce sycophancy.
- Use abliterated/uncensored models for independence.

### Why
Lower temperature may reduce theatricality while preserving Gemma performance.

### Status
Open; final value pending.

---

## 26. Abliterated / Uncensored Models

### Decision
Do not use abliterated/Heretic-style models for go-live.

### Alternatives Rejected
- Use “uncensored” model to encourage disagreement.

### Why
Less refusal does not equal better independent judgment; could increase unsafe compliance.

### Status
Locked for go-live.

---

## 27. Reviewer Pattern

### Decision
Use plan-only before complex implementation; commit checkpoints after approved patches.

### Alternatives Rejected
- Let Codex implement broad changes without plan.
- Large multi-feature patches.

### Why
Recent complexity showed need for scoped patches and review gates.

### Status
Locked.

---

## 28. Runtime Files

### Decision
Runtime DB/log/workspace files should not be committed.

### Alternatives Rejected
- Commit current pre-live runtime state.

### Why
Pre-live state is test data and will be reset.

### Status
Locked; cleanup/untracking still needed.

---

## 29. Go-Live Reset

### Decision
Runbook exists. Reset command still required before live.

### Alternatives Rejected
- Manual destructive reset without guardrails.
- Go live with pre-live test data.

### Why
Live continuity must start clean but backed up.

### Status
Open blocker.

---

## 30. Interpretation / Temporal Runtime

### Decision
Design docs exist; runtime is deferred unless explicitly prioritized.

### Alternatives Rejected
- Block go-live on all interpretive/temporal runtime features.

### Why
Valuable, but scope-expanding.

### Status
Deferred.

---

## 31. Avatar / Self-Representation

### Decision
Deferred until explicit reviewed workflow.

### Alternatives Rejected
- Assign avatar before go-live.
- Let ordinary image generation become identity.

### Why
Name/avatar should emerge intentionally later.

### Status
Locked for go-live.
