# Test Suite Cleanup

## Summary

Fixed existing full-suite test failures caused by stale test references. The patch is test-only and does not change runtime behavior.

## Files Changed

- `tests/test_artifacts.py`
- `tests/test_moltbook_selection_continuity.py`
- `tests/test_open_loops.py`
- `tests/test_url_prefetch.py`
- `changelog/2026-05-10-test-suite-cleanup.md`

## Behavior Changed

No runtime behavior changed.

Test behavior changed:

- Artifact tests now reference the active reloaded artifact/open-loop service modules instead of stale top-level exception classes.
- Open-loop tests now reference the active reloaded artifact/open-loop service modules instead of stale top-level exception classes.
- Route tests now patch `tir.api.routes.checkpoint_conversation`, matching the current route implementation.
- Route tests now reference the active `tir.api.routes` module instead of a stale imported FastAPI `app` after route-module reloads.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_moltbook_selection_continuity.py -v`
- `.pyanam/bin/python -m pytest tests/test_open_loops.py -v`
- `.pyanam/bin/python -m pytest tests/test_url_prefetch.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Existing deprecation warnings from ChromaDB and FastAPI startup handlers remain.

## Follow-Up Work

- Consider a broader test isolation cleanup for modules that use `importlib.reload`.
- Consider migrating FastAPI startup events to lifespan handlers in a dedicated maintenance patch.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Does not change schema, runtime behavior, prompts, memory architecture, artifact indexing, or manual research behavior.
