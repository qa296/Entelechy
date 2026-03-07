"""Path safety utilities."""

from pathlib import Path


def safe_path(base: Path, user_path: str) -> Path:
    """Ensure a path does not escape the base directory.

    Args:
        base: The base directory that must contain the resolved path.
        user_path: The user-provided relative path string.

    Returns:
        The resolved Path.

    Raises:
        ValueError: If the resolved path escapes the base directory.
    """
    resolved = (base / user_path).resolve()
    base_resolved = base.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        raise ValueError(f"Path escapes workspace: {user_path}")
    return resolved
