# Image / Media Capability Foundation v1

## Summary

Added the first storage/provenance foundation for image and media artifacts. Uploaded image files are now classified with explicit media metadata, screenshot labels can be supplied, and generated-image provenance fields can be preserved for future image generation backends.

## Files Changed

- `tir/artifacts/media.py`
- `tir/artifacts/ingestion.py`
- `tir/memory/artifact_indexing.py`
- `tir/api/routes.py`
- `frontend/src/App.jsx`
- `frontend/src/components/RegistryPanel.jsx`
- `frontend/src/styles.css`
- `tests/test_artifact_ingestion.py`
- `tests/test_artifact_upload_api.py`

## Behavior Changed

- Image uploads are registered as image artifacts with `media_kind=uploaded_image` by default.
- Upload callers may label screenshots with `media_kind=screenshot`.
- Media provenance metadata is normalized and preserved, including prompt, negative prompt, generation backend/model, generation params, source artifact links, visual description, confirmation state, uncertainty label, interpretation source, and intended use.
- Artifact event indexing labels media descriptions as metadata or visual interpretation rather than raw image content.
- Raw image bytes remain metadata-only and are not content-indexed into Chroma or FTS.
- The registry UI displays media metadata and lets image uploads be labeled as uploaded images or screenshots.

## Tests / Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `npm --prefix frontend run build`

## Known Limitations

- No image generation backend or image generation UI was added.
- No avatar, avatar candidate, or self-representation workflow was added.
- No automatic image captioning, OCR, visual QA, or model-based image interpretation was added.
- Media file previews remain minimal in the registry UI.

## Follow-Up Work

- Add an explicit Image Generation Backend/Interface v1 patch.
- Add richer media gallery/preview workflows if needed.
- Add post-go-live avatar/self-representation workflows only after the entity has live continuity and that work is explicitly approved.

## Project Anam Alignment Check

- This patch does not assign the entity a name, avatar, appearance, or personality.
- Image/media artifacts remain source-linked, inspectable, and provisional.
- Visual descriptions and prompts are preserved as metadata/provenance, not treated as identity facts.
- Raw media bytes are preserved as workspace artifacts without becoming hidden memory content.
