"""Shared directory/file ignore rules for project walks and indexing."""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Aligned with project_scanner skip_dirs plus .next for frontend builds.
DEFAULT_SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
        "target",
        ".next",
        ".pytest_cache",
        ".mypy_cache",
        ".idea",
        ".vscode",
        "bin",
        "obj",
        ".vs",
        "coverage",
        ".coverage",
    }
)


@dataclass
class FileScanStats:
    """Counts from walking a project tree for indexable files."""

    files_indexed: int = 0
    files_skipped_ignore: int = 0
    files_skipped_extension: int = 0
    dirs_skipped: int = 0
    skipped_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, int]:
        return {
            "files_indexed": self.files_indexed,
            "files_skipped_ignore": self.files_skipped_ignore,
            "files_skipped_extension": self.files_skipped_extension,
            "dirs_skipped": self.dirs_skipped,
        }


class GitIgnoreMatcher:
    """Minimal .gitignore matcher (root file; last matching rule wins)."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self._rules: list[tuple[str, bool, bool]] = []
        gitignore_path = self.project_root / ".gitignore"
        if gitignore_path.is_file():
            self._load_lines(gitignore_path.read_text(encoding="utf-8", errors="replace").splitlines())

    def _load_lines(self, lines: list[str]) -> None:
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            if negated:
                line = line[1:].strip()
            dir_only = line.endswith("/")
            if dir_only:
                line = line.rstrip("/")
            if line:
                self._rules.append((line, negated, dir_only))

    def is_ignored(self, rel_path: str, *, is_dir: bool = False) -> bool:
        if not self._rules:
            return False

        rel = rel_path.replace("\\", "/").lstrip("./")
        if not rel:
            return False

        ignored = False
        for pattern, negated, dir_only in self._rules:
            if dir_only and not is_dir:
                continue
            if self._matches(pattern, rel, is_dir=is_dir):
                ignored = not negated
        return ignored

    def _matches(self, pattern: str, rel_path: str, *, is_dir: bool) -> bool:
        path = rel_path.rstrip("/")
        if pattern.startswith("/"):
            anchored = pattern.lstrip("/")
            if fnmatch.fnmatchcase(path, anchored):
                return True
            if is_dir and fnmatch.fnmatchcase(path, anchored.rstrip("/")):
                return True
            return path.startswith(anchored + "/")

        basename = path.rsplit("/", 1)[-1]
        if fnmatch.fnmatchcase(basename, pattern):
            return True
        if fnmatch.fnmatchcase(path, pattern):
            return True
        if fnmatch.fnmatchcase(path, f"*/{pattern}"):
            return True
        return fnmatch.fnmatchcase(path, f"**/{pattern}")


def enumerate_indexable_files(
    project_root: Path,
    extensions: frozenset[str],
    *,
    skip_dirs: frozenset[str] | None = None,
    respect_gitignore: bool = True,
) -> tuple[list[Path], FileScanStats]:
    """Walk project_root and return indexable files plus skip statistics."""
    root = project_root.resolve()
    skip = skip_dirs or DEFAULT_SKIP_DIRS
    gitignore = GitIgnoreMatcher(root) if respect_gitignore else None
    stats = FileScanStats()
    indexed: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""

        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            rel_child_dir = f"{rel_dir}/{dirname}" if rel_dir else dirname
            if dirname in skip:
                stats.dirs_skipped += 1
                stats.skipped_paths.append(rel_child_dir + "/")
                continue
            if gitignore and gitignore.is_ignored(rel_child_dir, is_dir=True):
                stats.dirs_skipped += 1
                stats.skipped_paths.append(rel_child_dir + "/")
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current / filename
            rel_file = path.relative_to(root).as_posix()

            if gitignore and gitignore.is_ignored(rel_file, is_dir=False):
                stats.files_skipped_ignore += 1
                stats.skipped_paths.append(rel_file)
                continue

            if path.suffix.lower() not in extensions:
                stats.files_skipped_extension += 1
                continue

            if path.is_file():
                indexed.append(path.resolve())
                stats.files_indexed += 1

    logger.info(
        "Project scan under %s: indexed=%s ignored=%s extension_skipped=%s dirs_skipped=%s",
        root,
        stats.files_indexed,
        stats.files_skipped_ignore,
        stats.files_skipped_extension,
        stats.dirs_skipped,
    )
    return indexed, stats
