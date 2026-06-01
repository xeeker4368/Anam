# ACTIVE_TASK.md

## Current Active Area

Pre-go-live cleanup and stabilization.

The project is no longer primarily adding features. Current work is reducing frontend refresh/state complexity, cleaning small correctness issues, and preparing for final go-live reset/config/smoke testing.

## Just Completed

Completed patch:
- `Frontend Hook Stability + Refresh Narrowing v1`
- Commit: `5407e2a`

Changes:
- Stabilized App.jsx refresh callbacks.
- Fixed App.jsx hook dependency warnings.
- Split artifact/open-loop refresh paths.
- Chat completion refreshes conversations only.
- Upload/image generation refreshes artifacts only.
- Removed leftover `console.log('Closed:', data)`.
- Build/lint/diff-check passed.

Recent completed major features:
- Web UI polish.
- iPhone/mobile fixes.
- LAN startup and cleanup hardening.
- Chat-callable media tools.
- Image generation UI/API/CLI.
- Scheduler/nightly tick.
- Local runtime tooling hygiene.
- Backup/restore verification and restore hardening.

## Immediate Next Steps

1. Manually verify latest frontend cleanup:
   - one browser tab only
   - send chat message
   - confirm chat completion does not refresh health/artifacts/open-loops
   - switch tabs idle and during stream
   - verify no user-visible issue

2. Run:
   ```bash
   cd "/Volumes/Dock Storage/Anam"
   git status --short
   git log --oneline -8
   git push
   ```

3. Next recommended implementation patch:
   - `Pre-Go-Live Small Correctness Cleanup v1`

   Scope:
   - Deduplicate greeting detection.
   - Fix scheduler `pre_live_or_live` hardcode.
   - Add warning log for no assistant persistence.
   - Add clarifying comments for scheduler future image/Moltbook settings.

4. Then plan:
   - `Runtime Tracked File Hygiene — PLAN ONLY`

5. Then:
   - `Chat Pending Merge Identity Fix — PLAN ONLY`

6. Then:
   - `Chat Media Tool Result Rendering v1`

## Unresolved Questions

- Final Gemma temperature: 0.20 or 0.25.
- Whether to modify `soul.md` wording before go-live.
- Whether go-live uses image generation chat tool enabled by default or only manually via env.
- Whether scheduler should be manual-only at launch or later launchd/cron.
- Whether CORS should remain proxy-only or gain configurable LAN origins.
- Whether to untrack `data/prod/*` before go-live.

## Current Known Gotchas

- Do not re-run model smoke prompts inside current Anam memory and treat results as clean; memory is contaminated by prior tests.
- `data/prod/*` is tracked and remains dirty; do not commit it accidentally.
- `config/local.toml` is local-only; do not commit.
- `ComfyUI/` and `config/comfyui/` are local; do not commit.
- Chat/image generation requires:
  ```bash
  ANAM_IMAGE_GENERATION_ENABLED=true
  ANAM_IMAGE_GENERATION_ALLOW_AGENT_TOOL=true
  ```
- `start.sh --with-comfyui` may need `COMFYUI_PYTHON` set to the correct ComfyUI environment.
- Backend should remain localhost-only in LAN mode; iPhone reaches backend through Vite proxy.
- Recent frontend resume/polling work was overcomplicated; avoid adding more recovery layers without diagnosis.
- Normal `gemma4:26b` is preferred over MLX because image support matters.
- Qwen/Mistral were slow due to prompt prefill on Anam-sized prompts.

## Do Not Repeat These Mistakes

- Do not assume tab switching means stream failure.
- Do not add polling unless there is a real failure path.
- Do not solve UI state bugs by adding broad refreshes.
- Do not let Chat trigger broad App refreshes.
- Do not change model because of philosophical discomfort without testing local performance.
- Do not treat `soul.md` echoing as model hallucination.
