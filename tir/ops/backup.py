"""Filesystem backup and restore helpers for Project Anam runtime state."""

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
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
GOVERNANCE_FILE_NAMES = (
    "BEHAVIORAL_GUIDANCE.md",
    "OPERATIONAL_GUIDANCE.md",
    "soul.md",
    "PROJECT_STATE.md",
    "DECISIONS.md",
    "ROADMAP.md",
    "ACTIVE_TASK.md",
    "CODING_ASSISTANT_RULES.md",
)
WORKING_DB_VERIFY_TABLES = (
    "schema_versions",
    "users",
    "conversations",
    "messages",
    "artifacts",
    "open_loops",
    "review_items",
    "behavioral_guidance_proposals",
)
ARCHIVE_DB_VERIFY_TABLES = (
    "users",
    "messages",
)
WORKSPACE_VERIFY_SUBPATHS = (
    "research",
    "journals",
    "research/source-traces",
    "uploads",
)


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


def _copy_optional_file(source: Path, destination: Path, relative_destination: str) -> dict:
    info = {
        "source": str(source),
        "backup": relative_destination,
        "exists": source.exists(),
    }
    if not source.exists():
        return info

    if not source.is_file():
        raise BackupError(f"Expected file, found non-file: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    info.update({
        "bytes": destination.stat().st_size,
        "sha256": _sha256_file(destination),
    })
    return info


def _backup_governance_files(backup_path: Path) -> dict:
    governance_dir = backup_path / "governance"
    entries = {}
    for name in GOVERNANCE_FILE_NAMES:
        entries[name] = _copy_optional_file(
            Path(config.PROJECT_ROOT) / name,
            governance_dir / name,
            f"governance/{name}",
        )
    return entries


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
    manifest["governance_files"] = _backup_governance_files(backup_path)
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


def find_latest_backup(root: Path | None = None) -> Path:
    """Return the latest backup directory that contains a manifest."""
    backup_root = Path(root) if root is not None else Path(config.BACKUP_DIR)
    if not backup_root.exists():
        raise BackupError(f"Backup root not found: {backup_root}")

    candidates = [
        path for path in backup_root.iterdir()
        if path.is_dir() and (path / "manifest.json").exists()
    ]
    if not candidates:
        raise BackupError(f"No backups with manifest.json found in: {backup_root}")
    return max(candidates, key=lambda path: path.name)


def _target_is_non_empty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def _prepare_verify_target(target_dir: Path, overwrite_target: bool) -> None:
    if target_dir.exists() and not target_dir.is_dir():
        raise BackupError(f"Verification target exists and is not a directory: {target_dir}")

    if _target_is_non_empty(target_dir):
        if not overwrite_target:
            raise BackupError(
                f"Verification target directory is not empty: {target_dir}"
            )
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)


def _manifest_path_entry(manifest: dict, key: str) -> dict:
    entry = manifest.get("paths", {}).get(key)
    if not isinstance(entry, dict):
        raise BackupError(f"Backup manifest is missing paths.{key}")
    return entry


def _copy_manifest_file(
    backup_path: Path,
    entry: dict,
    destination: Path,
    key: str,
) -> dict:
    expected = bool(entry.get("exists", False))
    copied = {
        "key": key,
        "expected": expected,
        "destination": str(destination),
        "copied": False,
    }
    if not expected:
        return copied

    source_relative = entry.get("backup")
    if not source_relative:
        raise BackupError(f"Manifest entry missing backup path: {key}")
    source = backup_path / source_relative
    if not source.exists():
        raise BackupError(f"Backup payload missing for {key}: {source}")
    if not source.is_file():
        raise BackupError(f"Expected backup file for {key}: {source}")

    _restore_file(source, destination)
    copied["copied"] = True
    return copied


def _copy_manifest_directory(
    backup_path: Path,
    entry: dict,
    destination: Path,
    key: str,
) -> dict:
    expected = bool(entry.get("exists", False))
    copied = {
        "key": key,
        "expected": expected,
        "destination": str(destination),
        "copied": False,
    }
    if not expected:
        return copied

    source_relative = entry.get("backup")
    if not source_relative:
        raise BackupError(f"Manifest entry missing backup path: {key}")
    source = backup_path / source_relative
    if not source.exists():
        raise BackupError(f"Backup payload missing for {key}: {source}")
    if not source.is_dir():
        raise BackupError(f"Expected backup directory for {key}: {source}")

    _restore_directory(source, destination)
    copied["copied"] = True
    return copied


