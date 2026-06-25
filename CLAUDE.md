@AGENTS.md
@CODING_ASSISTANT_RULES.md

# Project Anam — CC Working Rules

## Read first, every session

Before doing anything else, read `NORTH_STAR.md` in the project root. It is the
project's intent and the invariants no change may violate. If a task in front of
you conflicts with it, stop and surface the conflict rather than proceeding.

Document homes — do not mix:
- intent → NORTH_STAR.md
- decisions + rationale → DECISIONS.md
- current status → latest SESSION_HANDOFF
- tasks → roadmap

## Claude Code
- Default to plan mode. Do not edit, create, or delete files until I approve a plan.
- After an approved patch: write the changelog entry, then stop. Do not commit.
