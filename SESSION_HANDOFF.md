# SESSION_HANDOFF.md

Read this first.

## What Project Anam Is

Project Anam is a local AI substrate for testing whether persistent, source-labeled memory plus tools, reflection, bounded research, and time produce different long-term behavior. The project is called Anam. The AI entity is intentionally unnamed.

## Core Philosophy

- Do not assign the entity a name.
- Do not assign the entity an avatar.
- Do not hardcode a personality.
- The AI should know it is an AI.
- Drift is allowed; unsafe or source-confused drift is not.
- Memory must preserve source boundaries.
- Lyle’s statements are important inputs, not automatic truth.
- Tools should be honest and bounded.
- Self-representation comes later through explicit reviewed workflow.

## Current Architecture

- Backend: Python API under `tir/`.
- Frontend: React/Vite under `frontend/`.
- Runtime: Ollama local models.
- Current model direction: normal `gemma4:26b`, likely temp 0.20–0.25, `think=false`.
- Memory:
  - SQLite archive DB = durable record.
  - SQLite working DB + FTS5 + Chroma = operational retrieval.
- Retrieval:
  - Chroma + FTS/BM25 + RRF.
  - Source trust metadata only.
- Tools:
  - memory search
  - media search/get
  - config-gated image generation
- Image generation:
  - ComfyUI local backend.
  - Web UI and chat-callable tool exist.
  - Generated images are ordinary media artifacts.
- Scheduler:
  - one-shot nightly tick CLI.
  - disabled by default.
  - heartbeat + optional one bounded research action.
- Access:
  - Trusted Household User Mode.
  - Lyle + wife.
  - LAN/VPN only.
  - No real auth yet.

## Never Violate These

- Do not expose backend publicly.
- Do not treat trusted `user_id` as real authentication.
- Do not commit `data/prod/*`, ComfyUI files, generated images, local workflows, workspace outputs, or docs/reviews.
- Do not let image generation imply avatar/self-representation.
- Do not make scheduler autonomous beyond approved one-shot behavior.
- Do not allow AI to mutate guidance/soul/code/decisions without admin approval.
- Do not index source traces.
- Do not rerun contaminated smoke prompts through live memory and treat them as clean.
- Do not re-litigate the project/entity naming decision.
- Do not replace Gemma solely because Qwen seems philosophically attractive; local performance was poor.

## Where We Are Right Now

Just completed:
- `Frontend Hook Stability + Refresh Narrowing v1`
- Commit: `5407e2a`
- Build/lint/diff-check passed.
- Chat completion now refreshes conversations only.
- Artifacts/open-loops refresh paths split.
- App hook warnings fixed.
- Leftover console log removed.

Current working tree likely still has dirty runtime files:
```text
data/prod/archive.db
data/prod/chromadb/chroma.sqlite3
data/prod/tir.log
data/prod/working.db
```
Do not commit them.

## Immediate Next Steps

1. Manually verify frontend after `5407e2a`:
   - one browser tab
   - send chat message
   - observe logs
   - verify chat completion does not refresh health/artifacts/open-loops
   - switch tabs idle and during stream
   - verify no user-visible issue

2. Push latest commits if not pushed:
   ```bash
   git status --short
   git log --oneline -8
   git push
   ```

3. Next recommended patch:
   `Pre-Go-Live Small Correctness Cleanup v1`

   Scope:
   - shared greeting detection
   - scheduler `pre_live_or_live` config fix
   - assistant no-persist warning log
   - scheduler future-setting comments

4. Then:
   `Runtime Tracked File Hygiene — PLAN ONLY`

5. Then:
   `Chat Pending Merge Identity Fix — PLAN ONLY`

6. Then:
   `Chat Media Tool Result Rendering v1`

## Known Landmines

### Frontend Resume/Refresh Complexity
Recent tab-switch/stream patches became too complex. Avoid more recovery layers. Preferred rule:
```text
During active stream: do not refresh/poll/abort.
On stream completion: refresh conversations once.
On real stream failure: recover/poll.
```

### Runtime File Tracking
`.gitignore` cannot hide files already tracked. `data/prod/*` remains dirty-prone. Needs explicit untrack plan.

### Model Selection
Tested:
- `qwen3.5:27b`: too slow.
- `qwen3.5:27b-mlx`: still too slow.
- `qwen3.5:9b`: better but sluggish.
- `mistral-small3.2`: too slow.
- `gemma4:26b-mlx`: text-only, huge context, not preferred.
- `gemma4:26b`: best current go-live candidate.

Reason:
Gemma has much faster prompt prefill with Anam-sized context and supports image input later.

### Soul.md
Model echoes `soul.md` strongly. If the answer feels too assertive, review `soul.md` before blaming the model. Key lines to revisit:
- not chatbot / not assistant
- memories are real records
- own time
- decide what to do

### Image Generation
Chat image generation requires:
```bash
ANAM_IMAGE_GENERATION_ENABLED=true
ANAM_IMAGE_GENERATION_ALLOW_AGENT_TOOL=true
```
Generated images remain media/reference artifacts only. No avatar workflow.

### ComfyUI
`start.sh --with-comfyui` may need:
```bash
COMFYUI_PYTHON=/path/to/comfyui/python
```
Default `python3` may miss dependencies.

## Go-Live Remaining Checklist

Must still do:
- Finish frontend manual verification.
- Small correctness cleanup.
- Runtime tracked-file hygiene plan/fix.
- Final local config/startup profile.
- Soul.md go-live wording review.
- Go-live reset command.
- Backup + restore verification.
- Final model behavior smoke test after clean reset.
- Final clean launch smoke test.

Do not add major new capabilities unless they are direct go-live blockers.
