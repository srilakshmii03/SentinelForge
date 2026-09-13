from __future__ import annotations

from pathlib import Path


class SecurityError(ValueError):
    pass


def safe_join(root: Path, relative: str) -> Path:
    if not relative or "\x00" in relative:
        raise SecurityError("Invalid path")
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SecurityError("Path escapes assigned workspace") from exc
    return candidate


def reject_symlink_escape(root: Path, relative: str) -> Path:
    candidate = safe_join(root, relative)
    current = candidate
    while current != root.resolve() and current != current.parent:
        if current.is_symlink():
            target = current.resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError as exc:
                raise SecurityError("Symlink escapes assigned workspace") from exc
        current = current.parent
    return candidate
