# PROJECT_STATE.md

## Project Summary

Project Anam is a local, persistent AI substrate intended to test whether long-term memory, source-labeled experience, reflection, bounded research, and tools produce meaningfully different behavior over time. The project is named Anam; the AI entity itself is intentionally unnamed.

## Tech Stack

Known versions:
- Python: 3.14.5 via Homebrew path observed locally.
- Frontend: React + Vite.
- Backend: FastAPI/Uvicorn-style Python API.
- Model runtime: Ollama.
- Primary model candidate: `gemma4:26b`.
- Embedding model: `nomic-embed-text`.
- Vector DB: ChromaDB.
- Relational DB: SQLite.
- Search: SQLite FTS5 + Chroma hybrid retrieval.
- Image generation backend: ComfyUI local server.
- Image generation test checkpoint: SD 1.5 safetensors.
- Test runner: pytest.
- Frontend checks: npm build/lint.

Unknown exact package versions:
- FastAPI
- Uvicorn
- React
- Vite
- ChromaDB
- Node/npm
- Ollama

Verify with:
```bash
python --version
.pyanam/bin/python -m pip freeze
node --version
npm --version
ollama --version
npm --prefix frontend list --depth=0
```

## Current Directory Structure

```text
/
├── tir/                          Python backend package.
│   ├── api/                      HTTP API routes, auth, system endpoints.
│   ├── engine/                   Agent loop, context assembly, prompt/runtime execution.
│   ├── memory/                   SQLite archive/working DB, retrieval, chunking, Chroma, FTS.
│   ├── artifacts/                Artifact ingestion, media metadata, artifact search.
│   ├── media/                    Image generation service and ComfyUI backend.
│   ├── research/                 Bounded research, open loops, Moltbook/source trace handling.
│   ├── scheduler/                Nightly tick / bounded scheduler.
│   ├── ops/                      Backup, restore, status/capabilities.
│   └── tools/                    Tool registry, tool context, tool dispatch helpers.
├── skills/active/                Active agent-callable tools.
│   ├── memory_search/            Memory search skill.
│   └── media_artifacts/          media_search, media_get, image_generate tools.
├── frontend/                     React/Vite Web UI.
│   ├── src/App.jsx               Main UI shell, tabs, refresh ownership.
│   ├── src/components/Chat.jsx   Chat UI, streaming, mobile resume, pending state.
│   ├── src/components/...        Registry/media, system/status, debug panels.
│   └── src/styles.css            Global/mobile/iPhone styling.
├── config/                       Defaults and local configuration.
│   ├── defaults.toml             Tracked safe defaults.
│   └── local.toml                Local override file; do not commit.
├── data/prod/                    Runtime SQLite DBs, Chroma, logs. Currently tracked/dirty-prone.
├── workspace/                    Runtime/generated files, research notes, journals, uploads.
├── docs/                         Design docs, runbooks, inventories.
├── changelog/                    Patch-by-patch changelog entries.
├── tests/                        Backend/unit/integration test suite.
├── backups/                      Local backups. Do not commit.
├── ComfyUI/                      Local ComfyUI checkout. Do not commit.
├── start.sh                      Local/LAN startup script; can optionally start ComfyUI.
├── pytest.ini                    Pytest ignore/norecursedirs config.
└── README / project docs         General project material.
```

## Complete

- Persistent conversation storage.
- Archive/working SQLite model.
- Chroma + FTS5 hybrid retrieval.
- Conversation chunking and checkpointing.
- Memory search skill.
- Trusted Household User Mode v1.
- Active user display/switching in Web UI.
- LAN startup via `start.sh --lan`.
- iPhone/mobile UI polish.
- Mobile resume/local state persistence.
- Web UI image generation.
- CLI image generation.
- Chat-callable media tools:
  - `media_search`
  - `media_get`
  - config-gated `image_generate`
- Safe image preview endpoint.
- Image artifacts stored metadata-only in retrieval.
- ComfyUI backend integration.
- Source trace sidecar collection.
- Source trace ingestion blocklist.
- Moltbook source preview/trace handling.
- Bounded research open-loop run-next.
- Scheduler/nightly tick CLI.
- Backup/restore verification.
- Atomic restore hardening.
- Go-live reset runbook.
- Model smoke test protocol doc.
- Temporal awareness design doc.
- Interpretation trace design doc.
- Frontend hook stability + refresh narrowing v1.
- Local runtime/tooling hygiene for pytest collection.
- Full backend test suite passing recently: 835 tests.
- Frontend build/lint passing, with warnings previously resolved except when noted.

## In Progress

- Pre-go-live cleanup based on code reviews.
- Manual verification of recent frontend refresh behavior.
- Final model temperature choice for `gemma4:26b`.
- Soul.md go-live wording review.
- Runtime tracked file hygiene plan.
- Go-live reset command implementation.
- Final launch config/profile.

## Deferred

- Real login/session auth.
- Public internet exposure.
- Avatar/self-representation workflow.
- Avatar candidate/final selection.
- Agent-callable autonomous image generation.
- Scheduler-triggered image generation.
- Model switching UI.
- API key management UI.
- Working theories.
- Interpretation Trace Runtime v1.
- Temporal Runtime Headers v1.
- Web Source Runtime v1.
- Launchd/cron automation for scheduler.
- Full frontend test harness.
- Production/static frontend serving path.
- Self-modification system.
