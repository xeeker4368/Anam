import importlib
import json
from types import SimpleNamespace

import pytest


@pytest.fixture()
def temp_backup_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.BACKUP_DIR", tmp_path / "backups")

    import tir.memory.db as db_mod
    import tir.ops.backup as backup_mod
    import tir.admin as admin_mod

    importlib.reload(db_mod)
    importlib.reload(backup_mod)
    importlib.reload(admin_mod)
    db_mod.init_databases()
    yield db_mod, backup_mod, admin_mod, tmp_path


def _manifest(summary: dict) -> dict:
    return json.loads((summary["manifest_path"] and open(summary["manifest_path"]).read()))


def _write_runtime_dirs(tmp_path):
    chroma_dir = tmp_path / "data" / "prod" / "chromadb"
    chroma_dir.mkdir(parents=True)
    (chroma_dir / "index.bin").write_bytes(b"vector data")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("workspace note", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=1", encoding="utf-8")
    (workspace / "secrets").mkdir()
    (workspace / "secrets" / "token.txt").write_text("token", encoding="utf-8")
    (workspace / "logs").mkdir()
    (workspace / "logs" / "runtime.log").write_text("log", encoding="utf-8")


def test_backup_creates_timestamped_directory_and_manifest(temp_backup_env):
    db_mod, backup_mod, _admin_mod, tmp_path = temp_backup_env
    db_mod.create_user("Lyle")

    summary = backup_mod.create_backup()
    backup_path = tmp_path / "backups" / summary["backup_path"].split("/")[-1]
    manifest = _manifest(summary)

    assert backup_path.exists()
    assert (backup_path / "manifest.json").exists()
    assert manifest["backup_version"] == 1
    assert manifest["project"] == "Project Anam"
    assert manifest["created_at"]


def test_backup_copies_db_files_and_records_hashes(temp_backup_env):
    db_mod, backup_mod, _admin_mod, _tmp_path = temp_backup_env
    db_mod.create_user("Lyle")

    summary = backup_mod.create_backup()
    manifest = _manifest(summary)

    working = manifest["paths"]["working_db"]
    archive = manifest["paths"]["archive_db"]
    assert working["exists"] is True
    assert archive["exists"] is True
    assert working["bytes"] > 0
    assert archive["bytes"] > 0
    assert len(working["sha256"]) == 64
    assert len(archive["sha256"]) == 64
    assert (summary["manifest"].get("paths") == manifest["paths"])


def test_backup_copies_chroma_and_workspace_when_present(temp_backup_env):
    _db_mod, backup_mod, _admin_mod, tmp_path = temp_backup_env
    _write_runtime_dirs(tmp_path)

    summary = backup_mod.create_backup()
    backup_path = tmp_path / "backups" / summary["backup_path"].split("/")[-1]
    manifest = _manifest(summary)

    assert manifest["paths"]["chroma_dir"]["exists"] is True
    assert manifest["paths"]["chroma_dir"]["file_count"] == 1
    assert (backup_path / "runtime" / "chromadb" / "index.bin").exists()
    assert manifest["paths"]["workspace_dir"]["exists"] is True
    assert (backup_path / "workspace" / "note.txt").exists()


def test_backup_records_missing_optional_dirs_without_failing(temp_backup_env):
    _db_mod, backup_mod, _admin_mod, _tmp_path = temp_backup_env

    summary = backup_mod.create_backup()
    manifest = _manifest(summary)

    assert manifest["paths"]["chroma_dir"]["exists"] is False
    assert manifest["paths"]["workspace_dir"]["exists"] is False


def test_backup_does_not_copy_env_secrets_or_logs(temp_backup_env):
    _db_mod, backup_mod, _admin_mod, tmp_path = temp_backup_env
    _write_runtime_dirs(tmp_path)

    summary = backup_mod.create_backup()
    backup_path = tmp_path / "backups" / summary["backup_path"].split("/")[-1]

    assert not (backup_path / "workspace" / ".env").exists()
    assert not (backup_path / "workspace" / "secrets").exists()
    assert not (backup_path / "workspace" / "logs").exists()


def test_restore_dry_run_does_not_mutate(temp_backup_env):
    db_mod, backup_mod, _admin_mod, tmp_path = temp_backup_env
    db_mod.create_user("Before")
    summary = backup_mod.create_backup()
    db_mod.create_user("After")

    restore = backup_mod.restore_backup(summary["backup_path"], dry_run=True)

    assert restore["ok"] is True
    assert restore["dry_run"] is True
    assert restore["pre_restore_backup"] is None
    assert db_mod.get_user_by_name("After") is not None
    assert (tmp_path / "backups").exists()


def test_restore_without_force_refuses(temp_backup_env):
    db_mod, backup_mod, _admin_mod, _tmp_path = temp_backup_env
    db_mod.create_user("Before")
    summary = backup_mod.create_backup()

    restore = backup_mod.restore_backup(summary["backup_path"])

    assert restore["ok"] is False
    assert "requires force" in restore["error"]


def test_restore_validates_manifest(temp_backup_env, tmp_path):
    _db_mod, backup_mod, _admin_mod, _env_tmp_path = temp_backup_env
    bad_backup = tmp_path / "bad-backup"
    bad_backup.mkdir()

    with pytest.raises(backup_mod.BackupError):
        backup_mod.restore_backup(bad_backup, dry_run=True)


def test_restore_creates_pre_restore_backup_and_restores_files(temp_backup_env):
    db_mod, backup_mod, _admin_mod, tmp_path = temp_backup_env
    db_mod.create_user("Before")
    _write_runtime_dirs(tmp_path)
    summary = backup_mod.create_backup()

    db_mod.create_user("After")
    (tmp_path / "workspace" / "note.txt").write_text("mutated", encoding="utf-8")
    (tmp_path / "data" / "prod" / "chromadb" / "index.bin").write_bytes(b"mutated")

    restore = backup_mod.restore_backup(summary["backup_path"], force=True)

    assert restore["ok"] is True
    assert restore["pre_restore_backup"]
    assert (tmp_path / "workspace" / "note.txt").read_text(encoding="utf-8") == "workspace note"
    assert (tmp_path / "data" / "prod" / "chromadb" / "index.bin").read_bytes() == b"vector data"
    assert db_mod.get_user_by_name("Before") is not None
    assert db_mod.get_user_by_name("After") is None
    assert (tmp_path / "backups" / restore["pre_restore_backup"].split("/")[-1] / "manifest.json").exists()


def test_admin_backup_command_prints_summary(temp_backup_env, capsys):
    db_mod, _backup_mod, admin_mod, tmp_path = temp_backup_env
    db_mod.create_user("Lyle")

    admin_mod.cmd_backup(SimpleNamespace(destination=tmp_path / "manual-backups"))

    output = capsys.readouterr().out
    assert "Backup complete" in output
    assert "Backup path:" in output
    assert "working_db: copied" in output


def test_admin_restore_dry_run_prints_summary(temp_backup_env, capsys):
    db_mod, backup_mod, admin_mod, _tmp_path = temp_backup_env
    db_mod.create_user("Lyle")
    summary = backup_mod.create_backup()

    admin_mod.cmd_restore(
        SimpleNamespace(
            backup_path=summary["backup_path"],
            dry_run=True,
            force=False,
        )
    )

    output = capsys.readouterr().out
    assert "Restore" in output
    assert "Dry run: True" in output
    assert "Would replace:" in output
