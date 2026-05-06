# File and Artifact Ingestion Foundation

## Summary

Added an internal ingestion foundation for uploaded/generated files so files can be saved durably, artifact-registered, linked to source context, and indexed as retrievable artifact source memory.

## Files Changed

- `tir/artifacts/ingestion.py`
- `tir/artifacts/__init__.py`
- `tir/artifacts/service.py`
- `tir/memory/artifact_indexing.py`
- `tir/workspace/service.py`
- `tir/engine/context.py`
- `tests/test_artifact_ingestion.py`
- `changelog/2026-05-05-artifact-ingestion-foundation.md`

## Behavior Changed

- Added `ingest_artifact_file(...)` as an internal service for saving bytes into controlled workspace storage and registering artifact metadata.
- Added `uploads/` and `generated/` to default workspace directories.
- Added `uploaded_file` and `generated_file` artifact types.
- Ingested files are stored under dated workspace paths with artifact-id directory isolation.
- Ingested artifact metadata includes filename, safe filename, MIME type, size, SHA-256, created_by, authority, indexing status, source type, and user id.
- Every ingested file gets a retrievable metadata/event chunk.
- Supported text-like files also get content chunks.
- Unsupported/binary files are saved and registered, then indexed as metadata-only.
- Artifact document chunks are formatted in context as source material rather than core belief.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifacts.py tests/test_workspace.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py tests/test_memory_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_registry_visibility.py -v`
- `git diff --check`

## Known Limitations

- No public upload API or UI upload component exists yet.
- No DB schema changes were made; richer ingestion metadata lives in `metadata_json`.
- Unsupported/binary files receive metadata/event retrieval only, not content extraction.
- PDF, Office document, OCR, image, audio, and video extraction are deferred.
- File save, indexing, and artifact registration are not a single cross-store transaction.

## Follow-Up Work

- Add a bounded upload API after the internal service proves stable.
- Add UI upload controls only after API behavior is approved.
- Consider schema promotion for `sha256`, `mime_type`, `size_bytes`, `authority`, and `indexing_status` if filtering/reporting needs grow.
- Add extractors for PDF/Office/OCR/media only in staged follow-up patches.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience by storing files and source events.
- Makes entered/generated artifacts traceable and retrievable.
- Does not promote uploaded contents to operational guidance, identity, personality, or core belief.
- Does not add autonomy, write/action tools, image generation, speech, vision, self-modification, UI upload, or public upload API behavior.
