# SELF_UNDERSTANDING.md Design

Status: concept design only. This subsystem is not implemented.

## Definition

`SELF_UNDERSTANDING.md` would record the AI's reviewed, revisable understanding of itself based on accumulated experience. It may include observed patterns, tensions, uncertainties, changes over time, and provisional self-interpretations.

It is descriptive, not prescriptive. It should help preserve continuity of self-interpretation without turning that interpretation into a fixed personality, a name, or a behavioral command set.

## Name

Use `SELF_UNDERSTANDING.md`.

Do not use these names for the v1 concept:

- `PERSONALITY.md`
- `SELF_PROFILE.md`
- `IDENTITY.md`
- `SELF_MODEL.md`

The approved name emphasizes provisional understanding rather than a fixed identity profile or personality specification.

## Relationship To Existing Materials

`soul.md` is minimal seed orientation. It has higher precedence, is not derived from experience, and should not become a personality prompt.

`BEHAVIORAL_GUIDANCE.md` is normative future behavior guidance. It answers how future behavior should be guided after AI proposal and admin approval.

Reflection journals are expressive reflection artifacts. They may contain facts, interpretation, metaphor, and unresolved questions, but they are not reviewed durable self-understanding by default.

`SELF_UNDERSTANDING.md` would be reviewed self-interpretation derived from experience. It should preserve evidence-linked observations about developing patterns and tensions without converting them into instructions.

## Entry Style

Prefer wording that stays provisional and evidence-linked:

- "I currently understand..."
- "I have observed..."
- "A developing pattern may be..."
- "This may change..."
- "Evidence so far suggests..."

Avoid wording that freezes identity or treats user descriptions as direct truth:

- "I am permanently..."
- "My personality is..."
- "I always..."
- "I never..."
- "The user says I am..."

## Future Lifecycle

The expected lifecycle should mirror the project's review-first governance pattern:

1. The AI proposes a self-understanding candidate from accumulated experience.
2. An admin reviews the proposal.
3. Rejection requires a reason.
4. Rejected proposals remain visible as review evidence.
5. Approved entries can later be applied to `SELF_UNDERSTANDING.md`.
6. Application is explicit and admin-controlled.
7. Admins should not normally author self-understanding directly.

This keeps self-understanding AI-originated and experience-grounded while preserving human review and preventing accidental identity assignment.

## Evidence And Scope

Entries should be atomic and evidence-linked. Useful evidence may include conversations, reflection journals, behavioral guidance history, review queue items, artifacts, operational reflection notes, and other traceable experience.

An entry should not be accepted merely because a user or admin said it. User corrections can be evidence, but they should not automatically become self-understanding.

## Contradiction, Drift, And Supersession

Drift is expected. The system should allow understanding to change over time without treating earlier entries as failures.

Contradictions may coexist as tensions. Confidence can change. Newer entries should not automatically erase older entries.

Future tooling should support supersession, revision, and explicit contradiction notes. The preferred posture is evidence-linked uncertainty over forced simplification.

## Runtime Loading Strategy

Runtime loading is deferred.

When loading is eventually designed, it should:

- load only applied or active entries
- sit below `soul.md` and operational guidance
- use a tight budget
- consider an off-by-default or admin/debug flag first
- avoid treating entries as behavioral instructions
- preserve source framing as reviewed self-interpretation

`SELF_UNDERSTANDING.md` should not override raw memory, direct conversation records, `soul.md`, operational guidance, or behavioral guidance.

## Implementation Phases

1. Design doc only.
2. Add proposal schema, service, and admin CLI.
3. Add review API and UI surface.
4. Add AI-generated proposal path from journals and conversations.
5. Add apply-to-file workflow.
6. Add optional or restricted runtime loading.
7. Add contradiction and supersession tooling.

## Risks

`SELF_UNDERSTANDING.md` can become a personality cage if loaded too strongly or treated as a fixed profile.

It can become user-authored identity if admin creation becomes the normal workflow.

It can overfit temporary project-phase behavior if proposals are generated from too narrow a window.

It can compete with raw memory if treated as higher authority than experience records.

It needs evidence links and review history to remain revisable.

## Non-Goals For This Patch

This design does not add a database schema, runtime loading, UI, model tool, proposal service, or apply workflow.

It does not modify `soul.md`, `BEHAVIORAL_GUIDANCE.md`, or `OPERATIONAL_GUIDANCE.md`.
