"""Resolve canonical relative paths beneath an explicit filesystem root."""

from pathlib import Path
import os


def safe_component(value):
    """Require one path component while retaining the original identifier."""
    text = str(value)
    if text in ("", ".", "..") or any(character in text for character in ("/", "\\", "\x00")):
        raise ValueError("A Hansard identifier is not a single path component.")
    return text


def resolve_within(root, relative):
    """Return a path below ``root``; reject non-canonical paths and symlinks.

    Relative paths use forward slashes and may contain nested components, but
    never absolute paths, empty components, dot components or backslashes.
    Existing symlink components are rejected for both reads and writes.
    """
    root = Path(root)
    raw = os.fspath(relative)
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        raise ValueError("Expected a canonical relative path")
    components = raw.split("/")
    if raw.startswith("/") or any(part in ("", ".", "..") for part in components):
        raise ValueError("Expected a canonical relative path")

    boundary = root.resolve(strict=True)
    if not boundary.is_dir():
        raise ValueError("Path root is not a directory")
    candidate = boundary
    for component in components:
        candidate = candidate / component
        if candidate.is_symlink():
            raise ValueError(f"Symlink path component is not allowed: {raw}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(boundary)
    except ValueError:
        raise ValueError(f"Path escapes its root: {raw}") from None
    return candidate
