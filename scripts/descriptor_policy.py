"""Pinned static Reader descriptor limits shared by publication checks."""

from pathlib import Path

MAX_DESCRIPTOR_BYTES = 16 * 1024 * 1024
DESCRIPTOR_PATH = "graph/okf-explorer.json"


def validate_descriptor_size(site):
    """Fail closed when the full-graph descriptor exceeds the deployed Reader limit."""
    site = Path(site)
    descriptor = site / DESCRIPTOR_PATH
    if (site.is_symlink() or not site.is_dir() or descriptor.is_symlink()
            or descriptor.parent.is_symlink() or not descriptor.is_file()
            or not descriptor.resolve().is_relative_to(site.resolve())):
        raise ValueError("The full-graph descriptor must be a regular file inside the published site.")
    size = descriptor.stat().st_size
    if size > MAX_DESCRIPTOR_BYTES:
        raise ValueError(
            f"The full-graph descriptor exceeds the pinned Reader limit "
            f"({size} bytes; maximum {MAX_DESCRIPTOR_BYTES})."
        )
    return size
