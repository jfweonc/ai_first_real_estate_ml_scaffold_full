from __future__ import annotations

import ast
from pathlib import Path

BASE_ALLOWLIST: set[str] = {".vscode/tasks.json"}


class PatchError(Exception):
    """Raised when applying a patch fails validation."""


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def _is_safe_relpath(path: str) -> bool:
    path = _normalize(path)
    if not path or path.startswith(("/", "\\")):
        return False
    parts = [part for part in path.split("/") if part not in ("", ".")]
    return all(part != ".." for part in parts)


def read_manifest_targets(manifest_path: Path) -> set[str]:
    """Parse the `targets` list from the phase manifest (minimal YAML reader)."""

    targets: set[str] = set(BASE_ALLOWLIST)
    if not manifest_path.exists():
        return targets
    in_targets = False
    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not in_targets and line.strip().startswith("targets:"):
            in_targets = True
            continue
        if in_targets:
            stripped = line.strip()
            if stripped.startswith("- "):
                targets.add(_normalize(stripped[2:].strip()))
            elif stripped and not stripped.startswith("#"):
                break
    return targets


def _ensure_allowed(path: str, allowlist: set[str]) -> None:
    norm = _normalize(path)
    if norm not in allowlist:
        raise PatchError(f"path not in allowlist: {norm}")
    if not _is_safe_relpath(norm):
        raise PatchError(f"unsafe path: {norm}")


def _write_file(repo_root: Path, rel_path: str, content: str) -> None:
    dest = repo_root / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8", newline="\n")


def _assert_python_parses(rel_path: str, content: str) -> None:
    if rel_path.endswith(".py"):
        try:
            ast.parse(content, filename=rel_path)
        except SyntaxError as exc:  # pragma: no cover - detailed in message
            raise PatchError(f"AST parse failed for {rel_path}: {exc}") from exc


def _consume_add(lines: list[str], idx: int, *, repo_root: Path, allowlist: set[str], changed: list[str]) -> int:
    rel = _normalize(lines[idx].split(":", 1)[1].strip())
    _ensure_allowed(rel, allowlist)
    idx += 1
    body: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("***"):
            break
        if line.startswith("+"):
            body.append(line[1:])
        elif line == "":
            body.append("")
        else:
            raise PatchError("unexpected line in Add File block")
        idx += 1
    content = "\n".join(body)
    if body and not content.endswith("\n"):
        content += "\n"
    _assert_python_parses(rel, content)
    _write_file(repo_root, rel, content)
    changed.append(rel)
    return idx


def _consume_update(lines: list[str], idx: int, *, repo_root: Path, allowlist: set[str], changed: list[str]) -> int:
    rel = _normalize(lines[idx].split(":", 1)[1].strip())
    _ensure_allowed(rel, allowlist)
    idx += 1
    new_lines: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("***"):
            break
        if line.startswith("@@"):
            idx += 1
            continue
        if line.startswith("+") or line.startswith(" "):
            new_lines.append(line[1:])
        elif line.startswith("-"):
            pass
        elif line == "":
            new_lines.append("")
        else:
            raise PatchError("unexpected line in Update File hunk")
        idx += 1
    if not new_lines:
        existing = repo_root / rel
        content = existing.read_text(encoding="utf-8") if existing.exists() else ""
    else:
        content = "\n".join(new_lines)
        if not content.endswith("\n"):
            content += "\n"
    _assert_python_parses(rel, content)
    _write_file(repo_root, rel, content)
    changed.append(rel)
    return idx


def apply_patch_text(patch_text: str, *, repo_root: Path, allowlist: set[str]) -> list[str]:
    lines = patch_text.splitlines()
    idx = 0
    changed: list[str] = []
    while idx < len(lines):
        if lines[idx].strip() != "*** Begin Patch":
            idx += 1
            continue
        idx += 1
        while idx < len(lines) and lines[idx].strip() != "*** End Patch":
            line = lines[idx]
            if line.startswith("*** Add File: "):
                idx = _consume_add(lines, idx, repo_root=repo_root, allowlist=allowlist, changed=changed)
                continue
            if line.startswith("*** Update File: "):
                idx = _consume_update(lines, idx, repo_root=repo_root, allowlist=allowlist, changed=changed)
                continue
            idx += 1
        if idx < len(lines) and lines[idx].strip() == "*** End Patch":
            idx += 1
    return changed


def apply_patch_file(patch_file: Path, *, repo_root: Path, manifest_path: Path) -> list[str]:
    if not patch_file.exists():
        raise PatchError(f"patch file not found: {patch_file}")
    allowlist = read_manifest_targets(manifest_path)
    if not allowlist:
        raise PatchError("no allowlisted targets found in manifest")
    text = patch_file.read_text(encoding="utf-8")
    return apply_patch_text(text, repo_root=repo_root, allowlist=allowlist)
