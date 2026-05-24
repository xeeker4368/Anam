# Image Generation Backend / Interface v1

## Summary

Added a backend-agnostic image generation service with a ComfyUI backend implementation, exposed through an admin CLI only. Image generation is disabled by default and successful outputs are saved through the existing media artifact ingestion path.

## Files Changed

- `config/defaults.toml`
- `tir/config.py`
- `tir/admin.py`
- `tir/artifacts/media.py`
- `tir/memory/artifact_indexing.py`
- `tir/media/__init__.py`
- `tir/media/image_generation.py`
- `tir/media/backends/__init__.py`
- `tir/media/backends/base.py`
- `tir/media/backends/comfyui.py`
- `tests/test_image_generation.py`
- `tests/test_admin.py`
- `tests/test_config.py`

## Behavior Changed

- Added disabled-by-default image generation config.
- Added `image-generate` admin command with `--dry-run` and `--write` modes.
- Added a backend protocol so future generators can be swapped without changing artifact storage.
- Added a ComfyUI backend that only accepts local ComfyUI URLs in v1.
- Successful generation stores bytes through `ingest_artifact_file(...)` with generated-image media provenance.
- Generation failures return structured error output and create no artifact unless an output image exists.
- Generated image event chunks include labeled prompt/provenance metadata while raw image bytes remain unindexed.

## Tests / Checks Run

- `.pyanam/bin/python -m pytest tests/test_image_generation.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_config.py -v`

## Known Limitations

- Image generation remains disabled by default.
- No agent-callable image generation tool was added.
- No frontend image generation UI was added.
- No avatar, avatar candidate, or self-representation workflow was added.
- ComfyUI workflow configuration is operator-supplied and must be validated before real use.

## Follow-Up Work

- Add an operator-approved ComfyUI workflow file or setup guide.
- Add live ComfyUI smoke testing once a local backend is installed.
- Consider agent-callable image generation only after CLI/backend behavior is stable.
- Keep avatar/self-representation work post-go-live and separately approved.

## Project Anam Alignment Check

- This patch does not assign the entity a name, avatar, appearance, personality, or identity metadata.
- Generated images are ordinary media artifacts, not identity facts.
- Prompt/provenance metadata remains inspectable and source-linked.
- Raw generated image bytes do not become hidden retrievable memory content.
