from __future__ import annotations

from pathlib import PurePosixPath

from .paths import SecurityError


def _parse_header(line: str) -> str:
    if not line.startswith("+++ b/"):
        raise SecurityError("Unified diff must use +++ b/<path> headers")
    path = line[6:].split("\t", 1)[0].strip()
    if not path or path.startswith("/") or ".." in PurePosixPath(path).parts:
        raise SecurityError("Unsafe path in diff")
    return path


def apply_unified_diff(files: dict[str, str], diff: str) -> dict[str, str]:
    """Apply a conservative unified diff to an in-memory file map.

    Only existing files are supported in the assessment MVP. Binary patches and
    rename/delete operations are rejected so the approval boundary stays simple.
    """
    lines = diff.splitlines()
    result = dict(files)
    i = 0
    while i < len(lines):
        if not lines[i].startswith("--- "):
            i += 1
            continue
        if i + 1 >= len(lines):
            raise SecurityError("Incomplete unified diff")
        old_header = lines[i]
        new_path = _parse_header(lines[i + 1])
        if not old_header.startswith("--- a/"):
            raise SecurityError("Unified diff must use --- a/<path> headers")
        old_path = old_header[6:].split("\t", 1)[0].strip()
        if old_path != new_path or old_path not in result:
            raise SecurityError(f"Diff may only modify existing files: {new_path}")
        original = result[old_path].splitlines()
        output: list[str] = []
        pos = 0
        i += 2
        while i < len(lines) and lines[i].startswith("@@"):
            header = lines[i]
            try:
                old_range = header.split(" ")[1]
                old_start = int(old_range.split(",")[0].lstrip("-"))
            except Exception as exc:
                raise SecurityError("Malformed diff hunk") from exc
            target_index = old_start - 1
            if target_index < pos or target_index > len(original):
                raise SecurityError("Diff hunk is outside file bounds")
            output.extend(original[pos:target_index])
            i += 1
            while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("--- "):
                line = lines[i]
                if line.startswith(" "):
                    expected = line[1:]
                    if pos >= len(original) or original[pos] != expected:
                        raise SecurityError("Diff context does not match repository")
                    output.append(original[pos]); pos += 1
                elif line.startswith("-"):
                    expected = line[1:]
                    if pos >= len(original) or original[pos] != expected:
                        raise SecurityError("Diff deletion does not match repository")
                    pos += 1
                elif line.startswith("+"):
                    output.append(line[1:])
                elif line == "\\ No newline at end of file":
                    pass
                else:
                    raise SecurityError("Unsupported unified diff line")
                i += 1
        output.extend(original[pos:])
        result[old_path] = "\n".join(output) + ("\n" if result[old_path].endswith("\n") else "")
    if result == files:
        raise SecurityError("Diff contains no applicable file changes")
    return result
