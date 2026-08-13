# NOW.md — Project Anam current state

> One page. Overwritten every session, never dated copies. If it's not here,
> it's in NORTH_STAR (why), DECISIONS (choices), BACKLOG (wants), or a changelog.
> Last updated: 2026-07-03 (reviewer Claude session).

## Waiting on Lyle

- [ ] Send `PLAN_BRIEF_probe_harness_v1.md` to CC (plan-mode); paste plan back to reviewer Claude
- [ ] Write the five probe questions (plain English, in `probe/questions.md` once CC's plan defines the format)
- [ ] Tell reviewer Claude how the two NORTH_STAR `[LYLE:]` markers were resolved (record in DECISIONS.md)
- [ ] Commit NOW.md + BACKLOG.md; archive old SESSION_HANDOFF_*.md files to `docs/archive/`; fold PROJECT_STATE.md into this file (delete it)

## Next up (in order)

1. **Probe harness** — brief written, awaiting CC plan → review → build → device test
2. **Registry/inventory reconciliation** — capabilities.py stays a safety-posture declaration; honest field semantics; FEATURE_INVENTORY.md carries built/tested truth
3. **Orphan recovery ×3** (`0b6acc0e`, `74641c53`, `92f127b9`) — BACK UP STORE FIRST; doubles as the final-chunk-with-split proof the embed fix never got
4. **Artifact retrieval-replay vector** (bug #3, queued since 06-26)
5. **D1 Ollama socket leak** (one-liner, hot path)
6. **Enable pass** (one planned phase): source de-weight (ships WITH any generation-enable — invariant) + flag flips (journal cadence, research, scheduler window) + SearXNG JSON-403 fix + verify agent-loop misreport fix before trusting `allow_agent_tool`
7. **Wipe & launch** — post-travel, ~45+ days out. Pre-wipe data is throwaway test corpus (kept deliberately for testing).

## Reviewer Claude's open IOUs (verification, no build)

- [ ] Nightly tick failure mode = stop-and-log, not retry-forever (gates unattended travel run)
- [ ] Agent-loop misreport fix (outer ok:true / inner ok:false) confirmed in tree

## Standing decisions in force

- Project, not experiment (NORTH_STAR rewritten 2026-07). Integrity discipline kept; purity discipline released.
- Nightly tick stays ENABLED during travel (Lyle's call; conditioned on the two IOUs above passing).
- Model: gemma4:26b (DECISIONS #24 stands; -mlx re-rejected 2026-07-03).
- Safety flags (`scheduler.*`, `allow_*`, `go_live`) are file-only, never UI-editable.
- Self-mod milestone status: pipeline exercised end-to-end; entity-ORIGINATED proposal not yet demonstrated (2026-05-09 proposal was AI-generated, operator-dictated).

## Recently done

- 2026-07-03: NORTH_STAR rewritten to project framing. Proposal provenance settled via prod DB. Both 06-28 commits verified at HEAD (3250240, 69c4645). Doc system simplified to NORTH_STAR / DECISIONS / NOW / BACKLOG / changelogs.
- 2026-06-28: embed sub-chunk fix committed; cross-user Option 1 committed (static-green only — watch for live bleed); feature map produced.

- 2026-08-12: Automated nightly backup is live (launchd, 2am, → ~/Backups/Anam on internal
disk). Closes the last hard blocker in FEATURE_INVENTORY.md around off-drive
backup. Verify it's still firing if you haven't checked `~/Backups/Anam/logs/`
in a while — no alerting exists if it silently stops.
