from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


ProcessRunner = Callable[..., Any]

_CACHE_DIRECTORIES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
_CACHE_SUFFIXES = {".pyc", ".pyo"}


class WorkspaceCleaner:
    """Remove only untracked, known transient cache artifacts."""

    def __init__(self, runner: ProcessRunner = subprocess.run) -> None:
        self._runner = runner

    def remove_transient_artifacts(
        self, workspace_path: str | Path
    ) -> list[str]:
        workspace = Path(workspace_path).expanduser().resolve()
        try:
            completed = self._runner(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                    "-z",
                ],
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if completed.returncode != 0:
            return []

        removed: list[str] = []
        for relative_value in (completed.stdout or "").split("\0"):
            if not relative_value:
                continue
            relative = Path(relative_value)
            if not self._is_transient(relative):
                continue
            candidate = (workspace / relative).resolve()
            if not candidate.is_relative_to(workspace) or not candidate.is_file():
                continue
            candidate.unlink()
            removed.append(relative.as_posix())
            self._remove_empty_cache_parents(candidate.parent, workspace)
        return removed

    @staticmethod
    def _is_transient(relative: Path) -> bool:
        return (
            relative.suffix.lower() in _CACHE_SUFFIXES
            or any(part in _CACHE_DIRECTORIES for part in relative.parts)
        )

    @staticmethod
    def _remove_empty_cache_parents(path: Path, workspace: Path) -> None:
        current = path
        while current != workspace:
            if current.name not in _CACHE_DIRECTORIES:
                break
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
