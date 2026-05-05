"""Read-only runtime status helpers for Project Anam."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tir import config
from tir.memory.audit import audit_memory_integrity
from tir.memory.chroma import get_collection_count
from tir.ops.capabilities import build_capabilities_status as _build_capabilities_status


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(
            Path(config.PROJECT_ROOT).resolve(strict=False)
        ).as_posix()
    except ValueError:
        if len(path.parts) >= 2 and path.parts[-2:] == ("data", "prod"):
            return "data/prod"
        return path.name


def _check_sqlite_db(path: Path) -> dict:
    result = {
        "exists": path.exists(),
        "ok": False,
    }
    if not path.exists():
        result["error"] = "missing"
        return result

    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _chroma_status() -> dict:
    path = Path(config.CHROMA_DIR)
    status = {
        "path_exists": path.exists(),
        "count": None,
        "ok": False,
        "error": None,
    }
    try:
        status["count"] = get_collection_count()
        status["ok"] = True
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"
    return status


def _latest_backup() -> dict | None:
    backup_dir = Path(config.BACKUP_DIR)
    if not backup_dir.exists():
        return None

    candidates = [path for path in backup_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None

    latest = max(candidates, key=lambda path: path.name)
    manifest_path = latest / "manifest.json"
    latest_info = {
        "name": latest.name,
        "has_manifest": manifest_path.exists(),
        "created_at": None,
    }
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            latest_info["created_at"] = manifest.get("created_at")
        except Exception:
            latest_info["created_at"] = None
    return latest_info


def _registry_counts(registry) -> dict:
    if registry is None:
        return {
            "registry_loaded": False,
            "active_skill_count": 0,
            "active_tool_count": 0,
        }

    skill_count = len(getattr(registry, "_skills", {}) or {})
    try:
        tool_count = len(registry.list_tools())
    except Exception:
        tool_count = 0

    return {
        "registry_loaded": True,
        "active_skill_count": skill_count,
        "active_tool_count": tool_count,
    }


def build_system_health(registry=None) -> dict:
    """Return read-only runtime health for operator visibility."""
    backup_dir = Path(config.BACKUP_DIR)
    return {
        "ok": True,
        "api_ok": True,
        "project": "Project Anam",
        "timestamp": _timestamp(),
        "data_dir": {
            "exists": Path(config.DATA_DIR).exists(),
            "name": _display_path(Path(config.DATA_DIR)),
        },
        "working_db": _check_sqlite_db(Path(config.WORKING_DB)),
        "archive_db": _check_sqlite_db(Path(config.ARCHIVE_DB)),
        "chroma": _chroma_status(),
        "backups": {
            "backup_dir_exists": backup_dir.exists(),
            "latest_backup": _latest_backup(),
        },
        "external": {
            "searxng": {
                "configured": bool(config.SEARXNG_URL),
                "url": config.SEARXNG_URL,
            },
            "moltbook_token_configured": bool(os.getenv("MOLTBOOK_TOKEN")),
        },
        "skills": _registry_counts(registry),
    }


def build_memory_status() -> dict:
    """Return structured memory audit status without mutating state."""
    try:
        return {
            "ok": True,
            "audit": audit_memory_integrity(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_capabilities_status(registry=None) -> dict:
    """Return read-only capability availability and configuration status."""
    return _build_capabilities_status(registry)
