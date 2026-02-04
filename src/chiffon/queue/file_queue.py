from pathlib import Path
import yaml


def next_task_file(queue_dir: Path) -> Path | None:
    """Return the first YAML file in queue_dir sorted lexicographically."""
    if not queue_dir.is_dir():
        raise ValueError(f"{queue_dir} is not a directory")
    # Collect .yml and .yaml files
    files = list(queue_dir.glob("*.yml")) + list(queue_dir.glob("*.yaml"))
    if not files:
        return None
    files.sort(key=lambda p: p.name)
    return files[0]


def load_task(path: Path) -> dict:
    """Load and validate a task YAML file.

    Required keys: id (str), goal (str).
    Optional keys: edits, verify – must be lists if present; default to [].
    Raises ValueError with informative message on parse or validation errors.
    """
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse YAML at {path}: {e}") from e
    if not isinstance(content, dict):
        raise ValueError(f"YAML content is not a mapping at {path}")
    # Required fields
    for key in ("id", "goal"):
        if key not in content:
            raise ValueError(f"Missing required key '{key}' in task file {path}")
        if not isinstance(content[key], str):
            raise ValueError(f"Key '{key}' must be a string in task file {path}")
    # Optional lists
    edits = content.get("edits", [])
    verify = content.get("verify", [])
    if not isinstance(edits, list):
        raise ValueError(f"'edits' must be a list in task file {path}")
    if not isinstance(verify, list):
        raise ValueError(f"'verify' must be a list in task file {path}")
    # Return cleaned dict
    return {
        "id": content["id"],
        "goal": content["goal"],
        "edits": edits,
        "verify": verify,
    }
