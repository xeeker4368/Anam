# Artifact Upload API

## Summary

Added a read/write-by-user API entry point for artifact ingestion: `POST /api/artifacts/upload`. Uploaded files now enter through the existing ingestion service, are saved under controlled workspace storage, artifact-registered, provenance-validated, indexed for retrieval, and returned with structured upload/indexing metadata.

## Files Changed

- `requirements.txt`
- `tir/api/routes.py`
- `tir/ops/capabilities.py`
- `tests/test_artifact_upload_api.py`
- `tests/test_capabilities.py`
- `tests/test_system_status_api.py`
- `changelog/2026-05-05-artifact-upload-api.md`

## Behavior Changed

- Added `POST /api/artifacts/upload` accepting multipart uploads with optional title, description, authority, status, revision, conversation, and message provenance fields.
- Uploads use `ingest_artifact_file(...)` and pass the resolved user id into artifact metadata, Chroma metadata, and FTS indexing.
- Upload size is capped with the ingestion layer's `MAX_INGEST_BYTES` limit.
- Any file under the size limit can be saved and registered; supported text-like files receive content chunks, and unsupported/binary files receive metadata/event indexing only.
- Source conversation and message links are validated before ingestion; wrong-user or mismatched provenance links are rejected.
- Malformed upload requests return the approved `{ok:false,error}` envelope with HTTP 400 for the upload route.
- `file_uploads` capability now reports implemented, enabled, available, and manual.

## Dependency Changes

- Added `python-multipart` to `requirements.txt` for FastAPI multipart upload handling.

## Tests/Checks Run

- `.pyanam/bin/python -m pip install -r requirements.txt`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py tests/test_capabilities.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_system_status_api.py -v`
- `git diff --check`

## Known Limitations

- No UI upload component exists yet.
- Uploads are API-only and use the existing local/user resolution model.
- Unsupported/binary files are metadata-only for retrieval.
- PDF, OCR, Office document, image, audio, and video extraction remain deferred.
- Upload storage, artifact registration, and indexing are not a single cross-store transaction.

## Follow-Up Work

- Add a read-only UI upload surface after the API behavior is stable.
- Add richer document extraction in staged, type-specific patches.
- Consider a transaction/repair story for partial upload failures if upload volume grows.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience by saving uploaded files and creating retrievable source events.
- Keeps uploaded content as source material by default, not operational guidance, identity, personality, or core belief.
- Does not add image generation, speech, vision, autonomy, AI write/action tools, self-modification, or DB schema changes.
