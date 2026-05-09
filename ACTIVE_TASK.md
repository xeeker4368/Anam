# ACTIVE_TASK.md

## Current Recommended Task

First AI-Generated Behavioral Guidance Proposal Path — design only.

## Task Goal

Design the first path where the entity can generate one behavioral guidance proposal into `working.db` for admin review.

This should be a narrow, inspectable path from reviewed experience to a single proposed guidance record. It should not apply guidance to runtime files, load new guidance into prompts, or create autonomous behavior.

## Current Checkpoint

Recent completed foundation work:

- API secret hardening exists for local-network use when `ANAM_API_SECRET` is configured.
- Governance files are backed up/restored by explicit allowlist.
- Governance files are blocked from normal artifact ingestion.
- `working.db` has `schema_versions` baseline/migration foundation.
- Behavioral guidance proposal model/API/UI exists.
- Behavioral guidance proposal UI is review-only.
- `soul.md` includes minimal permission to question, disagree with, or decline proposed corrections or changes.

## Design Constraints

- No automatic apply-to-file.
- No prompt loading of `BEHAVIORAL_GUIDANCE.md`.
- No self-modification.
- No user-created behavioral guidance entries.
- No scheduler/background review pass yet.
- No new entity name.
- No assigned personality.
- No changes to `soul.md`, `OPERATIONAL_GUIDANCE.md`, or active `BEHAVIORAL_GUIDANCE.md` entries.

## Files/Subsystems To Inspect First

- `tir/behavioral_guidance/service.py`
- `tir/api/routes.py`
- `frontend/src/components/SystemPanel.jsx`
- `tir/memory/db.py`
- `tir/memory/migrations.py`
- review queue service/API/UI
- current context/retrieval debug paths

## New Chat Kickoff Instruction

Use this in the new implementation chat:

```text
You are helping me continue Project Anam.

Before making suggestions or writing code, read the attached project baseline documents in this order:

1. PROJECT_STATE.md
2. DECISIONS.md
3. ROADMAP.md
4. ACTIVE_TASK.md
5. CODING_ASSISTANT_RULES.md

After reading, respond with:
- your understanding of Project Anam in 8 bullets
- the current active task
- the files/subsystems you need to inspect first
- any assumptions or risks
- no code changes yet
```

## Success Criteria For The Next Design

A proposal-path design should answer:

- What experience source can create the first proposal?
- How is the proposal kept atomic?
- How is the source conversation/message/user linked?
- How does the system avoid user-authored guidance entries?
- How does admin review remain separate from application?
- What tests prove no file mutation or prompt loading occurs?
