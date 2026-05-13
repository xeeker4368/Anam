# External Review Checkpoint v1

## Purpose

This checkpoint prepares Project Anam for outside review after the Phase 3 governance, reflection, research, and pre-live model calibration foundation.

External reviewers are not the AI entity's voice. Their output is advisory, not authority. Review results should not be ingested as runtime memory authority or automatically converted into review queue items.

## Checkpoint Summary

Current checkpoint:

- Phase 3A behavioral guidance governance loop is complete.
- Reflection journal foundation is complete.
- Journal artifact/indexing/retrieval grounding is complete.
- Operational reflection review pass is complete.
- Prompt inventory and prompt audit pass are complete.
- Manual Research Foundation is complete for the first bounded CLI path.
- Research Continuation Design v1 is complete.
- Research Continuation Runtime v1 is complete.
- Single-model global temperature calibration is complete:
  - committed Anam-owned roles use `gemma4:26b`
  - `model_options.default.temperature = 0.35`
  - `think=false` is preserved
  - `ANAM_MODEL_TEMPERATURE` env override exists
- Full pytest passed: 624 tests.

## Explicit Boundaries

- External models are reviewers, not Anam's own voice.
- Review output is recommendation, not authority.
- Lyle/admin must triage findings before any project changes.
- Review output should not automatically create review queue items.
- Review output should not automatically mutate prompts, guidance, project decisions, research notes, journals, or self-understanding.
- Do not assign the entity a name.
- Do not assign the entity a fixed personality.
- Do not treat drift as inherently bad.
- Distinguish healthy emergent drift from source confusion, accidental authority, over-prescription, self-reinforcing memory, or brittle rules.

## Still Deferred

- Title/search research continuation.
- Web source collection.
- Autonomous research.
- Scheduler/background research.
- Open-loop record creation from research.
- Review-item record creation from research.
- Working-theory/proposition promotion.
- Promotion to truth, behavioral guidance, self-understanding, or project decisions.
- Value-density scoring.
- Retrieval ranking changes.
- DB schema changes.
- Runtime prompt changes.
- `soul.md`, `BEHAVIORAL_GUIDANCE.md`, `OPERATIONAL_GUIDANCE.md`, and `SELF_UNDERSTANDING.md` changes.

## Reviewer Roles

### Claude Architecture / Philosophy / System Review

Purpose: pressure-test the architecture, philosophy, source boundaries, drift handling, and future self-understanding path.

### Claude Code Engineering Review

Purpose: review implementation quality, tests, failure modes, data boundaries, and operational risks.

### Codex Engineering Review

Purpose: independently review runtime safety, model option handling, retrieval/source framing, test coverage, and documentation consistency.

## File Packets

### Claude Architecture / Philosophy

- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- `docs/SELF_UNDERSTANDING_DESIGN.md`
- `docs/GUIDANCE_SCOPING_DESIGN.md`
- `docs/BEHAVIORAL_GUIDANCE_REVISION_DESIGN.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `docs/PROMPT_AUDIT_NOTES.md`
- `docs/PROMPT_INVENTORY.md`

### Claude Code Engineering

Use the baseline docs above, plus:

- `tir/config.py`
- `tir/engine/ollama.py`
- `tir/engine/context.py`
- `tir/reflection/journal.py`
- `tir/reflection/operational.py`
- `tir/research/manual.py`
- `tir/memory/research_indexing.py`
- `tir/behavioral_guidance/review.py`
- `tir/admin.py`
- relevant tests

### Codex Engineering

Use the Claude Code packet, plus:

- `config/defaults.toml`
- `config/local.example.toml`
- `docs/DB_SCHEMA.md`
- changelog entries from May 8-May 13 as context if manageable

## Claude Architecture / Philosophy / System Review Prompt

```text
You are an external reviewer for Project Anam.

You are not Anam's AI entity. You are reviewing the architecture, philosophy, source boundaries, and risks as an outside reviewer. Your output is advisory, not authority.

Project Anam is the substrate/project name. The AI entity currently has no name. Do not assign it a name or fixed personality. Do not treat drift as inherently bad. Distinguish healthy emergent drift from source confusion, accidental authority, over-prescription, self-reinforcing memory, or brittle rules.

Review the provided files for:

