"""Filesystem backup and restore helpers for Project Anam runtime state."""

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tir import config

BACKUP_VERSION = 1
PROJECT_NAME = "Project Anam"
EXCLUDED_NAMES = {
    ".env",
    ".pytest_cache",
    "__pycache__",
    ".DS_Store",
    "cache",
    "caches",
    "logs",
    "secrets",
}


class BackupError(RuntimeError):
    """Raised when backup or restore cannot proceed safely."""


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _unique_child(root: Path, name: str) -> Path:
    candidate = root / name
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        suffixed = root / f"{name}-{index}"
        if not suffixed.exists():
            return suffixed
        index += 1


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_stats(path: Path) -> dict:
    file_count = 0
    total_bytes = 0
    for item in path.rglob("*"):
        if item.is_file():
            file_count += 1
            total_bytes += item.stat().st_size
    return {
        "file_count": file_count,
        "bytes": total_bytes,
    }


def _ignore_runtime_names(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED_NAMES}


def _backup_sqlite_db(source: Path, destination: Path, relative_destination: str) -> dict:
    info = {
        "source": str(source),
        "backup": relative_destination,
        "exists": source.exists(),
    }
    if not source.exists():
        return info

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(str(source), timeout=10)
    try:
        dest_conn = sqlite3.connect(str(destination), timeout=10)
        try:
            source_conn.backup(dest_conn)
            dest_conn.commit()
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    info.update({
        "bytes": destination.stat().st_size,
        "sha256": _sha256_file(destination),
    })
    return info


def _copy_optional_dir(source: Path, destination: Path, relative_destination: str) -> dict:
    info = {
        "source": str(source),
        "backup": relative_destination,
        "exists": source.exists(),
    }
    if not source.exists():
        return info

    if not source.is_dir():
        raise BackupError(f"Expected directory, found non-directory: {source}")

    shutil.copytree(source, destination, ignore=_ignore_runtime_names)
    info.update(_directory_stats(destination))
    return info


def _build_manifest(backup_path: Path, created_at: str) -> dict:
    runtime_dir = backup_path / "runtime"
    manifest = {
        "backup_version": BACKUP_VERSION,
        "project": PROJECT_NAME,
        "created_at": created_at,
        "paths": {},
        "excluded": sorted(EXCLUDED_NAMES),
    }

    manifest["paths"]["working_db"] = _backup_sqlite_db(
        Path(config.WORKING_DB),
        runtime_dir / "working.db",
        "runtime/working.db",
    )
    manifest["paths"]["archive_db"] = _backup_sqlite_db(
        Path(config.ARCHIVE_DB),
        runtime_dir / "archive.db",
        "runtime/archive.db",
    )
    manifest["paths"]["chroma_dir"] = _copy_optional_dir(
        Path(config.CHROMA_DIR),
        runtime_dir / "chromadb",
        "runtime/chromadb",
    )
    manifest["paths"]["workspace_dir"] = _copy_optional_dir(
        Path(config.WORKSPACE_DIR),
        backup_path / "workspace",
        "workspace",
    )
    return manifest


def _write_manifest(backup_path: Path, manifest: dict) -> Path:
    manifest_path = backup_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _create_backup_at(root: Path, folder_name: str) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    backup_path = _unique_child(root, folder_name)
    backup_path.mkdir(parents=True)

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = _build_manifest(backup_path, created_at)
    manifest_path = _write_manifest(backup_path, manifest)

    return {
        "ok": True,
        "backup_path": str(backup_path),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }


def create_backup(destination_root: Path | None = None) -> dict:
    """Create a timestamped runtime-state backup and return a summary."""
    root = Path(destination_root) if destination_root is not None else Path(config.BACKUP_DIR)
    return _create_backup_at(root, _utc_timestamp())


def _load_manifest(backup_path: Path) -> dict:
    manifest_path = backup_path / "manifest.json"
    if not manifest_path.exists():
        raise BackupError(f"Backup manifest not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupError(f"Backup manifest is invalid JSON: {manifest_path}") from exc

    if manifest.get("backup_version") != BACKUP_VERSION:
        raise BackupError(
            f"Unsupported backup version: {manifest.get('backup_version')!r}"
        )
    return manifest


def _planned_restore_targets(manifest: dict) -> list[dict[str, Any]]:
    paths = manifest.get("paths", {})
    return [
        {
            "key": "working_db",
            "kind": "file",
            "source": paths.get("working_db", {}).get("backup"),
            "destination": Path(config.WORKING_DB),
            "exists": paths.get("working_db", {}).get("exists", False),
        },
        {
            "key": "archive_db",
            "kind": "file",
            "source": paths.get("archive_db", {}).get("backup"),
            "destination": Path(config.ARCHIVE_DB),
            "exists": paths.get("archive_db", {}).get("exists", False),
        },
        {
            "key": "chroma_dir",
            "kind": "directory",
            "source": paths.get("chroma_dir", {}).get("backup"),
            "destination": Path(config.CHROMA_DIR),
            "exists": paths.get("chroma_dir", {}).get("exists", False),
        },
        {
            "key": "workspace_dir",
            "kind": "directory",
            "source": paths.get("workspace_dir", {}).get("backup"),
            "destination": Path(config.WORKSPACE_DIR),
            "exists": paths.get("workspace_dir", {}).get("exists", False),
        },
    ]


def _restore_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _restore_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def restore_backup(
    backup_path: Path,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Restore runtime state from a backup manifest.

    Restore should be run with the app stopped. Mutation requires force=True.
    """
    backup_path = Path(backup_path)
    manifest = _load_manifest(backup_path)
    targets = _planned_restore_targets(manifest)
    replace_targets = [
        {
            "key": target["key"],
            "kind": target["kind"],
            "destination": str(target["destination"]),
            "backup_entry_exists": bool(target["exists"]),
        }
        for target in targets
    ]

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "backup_path": str(backup_path),
            "app_should_be_stopped": True,
            "would_replace": replace_targets,
            "pre_restore_backup": None,
            "restored": [],
            "warnings": ["Restore should be run with the app stopped."],
        }

    if not force:
        return {
            "ok": False,
            "dry_run": False,
            "backup_path": str(backup_path),
            "error": "restore requires force=True or dry_run=True",
            "app_should_be_stopped": True,
            "would_replace": replace_targets,
            "pre_restore_backup": None,
            "restored": [],
            "warnings": ["Restore should be run with the app stopped."],
        }

    pre_restore = _create_backup_at(
        Path(config.BACKUP_DIR),
        f"pre-restore-{_utc_timestamp()}",
    )

    restored = []
    for target in targets:
        if not target["exists"]:
            continue

        source_relative = target["source"]
        if not source_relative:
            raise BackupError(f"Manifest entry missing backup path: {target['key']}")
        source = backup_path / source_relative
        if not source.exists():
            raise BackupError(f"Backup payload missing: {source}")

        destination = target["destination"]
        if target["kind"] == "file":
            _restore_file(source, destination)
        elif target["kind"] == "directory":
            _restore_directory(source, destination)
        else:
            raise BackupError(f"Unsupported restore target kind: {target['kind']}")

        restored.append({
            "key": target["key"],
            "destination": str(destination),
        })

    return {
        "ok": True,
        "dry_run": False,
        "backup_path": str(backup_path),
        "app_should_be_stopped": True,
        "would_replace": replace_targets,
        "pre_restore_backup": pre_restore["backup_path"],
        "restored": restored,
        "warnings": ["Restore should be run with the app stopped."],
    }
