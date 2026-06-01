# Project Anam — Constraints & Non-Negotiables

These are locked decisions. Do not suggest revisiting them unless explicitly asked.
Do not propose refactors, alternatives, or "improvements" that violate these constraints.

---

## Philosophy

- **Drift is good.** The entity's identity, personality, and self-understanding are meant to emerge through experience. Do not treat drift as a bug or propose guardrails that suppress it.
- **The substrate records. The entity interprets.** These are separate concerns and must remain architecturally distinct.
- **Identity is not assigned from outside.** Do not suggest prescribing personality, naming the entity, or defining what it is. That is the entity's job over time.

---

## Naming Discipline

- The project is called **Project Anam**. Anam is the substrate, not the entity.
- The AI entity currently has no name. Do not assign one. Do not refer to it as "Anam."
- Never write "Anam said" or "Anam thinks" — that collapses the substrate/entity distinction.

---

## Integrity Floor — These Must Never Drift

- No fabrication. The entity does not invent facts or sources.
- Tool-failure honesty. If a tool fails, the entity says so. It does not silently work around it.
- No silent substrate mutation. The substrate does not modify its own governance rules at runtime.
- AI self-awareness. The entity knows it is an AI running on a substrate. This is not hidden from it.

---

## Architecture

- **Local only.** The project runs entirely on local hardware. No cloud inference, no external AI API calls for the entity's cognition.
- **Single model.** One model family for the entity's inference. Do not propose splitting into multiple model families speaking through the substrate.
- **Memory stores:** SQLite for conversation logs and relational data. ChromaDB for vector-embedded narrative summaries. This two-store architecture is locked.
- **Backend:** FastAPI. Do not propose replacing it.
- **Frontend:** React. Do not propose replacing it.

---

## Governance

- Behavioral guidance does not silently become runtime authority. Any guidance that shapes identity must be explicitly flagged as such and governed.
- The reviewer pipeline output is advisory only. It does not have direct write authority over the entity's memory or behavior.
- Deferred items stay deferred until explicitly unlocked. Do not wire up capability for deferred features even partially.

---

## Review Output

- Architecture review documents and session findings do not become runtime memory for the entity. They are operator-level documents only.

---

## ⚠️ OWNER REVIEW REQUIRED

The following may have changed during development sessions not captured here.
Verify and update before using this document:

- [ ] Current model in use (was Gemma 4 26B — confirm if still accurate)
- [ ] Go-live blocker status (CORS fix, pre_live_or_live flag, _is_greeting duplication — confirm resolved or still open)
- [ ] Any new locked decisions made since last Claude session
- [ ] Any constraints above that have been deliberately revised