def _sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _verify_sqlite_db(
    path: Path,
    *,
    required_tables: tuple[str, ...],
    require_schema_versions: bool = False,
) -> dict:
    result = {
        "exists": path.exists(),
        "opens": False,
        "ok": False,
        "quick_check": None,
        "schema_versions": [],
        "table_counts": {},
        "errors": [],
    }
    if not path.exists():
        result["errors"].append("missing")
        return result

    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            result["opens"] = True
            quick_check = conn.execute("PRAGMA quick_check").fetchone()
            result["quick_check"] = quick_check[0] if quick_check else None
            if result["quick_check"] != "ok":
                result["errors"].append(f"quick_check={result['quick_check']}")

            for table_name in required_tables:
                if not _sqlite_table_exists(conn, table_name):
                    result["errors"].append(f"missing table: {table_name}")
                    continue
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                result["table_counts"][table_name] = count

            if require_schema_versions and _sqlite_table_exists(conn, "schema_versions"):
                rows = conn.execute(
                    "SELECT version, name FROM schema_versions ORDER BY version"
                ).fetchall()
                result["schema_versions"] = [
                    {"version": row[0], "name": row[1]} for row in rows
                ]
                if not result["schema_versions"]:
                    result["errors"].append("schema_versions is empty")
            elif require_schema_versions:
                result["errors"].append("missing table: schema_versions")
        finally:
            conn.close()
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    result["ok"] = result["exists"] and result["opens"] and not result["errors"]
    return result


def _path_readability(path: Path, expected: bool, *, kind: str) -> dict:
    result = {
        "expected": expected,
        "exists": path.exists(),
        "readable": False,
        "ok": not expected,
    }
    if not expected:
        return result

    if not path.exists():
        result["error"] = "missing"
        return result

    if kind == "directory" and not path.is_dir():
        result["error"] = "not a directory"
        return result
    if kind == "file" and not path.is_file():
        result["error"] = "not a file"
        return result

    try:
        if kind == "directory":
            list(path.iterdir())
        else:
            with path.open("rb") as handle:
                handle.read(1)
        result["readable"] = True
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _verify_hash(path: Path, entry: dict, key: str) -> dict | None:
    expected_hash = entry.get("sha256")
    if not expected_hash:
        return None
    result = {
        "key": key,
        "expected_sha256": expected_hash,
        "actual_sha256": None,
        "ok": False,
    }
    if not path.exists() or not path.is_file():
        result["error"] = "missing"
        return result
    actual_hash = _sha256_file(path)
    result["actual_sha256"] = actual_hash
    result["ok"] = actual_hash == expected_hash
    return result


def _workspace_report(workspace_path: Path, expected: bool) -> dict:
    report = _path_readability(workspace_path, expected, kind="directory")
    subpaths = {}
    for relative in WORKSPACE_VERIFY_SUBPATHS:
        subpath = workspace_path / relative
        subpaths[relative] = {
            "exists": subpath.exists(),
            "readable": False,
        }
        if subpath.exists():
            try:
                list(subpath.iterdir())
                subpaths[relative]["readable"] = True
            except Exception as exc:
                subpaths[relative]["error"] = f"{type(exc).__name__}: {exc}"
    report["subpaths"] = subpaths
    return report


def _governance_report(target_dir: Path, manifest: dict) -> dict:
    entries = {}
    all_ok = True
    for name, entry in manifest.get("governance_files", {}).items():
        expected = bool(entry.get("exists", False))
        path = target_dir / "governance" / name
        item = _path_readability(path, expected, kind="file")
        entries[name] = item
        all_ok = all_ok and item["ok"]
    return {
        "ok": all_ok,
        "files": entries,
    }


def verify_backup_restore(
    backup_path: Path,
    target_dir: Path,
    *,
    overwrite_target: bool = False,
) -> dict:
    """Restore a backup into an isolated target and verify restored state.

    This helper never writes to configured runtime paths. It copies backup
    payloads into ``target_dir`` and performs read-only verification there.
    """
    backup_path = Path(backup_path)
    target_dir = Path(target_dir)
    manifest = _load_manifest(backup_path)
    _prepare_verify_target(target_dir, overwrite_target)

    working_entry = _manifest_path_entry(manifest, "working_db")
    archive_entry = _manifest_path_entry(manifest, "archive_db")
    chroma_entry = _manifest_path_entry(manifest, "chroma_dir")
    workspace_entry = _manifest_path_entry(manifest, "workspace_dir")

    target_working_db = target_dir / "data" / "prod" / "working.db"
    target_archive_db = target_dir / "data" / "prod" / "archive.db"
    target_chroma_dir = target_dir / "data" / "prod" / "chromadb"
    target_workspace_dir = target_dir / "workspace"

    restored = [
        _copy_manifest_file(backup_path, working_entry, target_working_db, "working_db"),
        _copy_manifest_file(backup_path, archive_entry, target_archive_db, "archive_db"),
        _copy_manifest_directory(backup_path, chroma_entry, target_chroma_dir, "chroma_dir"),
        _copy_manifest_directory(
            backup_path,
            workspace_entry,
            target_workspace_dir,
            "workspace_dir",
        ),
    ]

    for name, entry in manifest.get("governance_files", {}).items():
        restored.append(
            _copy_manifest_file(
                backup_path,
                entry,
                target_dir / "governance" / name,
                f"governance:{name}",
            )
        )

    hash_checks = [
        check for check in (
            _verify_hash(target_working_db, working_entry, "working_db"),
            _verify_hash(target_archive_db, archive_entry, "archive_db"),
            *(
                _verify_hash(target_dir / "governance" / name, entry, f"governance:{name}")
                for name, entry in manifest.get("governance_files", {}).items()
            ),
        )
        if check is not None
    ]

    working_db = _verify_sqlite_db(
        target_working_db,
        required_tables=WORKING_DB_VERIFY_TABLES,
        require_schema_versions=True,
    )
    archive_db = _verify_sqlite_db(
        target_archive_db,
        required_tables=ARCHIVE_DB_VERIFY_TABLES,
    )
    chroma = _path_readability(
        target_chroma_dir,
        bool(chroma_entry.get("exists", False)),
        kind="directory",
    )
    workspace = _workspace_report(
        target_workspace_dir,
        bool(workspace_entry.get("exists", False)),
    )
    governance = _governance_report(target_dir, manifest)
    hashes_ok = all(check["ok"] for check in hash_checks)

    ok = all((
        working_db["ok"],
        archive_db["ok"],
        chroma["ok"],
        workspace["ok"],
        governance["ok"],
        hashes_ok,
    ))

    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "backup_path": str(backup_path),
        "target_dir": str(target_dir),
        "manifest": {
            "backup_version": manifest.get("backup_version"),
            "project": manifest.get("project"),
            "created_at": manifest.get("created_at"),
        },
        "restored": restored,
        "working_db": working_db,
        "archive_db": archive_db,
        "chroma": chroma,
        "workspace": workspace,
        "governance_files": governance,
        "hash_checks": hash_checks,
        "hashes_ok": hashes_ok,
        "active_environment_mutated": False,
    }