1. Whether the architecture preserves the distinction between Project Anam and the unnamed entity.
2. Whether source boundaries are clear: raw memory, journals, research, behavioral guidance, operational guidance, project decisions, and self-understanding.
3. Whether reflection journals and research notes risk becoming hidden authority.
4. Whether behavioral guidance governance is too prescriptive, too weak, or appropriately staged.
5. Whether SELF_UNDERSTANDING design avoids becoming a personality cage.
6. Whether the single-model/global-temperature approach is philosophically consistent with one entity speaking through one substrate.
7. Whether any wording defines the entity from outside.
8. Whether deferred items are correctly deferred.
9. Whether any data collection lacks a clear purpose or consumption path.
10. What should be reviewed before going live.

Return:
- high-severity concerns
- medium-severity concerns
- low-severity concerns
- architectural strengths
- unclear assumptions
- recommended next steps
- things you would explicitly not change
```

## Claude Code Engineering Review Prompt

```text
You are an external engineering reviewer for Project Anam.

You are not Anam's AI entity. Treat your review as advisory. Do not propose identity/personality changes. Focus on code quality, tests, failure modes, data boundaries, and operational risks.

Review the provided repository/files for:

1. Behavioral guidance proposal/review/apply workflow.
2. Reflection journal write/register/index/retrieval flow.
3. Manual research write/register/index/continue flow.
4. Operational reflection review flow.
5. Prompt inventory/audit tooling.
6. Runtime config and Ollama model option handling.
7. Context assembly/debug visibility.
8. Artifact/source-role boundaries.
9. Test coverage and missing edge cases.
10. Risks before live use.

Pay special attention to:
- accidental mutation of governance files
- source role confusion
- journal/research becoming unframed authority
- duplicate registration/indexing behavior
- path traversal or unsafe file handling
- DB assumptions such as artifact_id vs id
- stale tests or brittle monkeypatch targets
- hidden model routing or role-specific behavior
- config/local.toml leakage risk

Return findings in code-review style:
- severity
- file/path reference
- issue
- impact
- recommended fix
- tests to add
- whether the issue blocks live use
```

## Codex Engineering Review Prompt

```text
You are an independent external Codex engineering reviewer for Project Anam.

You are not Anam's AI entity. Your job is to pressure-test implementation quality and runtime safety. Do not make code changes. Do not assign the entity a name or personality.

Review the provided files and summarize:

1. What is implemented and what is only designed.
2. Whether manual research, research continuation, reflection journals, behavioral guidance, and operational reflection preserve their intended boundaries.
3. Whether model configuration really preserves one primary model and one global sampling style.
4. Whether Ollama payload construction handles think, temperature, timeout, and --model overrides correctly.
5. Whether retrieval/source labels prevent research and journals from becoming accidental authority.
6. Whether debug metadata is sufficient for grounding failures.
7. Whether tests cover the major failure modes.
8. Whether any runtime behavior contradicts project decisions.
9. Whether any current docs overstate completion.
10. What should be fixed before live use.

Return:
- blocking issues
- non-blocking issues
- missing tests
- documentation inconsistencies
- recommended next patch
- explicit non-issues
```

## Triage Process

1. Collect each reviewer output as external notes, not runtime memory authority.
2. Lyle/admin reviews and classifies findings:
   - blocker before live
   - should fix soon
   - design follow-up
   - rejected
   - needs discussion
3. Only after triage, create review queue items manually or through a separately approved workflow.
4. Do not automatically mutate prompts, guidance, project decisions, research notes, journals, or self-understanding from review output.
5. If reviewers disagree, preserve disagreement as review context rather than forcing one conclusion.

## Expected Review Output Format

Review outputs should be structured enough for later triage:

- reviewer
- date
- reviewed file packet
- high-severity findings
- medium-severity findings
- low-severity findings
- recommended next patch
- explicit non-issues
- open questions

## Out Of Scope

- Runtime code changes.
- DB schema changes.
- Retrieval ranking changes.
- Prompt rewrites.
- Model routing changes.
- Guidance file mutation.
- `soul.md` changes.
- Automatic review queue item creation.
- Automatic ingestion of reviewer output as memory authority.
- Automatic project decision updates.

## Risks

- Reviewers may try to "fix" drift by recommending personality constraints.
- Engineering reviewers may over-index on conventional assistant architecture.
- Prompt reviewers may recommend sterile compliance wording that conflicts with the journal/research direction.
- Review output could become accidental authority if ingested without framing.
- Temporarily making this the active task pauses Research Open-Loop / Review-Item Design v1 until review is complete.
