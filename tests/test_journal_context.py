import importlib
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def journal_context_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "working.db")
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "chromadb"))

    import tir.memory.db as db_mod
    import tir.artifacts.service as artifacts_mod
    import tir.engine.journal_context as journal_context_mod

    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    importlib.reload(journal_context_mod)
    db_mod.init_databases()

    workspace = tmp_path / "workspace"
    (workspace / "journals").mkdir(parents=True)
    return {
        "db": db_mod,
        "artifacts": artifacts_mod,
        "journal_context": journal_context_mod,
        "workspace": workspace,
    }


def _fixed_now():
    return datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)


def _create_journal_artifact(env, *, journal_date="2026-05-08", content="Journal text."):
    path = f"journals/{journal_date}.md"
    (env["workspace"] / path).write_text(content, encoding="utf-8")
    return env["artifacts"].create_artifact(
        artifact_type="journal",
        title=f"Reflection Journal — {journal_date}",
        path=path,
        status="active",
        source="reflection",
        metadata={
            "journal_date": journal_date,
            "local_date": journal_date,
            "source_type": "journal",
            "source_role": "journal",
            "origin": "reflection_journal",
        },
        workspace_root=env["workspace"],
    )


def test_detects_month_day_reflection_journal_intent(journal_context_env):
    journal_context = journal_context_env["journal_context"]

    intent = journal_context.detect_journal_date_intent(
        "Do you remember anything from your May 8 reflection journal?",
        now=_fixed_now(),
    )

    assert intent["matched"] is True
    assert intent["journal_date"] == "2026-05-08"
    assert intent["year_inferred"] is True


def test_detects_iso_journal_intent(journal_context_env):
    journal_context = journal_context_env["journal_context"]

    intent = journal_context.detect_journal_date_intent(
        "Look at your journal from 2026-05-08",
        now=_fixed_now(),
    )

    assert intent["matched"] is True
    assert intent["journal_date"] == "2026-05-08"
    assert intent["year_inferred"] is False


def test_non_journal_date_mention_does_not_trigger(journal_context_env):
    journal_context = journal_context_env["journal_context"]

    intent = journal_context.detect_journal_date_intent(
        "What happened on May 8?",
        now=_fixed_now(),
    )

    assert intent["matched"] is False
    assert intent["reason"] == "missing_journal_term"


def test_missing_date_does_not_trigger(journal_context_env):
    journal_context = journal_context_env["journal_context"]

    intent = journal_context.detect_journal_date_intent(
        "Do you remember your journal?",
        now=_fixed_now(),
    )

    assert intent["matched"] is False
    assert intent["reason"] == "missing_date"


def test_matching_artifact_loads_primary_journal_context(journal_context_env):
    artifact = _create_journal_artifact(
        journal_context_env,
        content="# Reflection Journal — 2026-05-08\n\nThe journal mentioned source framing.",
    )
    journal_context = journal_context_env["journal_context"]

    context, meta = journal_context.build_primary_journal_context(
        "What did your May 8 journal say?",
        now=_fixed_now(),
        workspace_root=journal_context_env["workspace"],
    )

    assert meta["included"] is True
    assert meta["journal_date"] == "2026-05-08"
    assert meta["artifact_id"] == artifact["artifact_id"]
    assert meta["path"] == "journals/2026-05-08.md"
    assert context.startswith("[Primary reflection journal source — 2026-05-08]")
    assert "Treat it as the primary source" in context
    assert "Distinguish what the journal states from later interpretation" in context
    assert "The journal mentioned source framing." in context


def test_missing_artifact_is_reported_cleanly(journal_context_env):
    journal_context = journal_context_env["journal_context"]

    context, meta = journal_context.build_primary_journal_context(
        "What did your 2026-05-08 journal say?",
        now=_fixed_now(),
        workspace_root=journal_context_env["workspace"],
    )

    assert context is None
    assert meta["included"] is False
    assert meta["journal_date"] == "2026-05-08"
    assert meta["reason"] == "journal_artifact_not_found"


def test_missing_journal_file_is_reported_cleanly(journal_context_env):
    artifact = journal_context_env["artifacts"].create_artifact(
        artifact_type="journal",
        title="Reflection Journal — 2026-05-08",
        path="journals/2026-05-08.md",
        status="active",
        source="reflection",
        metadata={
            "journal_date": "2026-05-08",
            "source_type": "journal",
            "origin": "reflection_journal",
        },
        workspace_root=journal_context_env["workspace"],
    )
    journal_context = journal_context_env["journal_context"]

    context, meta = journal_context.build_primary_journal_context(
        "What did your 2026-05-08 journal say?",
        now=_fixed_now(),
        workspace_root=journal_context_env["workspace"],
    )

    assert context is None
    assert meta["included"] is False
    assert meta["artifact_id"] == artifact["artifact_id"]
    assert meta["reason"] == "journal_file_not_found"


def test_over_budget_journal_truncates_with_marker(journal_context_env):
    journal_context = journal_context_env["journal_context"]
    content = "A" * (journal_context.PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET + 1000)
    _create_journal_artifact(journal_context_env, content=content)

    context, meta = journal_context.build_primary_journal_context(
        "Summarize your 2026-05-08 journal",
        now=_fixed_now(),
        workspace_root=journal_context_env["workspace"],
    )

    assert meta["included"] is True
    assert meta["truncated"] is True
    assert journal_context.PRIMARY_JOURNAL_CONTEXT_TRUNCATION_MARKER in context
    assert len(context) <= journal_context.PRIMARY_JOURNAL_CONTEXT_CHAR_BUDGET
