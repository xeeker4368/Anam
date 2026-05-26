# Web UI Go-Live Usability v1

## Summary

Added a browser-accessible generated-media flow and clearer household user switching while keeping image generation user/operator-triggered only.

## Files Changed

- `tir/api/routes.py`
- `tir/ops/capabilities.py`
- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`
- `frontend/src/components/RegistryPanel.jsx`
- `frontend/src/styles.css`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_image_generation_api.py`
- `tests/test_capabilities.py`
- `tests/test_system_status_api.py`

## Behavior Changed

- Added `POST /api/image-generation/generate` for trusted-household, user-triggered image generation.
- Added `GET /api/artifacts/{artifact_id}/file` for safe image/media artifact previews from workspace storage.
- Added a compact Registry-panel Generate Image form for generated media artifacts.
- Added a main-chat household user selector when multiple users exist.
- Updated capability status so image generation is reported as implemented manual functionality with enabled/configured readiness fields.

## Tests / Checks Run

- `.pyanam/bin/python -m pytest tests/test_image_generation_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_system_status_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_image_generation.py -v`
- `.pyanam/bin/python -m pytest tests/test_capabilities.py tests/test_system_status_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python -m pytest tests -v`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`

## Known Limitations

- No avatar workflow, avatar candidate status, or self-representation path is included.
- Image generation is not agent-callable.
- The preview endpoint is intentionally narrow and serves only safe image MIME types.
- Real authentication remains deferred; this keeps the trusted household client identity model.

## Follow-Up Work

- Add richer media gallery/browse behavior only if needed after go-live.
- Add real login/session auth before broader exposure.
- Keep avatar/self-representation workflow post-go-live and separately approved.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, appearance, visual identity, or personality.
- Preserves generated images as ordinary traceable media artifacts.
- Keeps raw image bytes out of content indexing.
- Preserves the distinction between Project Anam as substrate and the unnamed entity.
