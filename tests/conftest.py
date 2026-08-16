"""Test-session guards that keep the suite out of the production store.

Why this file exists: for roughly seven weeks the suite wrote real chunks into
`data/prod/chromadb` on every run (50 orphaned `fake-output.png` event chunks
accumulated there) and real trace lines into `data/prod/chat_debug.jsonl`.
Nothing failed, because the writes either succeeded into production or were
swallowed downstream. See PLAN-2026-08-16-chroma-test-isolation.md.

Two mechanisms here, deliberately different:

* **Chroma — guard only, no redirect.** With the call-time path resolution in
  `tir/memory/chroma.py`, every existing fixture that patches
  `tir.config.CHROMA_DIR` now genuinely redirects. Nothing needs helping, so
  this file only watches, and any write that resolves the real store is a bug
  we want surfaced rather than absorbed.
* **chat debug trace — redirect *and* guard.** `tir/api/routes.py` snapshots
  `CHAT_DEBUG_TRACE_PATH` into its own namespace at import, so call-time
  resolution in `tir/ops/chat_debug_trace.py` cannot reach it, and several
  tests exercise the chat route with no path isolation of their own. Those
  tests cannot be fixed from the source side without editing them, so the
  redirect below points them at tmp_path. The guard still watches underneath.

The violation type inherits from `BaseException` on purpose: several runtime
paths wrap store access in `except Exception` (`retrieve`, `index_artifact_file`,
the routes trace call), and a guard those swallow is no guard at all. Violations
are also recorded and re-reported at session end, so a swallowed one still fails
the run visibly.
"""

import chromadb
import pytest

from tir import config


# Captured at conftest import — before any test can patch config.
REAL_CHROMA_DIR = str(config.CHROMA_DIR)
REAL_DATA_DIR = str(config.DATA_DIR)
REAL_CHAT_DEBUG_TRACE_PATH = str(config.DATA_DIR / "chat_debug.jsonl")

_violations: list[str] = []


class StoreIsolationViolation(BaseException):
    """Raised when a test resolves a real production store path."""


def _record(message: str) -> StoreIsolationViolation:
    _violations.append(message)
    return StoreIsolationViolation(message)


def _same_path(left, right) -> bool:
    import os

    return os.path.abspath(str(left)) == os.path.abspath(str(right))


@pytest.fixture(scope="session", autouse=True)
def _guard_production_store():
    """Fail loudly if any test opens the real Chroma store or trace file."""
    original_client = chromadb.PersistentClient
    import tir.ops.chat_debug_trace as chat_debug_trace

    original_write = chat_debug_trace.write_chat_debug_trace

    def guarded_client(*args, **kwargs):
        path = kwargs.get("path") or (args[0] if args else None)
        if path is not None and _same_path(path, REAL_CHROMA_DIR):
            raise _record(
                "Test opened the PRODUCTION Chroma store at "
                f"{REAL_CHROMA_DIR}. Isolate it (patch tir.config.CHROMA_DIR "
                "and call tir.memory.chroma.reset_client(), or replace "
                "tir.memory.chroma._get_collection)."
            )
        return original_client(*args, **kwargs)

    def guarded_write(record, *, path=None):
        target = path or chat_debug_trace.chat_debug_trace_path()
        if _same_path(target, REAL_CHAT_DEBUG_TRACE_PATH):
            raise _record(
                "Test wrote the PRODUCTION chat debug trace at "
                f"{REAL_CHAT_DEBUG_TRACE_PATH}."
            )
        return original_write(record, path=path)

    chromadb.PersistentClient = guarded_client
    chat_debug_trace.write_chat_debug_trace = guarded_write
    try:
        yield
    finally:
        chromadb.PersistentClient = original_client
        chat_debug_trace.write_chat_debug_trace = original_write


class _ViolationLog:
    """Violations recorded since this test started — not the whole session.

    Scoped deliberately: when the guard is doing its job during a genuinely
    broken run, `_violations` already holds entries from other tests, and a
    test asserting on the global list would fail for the wrong reason.
    """

    def __init__(self, start: int):
        self._start = start

    @property
    def recorded(self) -> list[str]:
        return _violations[self._start:]

    def __len__(self) -> int:
        return len(self.recorded)


@pytest.fixture()
def expected_isolation_violations():
    """For tests that trip the guard on purpose.

    Yields a view of violations recorded during this test, and drops them on
    teardown so a deliberate trip does not fail `pytest_sessionfinish`.
    """
    start = len(_violations)
    yield _ViolationLog(start)
    del _violations[start:]


@pytest.fixture(autouse=True)
def _redirect_chat_debug_trace_path(tmp_path, monkeypatch):
    """Point the chat debug trace at tmp_path for every test.

    Needed because `tir.api.routes` binds `CHAT_DEBUG_TRACE_PATH` at import and
    passes it explicitly, so it cannot be reached by call-time resolution.
    Tests with their own trace-path fixture patch the same attribute afterwards
    and still win.
    """
    redirected = tmp_path / "conftest_chat_debug.jsonl"
    monkeypatch.setattr(
        "tir.ops.chat_debug_trace.CHAT_DEBUG_TRACE_PATH", redirected, raising=False
    )
    try:
        import tir.api.routes  # noqa: F401
    except Exception:
        return
    monkeypatch.setattr(
        "tir.api.routes.CHAT_DEBUG_TRACE_PATH", redirected, raising=False
    )


def pytest_sessionfinish(session, exitstatus):
    """Re-surface violations even if a runtime path swallowed the exception."""
    if _violations:
        session.exitstatus = 1
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line("")
            reporter.write_line(
                f"PRODUCTION STORE ISOLATION VIOLATIONS: {len(_violations)}",
                red=True,
                bold=True,
            )
            for message in dict.fromkeys(_violations):
                reporter.write_line(f"  - {message}", red=True)
