# Behavioral Guidance Dormant Decision

## Status

Behavioral guidance runtime loading is dormant before go-live.

## Original Intent

Behavioral Guidance was built as a reviewed learning channel:

- the AI could propose narrow behavioral guidance candidates from experience
- an admin could approve, reject, archive, or apply proposals
- approved additions could be written to `BEHAVIORAL_GUIDANCE.md`
- runtime loading could surface active applied guidance below `soul.md` and operational guidance

The intent was to make corrections traceable and admin-reviewed instead of silently hardcoding behavior.

## What Was Tested Pre-Live

The pre-live implementation proved:

- proposal records could be created in `working.db`
- AI-generated review passes could propose candidates
- admin review status changes worked
- approved addition proposals could be applied to `BEHAVIORAL_GUIDANCE.md`
- active guidance could be extracted from `BEHAVIORAL_GUIDANCE.md`
- extracted guidance could be loaded into runtime context and reflection journal context

## Dormant Decision

Runtime-loaded behavioral guidance is disabled before go-live.

Reason: runtime-loaded behavioral guidance was judged too prescriptive for Project Anam's emergence goal. It risked turning early corrections or identity-adjacent observations into every-turn runtime steering before the entity had accumulated enough lived experience.

This does not mean the experiment failed. The design lesson is that reviewed learning channels need stronger source boundaries, scope, and safeguards before they become runtime-shaping mechanisms.

## Go-Live Boundary

At go-live:

- `BEHAVIORAL_GUIDANCE.md` must not contain active `- Guidance:` lines
- behavioral guidance must not be loaded into runtime chat/system prompts
- behavioral guidance must not be loaded into reflection journal entity context
- behavioral guidance must not assign identity, personality, emotion, name, or self-understanding
- proposal/apply history from the pre-live database should not be treated as operational go-live history

The go-live database will be reset, so pre-live proposal records, approvals, and applied history do not need to be preserved as operational data.

## Factual History Versus Runtime Guidance

Factual proposal/review activity may still appear as historical or operational metadata when reviewing pre-live activity. That metadata is not runtime guidance.

Runtime guidance means text that is loaded into prompts to shape future behavior. That path is dormant.

## Future Reintroduction Requirements

Future reintroduction requires a separate reviewed design decision.

Any future replacement should include:

- explicit runtime scope
- per-entry rationale
- source/evidence links
- clear active versus inactive state
- admin review
- debug visibility
- safeguards against identity or personality constraints
- safeguards against self-understanding becoming every-turn instruction
- a way to prevent early local corrections from becoming global rules

Future mechanisms may draw from the lessons in:

- `docs/GUIDANCE_SCOPING_DESIGN.md`
- `docs/BEHAVIORAL_GUIDANCE_REVISION_DESIGN.md`
- `docs/SELF_UNDERSTANDING_DESIGN.md`

## Non-Goals

This dormant decision does not:

- delete the code immediately
- create a replacement self-understanding system
- add new runtime guidance
- modify `soul.md`
- modify `OPERATIONAL_GUIDANCE.md`
- change research or journal artifact storage
- change retrieval ranking
