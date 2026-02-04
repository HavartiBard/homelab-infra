import os
from pathlib import Path
import pytest

# Import the function from the package
from chiffon.common.paths import resolve_in_repo


def test_resolve_valid(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # create a nested file for completeness
    (repo_root / "a" / "b.txt").parent.mkdir(parents=True)
    (repo_root / "a" / "b.txt").write_text("content")

    resolved = resolve_in_repo(repo_root, "a/b.txt")
    assert resolved == repo_root / "a" / "b.txt"


def test_reject_traversal(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(ValueError) as excinfo:
        resolve_in_repo(repo_root, "../x")
    assert "escapes" in str(excinfo.value)


def test_reject_absolute(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # On non-windows use an absolute path to a temp file
    abs_file = tmp_path / "etc_passwd"
    abs_file.write_text("root:x")
    # construct absolute path string
    abs_path_str = str(abs_file)
    with pytest.raises(ValueError) as excinfo:
        resolve_in_repo(repo_root, abs_path_str)
    assert "Absolute path" in str(excinfo.value)
