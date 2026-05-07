## Summary

Added opt-in artifact-aware retrieval boosting for artifact/file-related chat prompts so exact filename, title, and artifact ID queries prefer `artifact_document` chunks over conversation chunks that merely mention the artifact.

## Files Changed

- `tir/memory/retrieval.py`
- `tir/api/routes.py`
- `tests/test_retrieval.py`
- `tests/test_api_agent_stream.py`

## Behavior Changed

- `retrieve(...)` now accepts `artifact_intent: bool = False`.
- Default retrieval behavior remains unchanged when `artifact_intent` is false.
- Automatic `/api/chat/stream` retrieval passes `artifact_intent=True` only when the existing artifact-intent helper detects upload/file/artifact/document intent.
- Artifact-aware ranking applies:
  - a modest boost to `artifact_document` chunks
  - a stronger boost for exact/strong filename, meaningful title, or artifact ID matches
  - fallback matching against artifact text headers for BM25-only rows
- Debug chunk metadata may include:
  - `artifact_boost`
  - `artifact_exact_match`
  - `artifact_match_field`

## Ranking Strategy

Artifact boosting is post-fusion and opt-in. It does not hard-filter conversation chunks or remove non-artifact chunks. If no artifact chunk matches, normal conversation/source retrieval can still surface useful context.

Generic one-word titles do not receive strong title boosts to avoid over-weighting vague artifact names.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_retrieval.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- Artifact title matching is intentionally conservative and may not boost vague or partial title references.
- BM25-only artifact rows rely on simple artifact header parsing.
- This does not add source-specific quotas or change broader retrieval ranking.

## Follow-Up Work

- Consider a later source-type quota if artifact chunks and conversation chunks still compete poorly in broad mixed queries.
- Consider richer artifact query parsing for partial title references after observing real usage.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Did not change DB schema, Chroma, FTS, or memory architecture.
- Did not promote uploaded artifacts to runtime guidance, identity, or operational truth.
- Preserved uploaded artifacts as uploaded source artifacts.
- Did not change `memory_search` behavior.
