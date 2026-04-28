import os
from pathlib import Path

import pytest

from tir.workspace.service import (
    DEFAULT_WORKSPACE_DIRS,
    WorkspacePathError,
    append_workspace_file,
    create_workspace_dir,
    ensure_workspace,
    list_workspace,
    read_workspace_file,
    resolve_workspace_path,
    write_workspace_file,
)


def test_ensure_workspace_creates_default_directories(tmp_path):
    root = tmp_path / "workspace"

    result = ensure_workspace(root)

    assert result == root
    assert root.is_dir()
    for dirname in DEFAULT_WORKSPACE_DIRS:
        assert (root / dirname).is_dir()


def test_write_read_append_list_and_create_dir(tmp_path):
    root = tmp_path / "workspace"
    ensure_workspace(root)

    created = create_workspace_dir("research/session-1", root)
    assert created == {"path": "research/session-1", "type": "directory"}

    written = write_workspace_file("research/session-1/notes.txt", "first", root)
    assert written["path"] == "research/session-1/notes.txt"
    assert written["bytes"] == 5

    appended = append_workspace_file("research/session-1/notes.txt", "\nsecond", root)
    assert appended["path"] == "research/session-1/notes.txt"
    assert read_workspace_file("research/session-1/notes.txt", root) == "first\nsecond"

    entries = list_workspace("research/session-1", root)
    assert entries == [
        {
            "name": "notes.txt",
            "path": "research/session-1/notes.txt",
            "type": "file",
            "size": appended["bytes"],
        }
    ]


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.txt",
        "research/../../outside.txt",
    ],
)
def test_traversal_is_rejected(tmp_path, bad_path):
    root = tmp_path / "workspace"
    ensure_workspace(root)

    with pytest.raises(WorkspacePathError):
        resolve_workspace_path(bad_path, root)


def test_absolute_path_is_rejected(tmp_path):
    root = tmp_path / "workspace"
    ensure_workspace(root)

    with pytest.raises(WorkspacePathError):
        resolve_workspace_path(tmp_path / "outside.txt", root)


def test_symlink_escape_is_rejected(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink not available on this platform")

    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    ensure_workspace(root)
    outside.mkdir()

    link = root / "research" / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not available: {exc}")

    with pytest.raises(WorkspacePathError):
        resolve_workspace_path("research/escape/file.txt", root)


def test_listing_symlink_escape_is_rejected(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink not available on this platform")

    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    ensure_workspace(root)
    outside.mkdir()

    link = root / "research" / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not available: {exc}")

    with pytest.raises(WorkspacePathError):
        list_workspace("research", root)


def test_reading_directory_fails(tmp_path):
    root = tmp_path / "workspace"
    ensure_workspace(root)

    with pytest.raises(IsADirectoryError):
        read_workspace_file("research", root)


def test_listing_missing_directory_fails(tmp_path):
    root = tmp_path / "workspace"
    ensure_workspace(root)

    with pytest.raises(FileNotFoundError):
        list_workspace("missing", root)


def test_listing_file_as_directory_fails(tmp_path):
    root = tmp_path / "workspace"
    ensure_workspace(root)
    write_workspace_file("research/file.txt", "content", root)

    with pytest.raises(NotADirectoryError):
        list_workspace("research/file.txt", root)


def test_module_import_does_not_create_real_workspace():
    import tir.config as config

    assert isinstance(config.WORKSPACE_DIR, Path)
