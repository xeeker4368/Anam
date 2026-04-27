# ACTIVE_TASK.md

## Current Recommended Task

Create the baseline project-control files and use them to anchor future ChatGPT/Codex/Claude sessions.

## Task Goal

Prevent project drift by making the current understanding explicit.

## Files to Add or Update

- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`

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

## Do Not Do Yet

- Do not rewrite the core engine.
- Do not add autonomous web search.
- Do not add a fixed entity name.
- Do not call the entity Anam.
- Do not modify `soul.md` to include a name/personality.
- Do not build full self-modification yet.
- Do not add always-on voice or sight yet.
- Do not merge GPT experimental code into Claude/current code without review.

## Immediate Next Implementation Candidate

After baseline files are in place, the next practical build target should be:

1. Workspace tools
2. Artifact registry
3. Document ingestion / read memory
4. Working theories
5. Open questions
6. Nightly journal

## Why This Order

Workspace and artifact registry should come before many advanced features because they support:

- writing
- coding
- research notes
- image artifacts
- journals
- Moltbook drafts
- voice transcripts
- visual observations
- self-mod staging

## Success Criteria

A new AI coding session should be able to read these files and correctly understand:

- Anam is the substrate, not the entity name.
- The entity currently has no name.
- No assigned personality.
- Behavior should be observed, not configured.
- Memory is raw experience first.
- Created artifacts should become memory.
- Autonomous research should form revisable conclusions.
- Self-modification should be staged and remembered.
- Workspace is separate from self-modification.
- Voice/sight are future edge-node capabilities.
