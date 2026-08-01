from __future__ import annotations

import subprocess
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel


ProcessRunner = Callable[..., Any]


class WorkspaceValidationResult(BaseModel):
    valid: bool
    workspace_path: str
    is_git_repository: bool = False
    git_root: str | None = None
    error: str | None = None


class WorkspaceValidator:
    """Validate a workspace using only fixed, read-only Git commands."""

    def __init__(
        self,
        runner: ProcessRunner = subprocess.run,
        *,
        allowed_root: str | Path | None = None,
    ) -> None:
        self._runner = runner
        configured_root = allowed_root or os.getenv(
            "AUTO_DEV_WORKSPACES_ROOT"
        )
        self.allowed_root = (
            Path(configured_root).expanduser().resolve()
            if configured_root
            else None
        )
        self.production = (
            os.getenv("AUTO_DEV_ENV", "development").strip().lower()
            == "production"
        )

    def validate(
        self, workspace_path: str | Path
    ) -> WorkspaceValidationResult:
        workspace = Path(workspace_path).expanduser().resolve()
        if not workspace.exists():
            return self._invalid(
                workspace, f"Workspace does not exist: {workspace}"
            )
        if not workspace.is_dir():
            return self._invalid(
                workspace, f"Workspace is not a directory: {workspace}"
            )
        if self.production and self.allowed_root is None:
            return self._invalid(
                workspace, "Production workspace root is not configured"
            )
        if self.allowed_root is not None and not workspace.is_relative_to(
            self.allowed_root
        ):
            return self._invalid(
                workspace,
                (
                    f"Workspace is outside allowed root: "
                    f"{self.allowed_root}"
                ),
            )

        try:
            inside = self._runner(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "rev-parse",
                    "--is-inside-work-tree",
                ],
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return self._invalid(
                workspace, f"Git validation failed: {exc}"
            )
        if (
            inside.returncode != 0
            or (inside.stdout or "").strip().lower() != "true"
        ):
            return self._invalid(
                workspace, f"Workspace is not a Git repository: {workspace}"
            )

        git_root = self._git_root(workspace)
        return WorkspaceValidationResult(
            valid=True,
            workspace_path=str(workspace),
            is_git_repository=True,
            git_root=git_root,
        )

    def _git_root(self, workspace: Path) -> str:
        try:
            result = self._runner(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "rev-parse",
                    "--show-toplevel",
                ],
                text=True,
                capture_output=True,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return str(workspace)
        root = (result.stdout or "").strip()
        return root if result.returncode == 0 and root else str(workspace)

    @staticmethod
    def _invalid(
        workspace: Path, error: str
    ) -> WorkspaceValidationResult:
        return WorkspaceValidationResult(
            valid=False,
            workspace_path=str(workspace),
            error=error,
        )
