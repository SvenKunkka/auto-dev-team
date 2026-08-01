from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class GitEvidence(BaseModel):
    branch: str = ""
    status: str = ""
    changed_files: list[str] = Field(default_factory=list)
    git_diff: str = ""


ProcessRunner = Callable[..., Any]


class GitCollector:
    """只执行固定只读Git命令。"""

    def __init__(self, runner: ProcessRunner = subprocess.run) -> None:
        self._runner = runner

    def collect(self, workspace_path: str | Path) -> GitEvidence:
        workspace = Path(workspace_path).expanduser().resolve()
        if not workspace.is_dir():
            return GitEvidence()

        branch = self._run(
            ["git", "-C", str(workspace), "branch", "--show-current"]
        )
        status = self._run(
            ["git", "-C", str(workspace), "status", "--porcelain"]
        )
        unstaged_diff = self._run(
            ["git", "-C", str(workspace), "diff", "--no-ext-diff"]
        )
        staged_diff = self._run(
            [
                "git",
                "-C",
                str(workspace),
                "diff",
                "--cached",
                "--no-ext-diff",
            ]
        )
        diffs = [part for part in (unstaged_diff, staged_diff) if part]
        return GitEvidence(
            branch=branch,
            status=status,
            changed_files=self._changed_files(status),
            git_diff="\n".join(diffs),
        )

    def _run(self, command: list[str]) -> str:
        try:
            completed = self._runner(
                command,
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if completed.returncode != 0:
            return ""
        return (completed.stdout or "").rstrip()

    @staticmethod
    def _changed_files(status: str) -> list[str]:
        changed_files: list[str] = []
        for line in status.splitlines():
            path = line[3:].strip()
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[1]
            if path:
                changed_files.append(path)
        return changed_files
