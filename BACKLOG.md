# BACKLOG.md — Project Anam

> Wants with nowhere to go that isn't the codebase. One line each. Items leave
> this file only by entering NOW.md's queue through the plan-check loop.
> Not ordered; not commitments.

## UX / usability

- Config visibility panel (read-only): every effective setting + which layer set it (default/local/env). Small; do early — it's diagnostic tooling.
- Editable settings allowlist in UI: curated non-safety settings only (models per role, temperature, probe cadence, image workflow path, idle-close minutes); writes to local.toml only; visible restart-required state. Safety flags remain file-only.
- Chat-window document upload (currently sidebar-only). **Blocked until bug: artifact replay vector is fixed** — touches the same injection surface.
- [Lyle: add remaining UX "etc." items here, one line each]

## Code hygiene

- Delete `_FALLBACK_CONFIG` duplicate in tir/config.py; crash loudly if defaults.toml missing. (Two copies of one truth; caused the 2026-07 model-edit confusion.)

## Memory / recovery

- Source chunk `created_at` from the chunk's message timestamps (not `datetime.now()`) in the chunking pipeline, so `memory-repair` preserves original provenance. Currently recovery stamps recovery-time on the chunk envelope (display-only, not ranking) — acceptable for the pre-wipe throwaway orphans, NOT acceptable if memory-repair is ever run on post-launch data. Plan properly (touches `_store_chunk`/`_store_chunk_group`/`chunk_conversation_final`; affects live behavior or needs a recovery-only param) BEFORE any post-launch recovery.

## Image generation

- Quality tuning (brass-helmet fidelity): verify Anam passes prompt intact into ComfyUI workflow first (our bug if not), then checkpoint/workflow tuning (not our bug). TIMEBOX IT.

## Post-launch, post-baseline (dated deliberate variables per NORTH_STAR inv. 6)

- Moltbook introduction (dated)
- Vision, Option A (caption/extract to text)
- Self-image arc (abstract symbol, not face)
- Raw-gemma control arm / memoryless probe comparison
- Probe drift analysis & scoring (v1 only captures)

## Deferred from PROJECT_STATE.md (kept so nothing is lost when that file dies)

- Real login/session auth (prerequisite for any editable-settings UI beyond LAN trust)
- Launchd/cron automation for scheduler
- Frontend test harness
- Go-live reset command (this one likely promotes to NOW before wipe)

## Ops / backup

- [x] Automated off-drive backup — DONE 2026-08-13. launchd job `com.anam.backup`
  runs nightly at 2am, calling `tir.admin backup --destination ~/Backups/Anam`.
  Destination is the internal disk (not the external "Dock Storage" drive the
  project lives on) — genuine second-location redundancy, not just a copy on
  the same physical disk.
  - Wrapper: `/Volumes/Dock Storage/Anam/scripts/run_backup.sh` (invoked via
    `/bin/bash`, not the venv python directly — launchd/xpcproxy denies
    file-write-create to removable volumes for background jobs; routing through
    bash on the internal volume, with the backup *destination* also internal,
    sidesteps it. Root cause: macOS sandboxd `kTCCServiceSystemPolicyRemovableVolumes`.)
  - Plist: `~/Library/LaunchAgents/com.anam.backup.plist`
  - Logs: `~/Backups/Anam/logs/backup-launchd.log` (+ `-error.log`)
  - Known gap: `cmd_backup` still has no try/except (raw traceback on failure,
    not a clean error) — if the scheduled job ever fails, the log will show a
    traceback rather than a readable message. Still on the bug list, unfixed.

## Self-image / vision sequencing

- Self-image work should be sequenced with at least basic vision (Option A —
  captioning/extraction to text, per the existing plan), not before it.
  Reasoning (from a 2026-08-14 conversation): without any way to perceive a
  generated result, "the entity chose this image" and "the entity described
  something and never checked it against the outcome" are indistinguishable —
  a choice that can't be verified against its own result is a thinner claim
  than one that can. Vision closes that specific gap; it does NOT by itself
  resolve whether a stated self-image preference is durable vs. a one-off
  fluent answer — that still needs the same repeated-question-over-time
  discipline the identity probe already uses. Both are probably wanted
  eventually; this note is about sequencing, not about whether to do either.