def _planned_restore_targets(manifest: dict) -> list[dict[str, Any]]:
    paths = manifest.get("paths", {})
    targets = [
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

    for name, entry in manifest.get("governance_files", {}).items():
        targets.append({
            "key": f"governance:{name}",
            "kind": "file",
            "source": entry.get("backup"),
            "destination": Path(config.PROJECT_ROOT) / name,
            "exists": entry.get("exists", False),
        })

    return targets


def _restore_temp_path(destination: Path, *, kind: str) -> Path:
    name = f".{destination.name}.restore-{kind}-{uuid.uuid4().hex}"
    return destination.parent / name


def _validate_restore_sources(
    backup_path: Path,
    targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate every restore payload before touching any destination."""
    validated = []
    for target in targets:
        if not target["exists"]:
            continue

        source_relative = target["source"]
        if not source_relative:
            raise BackupError(f"Manifest entry missing backup path: {target['key']}")

        source = backup_path / source_relative
        if not source.exists():
            raise BackupError(f"Backup payload missing for {target['key']}: {source}")

        if target["kind"] == "file" and not source.is_file():
            raise BackupError(f"Expected backup file for {target['key']}: {source}")
        if target["kind"] == "directory" and not source.is_dir():
            raise BackupError(f"Expected backup directory for {target['key']}: {source}")
        if target["kind"] not in {"file", "directory"}:
            raise BackupError(f"Unsupported restore target kind: {target['kind']}")

        validated.append({
            **target,
            "source_path": source,
        })
    return validated


def _restore_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise BackupError(f"Backup payload missing: {source}")
    if not source.is_file():
        raise BackupError(f"Expected backup file: {source}")
    if destination.exists() and destination.is_dir():
        raise BackupError(f"Cannot restore file over directory: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _restore_temp_path(destination, kind="file")
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _restore_directory(source: Path, destination: Path) -> None:
    if not source.exists():
        raise BackupError(f"Backup payload missing: {source}")
    if not source.is_dir():
        raise BackupError(f"Expected backup directory: {source}")
    if destination.exists() and not destination.is_dir():
        raise BackupError(f"Cannot restore directory over non-directory: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _restore_temp_path(destination, kind="dir")
    old_path = _restore_temp_path(destination, kind="old")
    copied = False
    old_moved = False
    try:
        shutil.copytree(source, temp_path)
        copied = True
        if destination.exists():
            destination.rename(old_path)
            old_moved = True
        temp_path.rename(destination)
        copied = False
        if old_moved and old_path.exists():
            shutil.rmtree(old_path)
            old_moved = False
    except Exception:
        if copied and temp_path.exists():
            shutil.rmtree(temp_path)
        if old_moved and old_path.exists() and not destination.exists():
            old_path.rename(destination)
            old_moved = False
        raise
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path)
        if old_moved and old_path.exists():
            shutil.rmtree(old_path)


def _restore_target(target: dict[str, Any]) -> dict[str, str]:
    destination = target["destination"]
    if target["kind"] == "file":
        _restore_file(target["source_path"], destination)
    elif target["kind"] == "directory":
        _restore_directory(target["source_path"], destination)
    else:
        raise BackupError(f"Unsupported restore target kind: {target['kind']}")
    return {
        "key": target["key"],
        "destination": str(destination),
    }


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

    validated_targets = _validate_restore_sources(backup_path, targets)

    pre_restore = _create_backup_at(
        Path(config.BACKUP_DIR),
        f"pre-restore-{_utc_timestamp()}",
    )

    restored = []
    for target in validated_targets:
        restored.append(_restore_target(target))

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
