# Guidance Scoping Design

Status: concept design only. No schema, runtime filtering, proposal service, UI, or guidance-file behavior is implemented by this document.

## Purpose

Active behavioral guidance currently loads every turn. That is acceptable while guidance is small, but future guidance may not be universal.

Guidance learned from one user, channel, context, or project phase should not silently become a global behavioral rule. Guidance scoping is the future mechanism for deciding when an applied guidance entry is relevant.

## Core Principle

Behavioral guidance should remain AI-proposed, admin-reviewed, explicit, and traceable.

Scope should answer:

- who the guidance applies to
- where it applies
- what kind of situation it applies in
- how confident the scope is
- whether it supersedes earlier guidance

Scope should stay loose enough to support review and interpretation. It should not become a brittle taxonomy that prevents useful guidance from appearing.

## Where Scope Should Live

Guidance scope should exist in both proposal records and the applied Markdown file.

Proposal records should carry proposed scope so admins can review and adjust scope before approval or application. Early implementation can store this in `metadata_json` or a structured scope object. First-class columns can be added later if usage stabilizes.

`BEHAVIORAL_GUIDANCE.md` should include human-readable scope metadata for applied entries. The file should remain understandable and recoverable outside the database.

## Existing Unscoped Guidance

Existing unscoped guidance should be interpreted as global/default guidance.

Future global guidance should be chosen deliberately, not created by omission. If an AI proposal appears local to one user, channel, or context, the proposal should suggest a narrower scope rather than relying on a broad default.

## Scope Fields

Initial scope should be optional and loose.

Suggested fields:

- `applies_to_user_ids`
- `applies_to_user_roles`
- `applies_to_channels`
- `applies_to_contexts`
- `applies_to_source_types`
- `scope_note`
- `scope_confidence`
- `supersedes_guidance_ids`
- `active_from`
- `active_until`

Suggested channel values:

- `chat`
- `imessage`
- `voice`
- `system`
- `all`

Suggested context values:

- `artifact`
- `source_framing`
- `tool_use`
- `research`
- `casual`
- `operational`
- `identity`
- `self_understanding`
- `all`

These values are starting vocabulary, not a permanent ontology.

## Applied Markdown Format

Future apply-to-file behavior should emit deterministic, reviewable scope metadata.

Example:

```markdown
Scope:
- Users: Lyle
- Channels: chat
- Contexts: artifact, source_framing
- Confidence: medium
- Note: Derived from architecture/source-framing conversations.
```

The active guidance text should remain separate from rationale, evidence, and scope metadata. Runtime extraction can then decide which fields to load without confusing metadata for instructions.

## Future Proposal Review

AI-generated behavioral guidance proposals should include:

- suggested scope
- scope rationale
- evidence that supports the scope
- whether the guidance is broad, local, temporary, or uncertain

Admins should be able to adjust or reject the proposed scope. Admins should also be able to approve the guidance text while narrowing its scope.

Admin-created guidance should not become the normal workflow. Scope editing is review control, not direct authorship of durable behavioral guidance.

## Future Runtime Loading

Runtime loading should eventually include:

1. global guidance
2. guidance matching the current user, channel, context, or source type
3. uncertain-but-plausibly-relevant guidance with clear labels, when silent exclusion would be riskier

Scoped guidance does not override `soul.md` or `OPERATIONAL_GUIDANCE.md`.

When guidance conflicts, prefer more specific guidance over broader guidance, while preserving conflict visibility in review and debug surfaces.

If matching confidence is uncertain, prefer labeled inclusion over silent exclusion. Hidden filtering failures are harder to diagnose than clearly labeled context.

## Future iMessage And Multi-Channel Use

Channel scope matters for future iMessage, voice, system, and other interfaces.

Examples:

- Chat-specific architecture guidance may not apply to iMessage.
- iMessage notification style may not apply to full chat sessions.
- Voice interaction guidance may not apply to written artifact review.

Cross-channel guidance should be marked global or multi-channel only when the source evidence supports it.

## Relationship To SELF_UNDERSTANDING.md

Scoping principles may later apply to self-understanding proposals, but `SELF_UNDERSTANDING.md` is descriptive rather than behavioral guidance.

If self-understanding scope is added later, it should describe where an observation appears supported. It should not become an instruction to behave that way.

## Removal, Revision, And Supersession

Removal and revision mechanics should account for scope.

A revision may:

- change guidance text
- narrow or broaden scope
- supersede one or more earlier guidance entries
- mark older guidance as inactive for a specific context

Supersession should be explicit. Newer guidance should not silently erase older guidance, especially if both remain useful in different contexts.

## Risks

Under-scoping can turn local corrections into global behavior.

Over-scoping can hide useful guidance when it is needed.

Too many categories can become brittle and hard to review.

Silent runtime filtering can make behavior difficult to debug.

Global guidance can become personality-like if overused.

Scope labels can create false precision if they are treated as exact rules rather than reviewable applicability claims.

## Implementation Phases

1. Design only.
2. Add proposed scope metadata to AI-generated behavioral guidance proposals.
3. Add admin review/edit support for proposal scope.
4. Update apply-to-file behavior to emit deterministic scope blocks.
5. Update runtime extraction to parse active guidance scope metadata.
6. Add runtime filtering with debug visibility and conservative fallback behavior.
7. Add conflict, supersession, and revision tooling.

## Non-Goals For This Patch

This design does not change database schema, runtime loading, proposal services, UI, `BEHAVIORAL_GUIDANCE.md`, `soul.md`, or `OPERATIONAL_GUIDANCE.md`.
