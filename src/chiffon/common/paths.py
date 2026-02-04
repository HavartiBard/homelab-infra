from pathlib import Path


def resolve_in_repo(repo_root: Path, rel_path: str) -> Path:
    """Resolve a relative path within the given repository root.

    Parameters
    ----------
    repo_root : Path
        The absolute path to the repository root. It will be resolved
        internally to an absolute path.
    rel_path : str
        A *relative* filesystem path that should be interpreted as
        relative to ``repo_root``.

    Returns
    -------
    Path
        Normalised, absolute path inside the repository.

    Raises
    ------
    ValueError
        If ``rel_path`` is an absolute path or if the resolved path
        escapes the repository root (e.g. via ``..`` components).
    """
    # Ensure repo_root is absolute and canonicalised.
    repo_root = Path(repo_root).resolve()

    # Reject absolute paths outright.
    candidate = Path(rel_path)
    if candidate.is_absolute():
        raise ValueError(f"Absolute path '{rel_path}' is not allowed")

    # Resolve the candidate relative to the repository root.
    resolved = (repo_root / candidate).resolve()

    try:
        resolved.relative_to(repo_root)
    except ValueError:
        # The resolved path is outside the repo root.
        raise ValueError(
            f"Resolved path '{resolved}' escapes repository root '{repo_root}'"
        )

    return resolved
