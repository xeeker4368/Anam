# Project Documentation Checkpoint After Governance Hardening

## Summary
- Updated project-control docs to reflect the completed governance hardening checkpoint.
- Set the next active task to the first AI-generated behavioral guidance proposal path, design only.
- Recorded decisions around governance file handling, behavioral guidance proposal governance, API secret scope, raw experience preservation, and review-pass language.

## Files Changed
- `ACTIVE_TASK.md`
- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `DESIGN_RATIONALE.md`
- `changelog/2026-05-08-project-doc-checkpoint-governance-hardening.md`

## Behavior Changed
- Documentation now reflects current implementation state:
  - API secret local-network hardening exists.
  - Governance files are backed up/restored by allowlist.
  - Governance files are blocked from normal artifact ingestion.
  - `working.db` has `schema_versions` baseline support.
  - Behavioral guidance proposal UI is review-only.
  - `BEHAVIORAL_GUIDANCE.md` is not loaded into runtime context.
  - `soul.md` includes minimal disagreement permission.
- No runtime behavior changed.

## Tests/Checks Run
- `git diff --check`
- `rg -n "dream|forgetting|SELF_UNDERSTANDING|BEHAVIORAL_GUIDANCE|API secret|schema_versions|governance" ACTIVE_TASK.md PROJECT_STATE.md DECISIONS.md ROADMAP.md DESIGN_RATIONALE.md`
- `rg -n "You are Anam|entity is Anam|personality slider|fixed personality" ACTIVE_TASK.md PROJECT_STATE.md DECISIONS.md ROADMAP.md DESIGN_RATIONALE.md`

## Known Limitations
- `Project_Anam_Phase_3_Governance_Reflection_Roadmap.md` was not found in the repo and was not created.
- This checkpoint does not design or implement the AI-generated proposal path.

## Follow-Up Work
- Design the first AI-generated behavioral guidance proposal path into `working.db`.
- Keep proposal creation separate from admin review and file application.

## Project Anam Alignment Check
- Does not assign the entity a name or personality.
- Does not add active behavioral guidance entries.
- Does not modify `BEHAVIORAL_GUIDANCE.md`, `OPERATIONAL_GUIDANCE.md`, or `soul.md`.
- Preserves the distinction between Project Anam as substrate and the unnamed entity.
