"""Safe internal workspace file operations.

This module defines bounded filesystem helpers for the configured workspace.
It intentionally does not expose LLM tools, API routes, UI behavior, memory
indexing, or artifact registry behavior.
"""

from pathlib import Path

from tir.config import WORKSPACE_DIR


DEFAULT_WORKSPACE_DIRS = (
    "writing",
    "coding",
    "research",
    "images",
    "moltbook",
    "journals",
    "voice",
    "vision",
    "drafts",
    "uploads",
    "generated",
    "self_mod",
    "staged_outputs",
)


class WorkspacePathError(ValueError):
    """Raised when a requested workspace path escapes or is invalid."""


def ensure_workspace(root: Path = WORKSPACE_DIR) -> Path:
    """Create the workspace root and default subdirectories if missing."""
    workspace_root = Path(root)
    workspace_root.mkdir(parents=True, exist_ok=True)

    for dirname in DEFAULT_WORKSPACE_DIRS:
        (workspace_root / dirname).mkdir(exist_ok=True)

    return workspace_root


def resolve_workspace_path(
    relative_path: str | Path = ".",
    root: Path = WORKSPACE_DIR,
    *,
    allow_root: bool = False,
) -> Path:
    """Resolve a relative path and require it to stay inside the workspace."""
    path = Path(relative_path)
    if path.is_absolute():
        raise WorkspacePathError("Workspace paths must be relative.")

    if str(path).strip() == "":
        raise WorkspacePathError("Workspace path cannot be empty.")

    if ".." in path.parts:
        raise WorkspacePathError("Workspace paths cannot contain traversal.")

    if path == Path(".") and not allow_root:
        raise WorkspacePathError("Workspace root is not valid for this operation.")

    workspace_root = Path(root).resolve()
    candidate = (workspace_root / path).resolve(strict=False)

    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise WorkspacePathError("Workspace path escapes the workspace root.") from exc

    return candidate


def _relative_display_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise WorkspacePathError("Workspace path escapes the workspace root.") from exc
    return "." if rel == Path(".") else rel.as_posix()


def list_workspace(relative_path: str | Path = ".", root: Path = WORKSPACE_DIR) -> list[dict]:
    """List files and directories under a workspace directory."""
    target = resolve_workspace_path(relative_path, root, allow_root=True)

    if not target.exists():
        raise FileNotFoundError(f"Workspace directory not found: {relative_path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Workspace path is not a directory: {relative_path}")

    workspace_root = Path(root).resolve()
    entries = []
    for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
        is_file = child.is_file()
        entries.append({
            "name": child.name,
            "path": _relative_display_path(child.resolve(strict=False), workspace_root),
            "type": "file" if is_file else "directory",
            "size": child.stat().st_size if is_file else None,
        })

    return entries


def read_workspace_file(relative_path: str | Path, root: Path = WORKSPACE_DIR) -> str:
    """Read a UTF-8 text file from inside the workspace."""
    target = resolve_workspace_path(relative_path, root)

    if not target.exists():
        raise FileNotFoundError(f"Workspace file not found: {relative_path}")
    if not target.is_file():
        raise IsADirectoryError(f"Workspace path is not a file: {relative_path}")

    return target.read_text(encoding="utf-8")


def write_workspace_file(
    relative_path: str | Path,
    content: str,
    root: Path = WORKSPACE_DIR,
) -> dict:
    """Write UTF-8 text to a workspace file, creating safe parents."""
    target = resolve_workspace_path(relative_path, root)
    parent = resolve_workspace_path(target.relative_to(Path(root).resolve()).parent, root, allow_root=True)
    parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return {
        "path": _relative_display_path(target, root),
        "bytes": target.stat().st_size,
    }


def append_workspace_file(
    relative_path: str | Path,
    content: str,
    root: Path = WORKSPACE_DIR,
) -> dict:
    """Append UTF-8 text to a workspace file, creating safe parents."""
    target = resolve_workspace_path(relative_path, root)
    parent = resolve_workspace_path(target.relative_to(Path(root).resolve()).parent, root, allow_root=True)
    parent.mkdir(parents=True, exist_ok=True)

    with target.open("a", encoding="utf-8") as handle:
        handle.write(content)

    return {
        "path": _relative_display_path(target, root),
        "bytes": target.stat().st_size,
    }


def create_workspace_dir(relative_path: str | Path, root: Path = WORKSPACE_DIR) -> dict:
    """Create a directory inside the workspace."""
    target = resolve_workspace_path(relative_path, root)
    target.mkdir(parents=True, exist_ok=True)

    return {
        "path": _relative_display_path(target, root),
        "type": "directory",
    }
