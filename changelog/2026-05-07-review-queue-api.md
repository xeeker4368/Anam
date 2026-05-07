## Summary

Exposed the operator-controlled review queue through simple API endpoints for future UI visibility and management.

## Files Changed

- `tir/api/routes.py`
- `tests/test_api_review.py`

## Behavior Changed

- Added `GET /api/review` to list review items with optional `status`, `category`, `priority`, `limit`, and `offset` filters.
- Added `POST /api/review` to create review items through the existing review service.
- Added `PATCH /api/review/{item_id}` to update only review item status.
- Review API responses use `{ "ok": true, ... }` envelopes for successful list/create/update operations.
- Review service validation errors return `{ "ok": false, "error": "..." }` with HTTP 400.
- Missing review items on PATCH return HTTP 404.

## Endpoint Shapes

`GET /api/review`

```json
{
  "ok": true,
  "items": []
}
```

`POST /api/review`

```json
{
  "ok": true,
  "item": {}
}
```

`PATCH /api/review/{item_id}`

```json
{
  "ok": true,
  "item": {}
}
```

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_review.py -v`
- `.pyanam/bin/python -m pytest tests/test_review_queue.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- No UI was added.
- No model tool access was added.
- No automatic queue creation exists.
- No scheduler or background worker was added.
- Review items are not indexed into Chroma or FTS.
- PATCH only updates status in v1.

## Follow-Up Work

- Add read-only UI visibility in a separate patch.
- Consider title/description editing only after operator workflow is clearer.
- Consider role/auth restrictions if this backend is ever exposed beyond the trusted local operator surface.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Did not add autonomous behavior, model tool access, or automatic queue creation.
- Preserved operator control.
- Did not alter memory architecture, DB archive schema, Chroma, or FTS.
- Did not rename `tir/`.
