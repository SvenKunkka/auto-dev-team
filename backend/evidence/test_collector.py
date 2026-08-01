from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

__test__ = False


class TestExecutionResult(BaseModel):
    command: list[str]
    stdout: str
    stderr: str
    exit_code: int | None
    error: str | None = None


ProcessRunner = Callable[..., Any]


class TestCollector:
    """只执行Supervisor required_tests中的受控测试命令。"""

    _ALLOWED_PREFIXES = (
        ("pytest",),
        ("uv", "run", "pytest"),
        ("python", "-m", "pytest"),
        ("python3", "-m", "pytest"),
        ("python", "-m", "unittest"),
        ("python3", "-m", "unittest"),
        ("npm", "test"),
        ("npm", "run", "test"),
        ("npm", "run", "build"),
        ("npm", "run", "lint"),
        ("npm", "run", "test:postgres-schema"),
        ("npm", "run", "test:postgres"),
        ("pnpm", "test"),
        ("pnpm", "run", "test"),
        ("yarn", "test"),
        ("cargo", "test"),
        ("go", "test"),
    )

    def __init__(self, runner: ProcessRunner = subprocess.run) -> None:
        self._runner = runner

    def collect(
        self,
        workspace_path: str | Path,
        required_tests: list[str],
    ) -> list[TestExecutionResult]:
        workspace = Path(workspace_path).expanduser().resolve()
        results: list[TestExecutionResult] = []
        for raw_command in required_tests:
            try:
                command = shlex.split(raw_command)
            except ValueError as exc:
                results.append(
                    TestExecutionResult(
                        command=[],
                        stdout="",
                        stderr="",
                        exit_code=None,
                        error=f"Invalid test command: {exc}",
                    )
                )
                continue

            if not self._is_allowed(command):
                results.append(
                    TestExecutionResult(
                        command=command,
                        stdout="",
                        stderr="",
                        exit_code=None,
                        error="Test command is not allowed",
                    )
                )
                continue

            try:
                completed = self._runner(
                    command,
                    cwd=workspace,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    text=True,
                    capture_output=True,
                    check=False,
                    shell=False,
                )
                results.append(
                    TestExecutionResult(
                        command=command,
                        stdout=(completed.stdout or "").strip(),
                        stderr=(completed.stderr or "").strip(),
                        exit_code=completed.returncode,
                    )
                )
            except (OSError, subprocess.SubprocessError) as exc:
                results.append(
                    TestExecutionResult(
                        command=command,
                        stdout="",
                        stderr="",
                        exit_code=None,
                        error=str(exc),
                    )
                )
        return results

    @classmethod
    def _is_allowed(cls, command: list[str]) -> bool:
        return any(
            tuple(command[: len(prefix)]) == prefix
            for prefix in cls._ALLOWED_PREFIXES
        )
