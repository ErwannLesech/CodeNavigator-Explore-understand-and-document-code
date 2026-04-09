from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
import re

from git import Repo

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".sql": "sql",
    ".js": "javascript",
    ".ts": "typescript",
}

IGNORED_DIRS = {".venv", "node_modules", "__pycache__", ".git", "dist", "build"}


@dataclass
class SourceFile:
    path: Path
    language: str
    content: str
    relative_path: str


def _is_git_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "git@")) or value.endswith(".git")


def _normalize_git_url(value: str) -> str:
    normalized = value.strip()

    # If a URL was accidentally wrapped in Path on Windows, backslashes can appear.
    if normalized.startswith(("http:/", "https:/")):
        normalized = normalized.replace("\\", "/")

    # Repair single-slash scheme forms like https:/github.com/... into https://github.com/...
    normalized = re.sub(r"^(https?):/(?!/)", r"\1://", normalized)

    return normalized


def walk_repo(root: str | Path) -> Iterator[SourceFile]:
    root_str = str(root)

    if _is_git_url(root_str):
        git_url = _normalize_git_url(root_str)
        with TemporaryDirectory(prefix="CodeNavigator_repo_") as tmp_dir:
            clone_path = Path(tmp_dir) / "repo"
            Repo.clone_from(git_url, clone_path)
            yield from _walk_local_repo(clone_path)
        return

    yield from _walk_local_repo(Path(root_str))


def _walk_local_repo(root: Path) -> Iterator[SourceFile]:
    if not root.exists() or not root.is_dir():
        raise ValueError(
            f"Repository path does not exist or is not a directory: {root}"
        )

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue

        if file_path.suffix not in SUPPORTED_EXTENSIONS:
            continue

        if any(part in IGNORED_DIRS for part in file_path.parts):
            continue

        try:
            content = file_path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue

        yield SourceFile(
            path=file_path,
            language=SUPPORTED_EXTENSIONS[file_path.suffix],
            content=content,
            relative_path=str(file_path.relative_to(root)),
        )
