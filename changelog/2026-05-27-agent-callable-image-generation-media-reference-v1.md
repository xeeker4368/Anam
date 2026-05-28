# Agent-Callable Image Generation + Media Artifact Reference v1

## Summary

Added chat-callable media artifact tools so explicit user requests can search, inspect, and generate ordinary media/reference artifacts from chat when configured.

## Files Changed

- `tir/tools/context.py`
- `tir/engine/agent_loop.py`
- `tir/api/routes.py`
- `tir/artifacts/search.py`
- `skills/active/media_artifacts/SKILL.md`
- `skills/active/media_artifacts/media_artifacts.py`
- `tests/test_media_artifact_tools.py`
- `tests/test_agent_loop.py`
- `tests/test_api_agent_stream.py`
- `docs/PROMPT_INVENTORY.md`

## Behavior Changed

- Chat requests now pass a compact `ToolContext` into tool dispatch with active user, conversation, source message, and request ids.
- Added `media_search` for safe metadata search over generated/uploaded media artifacts.
- Added `media_get` for safe metadata lookup by artifact id.
- Added `image_generate`, which calls the existing image generation service only when image generation and chat tool access are both enabled.
- Generated image tool results return artifact metadata and preview URLs only, not raw image bytes or absolute local filesystem paths.
- Image generation remains disabled for chat by default through `image_generation.allow_agent_tool=false`.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_media_artifact_tools.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py -v tests/test_api_agent_stream.py -v tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_image_generation.py -v tests/test_image_generation_api.py -v tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest tests -v`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with 3 existing React hook dependency warnings)
- `git diff --check`

## Known Limitations

- Chat image generation is available only when explicitly enabled in configuration.
- Tool results are structured JSON in the existing chat tool-result display; no special image-card chat rendering was added in this patch.
- Media search is metadata-based and does not inspect raw image bytes.
- Ambiguous natural-language references still depend on the model using `media_search` or asking for clarification.

## Follow-Up Work

- Consider richer chat rendering for media tool results if the existing JSON display is not comfortable enough.
- Consider explicit artifact-title UX guidance after go-live if generated media lookup needs stronger naming conventions.
- Design any future self-representation or visual identity workflow separately.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add personality traits or identity claims.
- Preserved raw artifact files and source-linked metadata.
- Kept generated images as ordinary media/reference artifacts.
- Did not change prompts, guidance files, `soul.md`, model config, DB schema, scheduler behavior, research behavior, Moltbook/web behavior, or avatar/self-representation workflow.
