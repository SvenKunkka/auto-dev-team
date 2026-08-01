from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel


ProcessRunner = Callable[..., Any]


class GitCommitResult(BaseModel):
    created: bool
    commit_hash: str | None = None
    error: str | None = None


class GitCommitter:
    """Create one task-scoped commit without executing shell strings."""

    def __init__(self, runner: ProcessRunner = subprocess.run) -> None:
        self._runner = runner

    def commit(
        self, *, workspace_path: str | Path, task_id: str
    ) -> GitCommitResult:
        workspace = Path(workspace_path).expanduser().resolve()
        add_result = self._run(
            ["git", "-C", str(workspace), "add", "--all"]
        )
        if add_result.returncode != 0:
            return GitCommitResult(
                created=False,
                error=self._error(add_result, "git add failed"),
            )

        commit_result = self._run(
            [
                "git",
                "-C",
                str(workspace),
                "commit",
                "--no-gpg-sign",
                "-m",
                f"auto-dev({task_id}): developer changes",
            ]
        )
        if commit_result.returncode != 0:
            return GitCommitResult(
                created=False,
                error=self._error(commit_result, "git commit failed"),
            )

        hash_result = self._run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"]
        )
        commit_hash = (hash_result.stdout or "").strip()
        if hash_result.returncode != 0 or not commit_hash:
            return GitCommitResult(
                created=False,
                error=self._error(
                    hash_result, "commit created but hash lookup failed"
                ),
            )
        return GitCommitResult(created=True, commit_hash=commit_hash)

    def _run(self, command: list[str]) -> Any:
        try:
            return self._runner(
                command,
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return subprocess.CompletedProcess(
                command, returncode=1, stdout="", stderr=str(exc)
            )

    @staticmethod
    def _error(result: Any, fallback: str) -> str:
        return (
            (result.stderr or "").strip()
            or (result.stdout or "").strip()
            or fallback
        )
