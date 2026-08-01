from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel


ProcessRunner = Callable[..., Any]


class TaskWorkspaceContext(BaseModel):
    base_workspace: str
    worktree_path: str
    delivery_branch: str
    task_branch: str
    base_commit: str


class TaskWorkspaceResult(BaseModel):
    success: bool
    context: TaskWorkspaceContext | None = None
    integrated_commit: str | None = None
    error: str | None = None


class TaskWorkspaceManager:
    """Isolate developer changes in a task-specific Git worktree."""

    def __init__(self, runner: ProcessRunner = subprocess.run) -> None:
        self._runner = runner

    def prepare(
        self,
        *,
        workspace_path: str,
        task_id: str,
        existing_context: str | None = None,
    ) -> TaskWorkspaceResult:
        base = Path(workspace_path).expanduser().resolve()
        if not base.is_dir():
            return TaskWorkspaceResult(
                success=False,
                error=f"Workspace does not exist: {base}",
            )
        if existing_context:
            try:
                context = TaskWorkspaceContext.model_validate_json(
                    existing_context
                )
            except (ValueError, TypeError):
                return TaskWorkspaceResult(
                    success=False,
                    error="Stored task workspace context is invalid",
                )
            return self._restore_worktree(context)

        branch = self._run(
            ["git", "-C", str(base), "branch", "--show-current"]
        )
        if branch.returncode != 0 or not (branch.stdout or "").strip():
            return TaskWorkspaceResult(
                success=False,
                error=self._error(branch, "Cannot determine delivery branch"),
            )
        status = self._run(
            ["git", "-C", str(base), "status", "--porcelain"]
        )
        if status.returncode != 0:
            return TaskWorkspaceResult(
                success=False,
                error=self._error(status, "Cannot inspect workspace status"),
            )
        if (status.stdout or "").strip():
            return TaskWorkspaceResult(
                success=False,
                error=(
                    "Delivery workspace has uncommitted changes; clean or "
                    "commit them before starting an isolated task"
                ),
            )
        head = self._run(["git", "-C", str(base), "rev-parse", "HEAD"])
        base_commit = (head.stdout or "").strip()
        if head.returncode != 0 or not base_commit:
            return TaskWorkspaceResult(
                success=False,
                error=self._error(head, "Cannot determine base commit"),
            )

        task_token = "".join(
            char for char in task_id.lower() if char.isalnum()
        )[:12]
        task_branch = f"auto-dev/task-{task_token}"
        worktree = (
            base.parent
            / ".auto-dev-worktrees"
            / base.name
            / task_token
        ).resolve()
        worktree.parent.mkdir(parents=True, exist_ok=True)
        context = TaskWorkspaceContext(
            base_workspace=str(base),
            worktree_path=str(worktree),
            delivery_branch=(branch.stdout or "").strip(),
            task_branch=task_branch,
            base_commit=base_commit,
        )
        if worktree.exists():
            return self._restore_worktree(context)

        created = self._run(
            [
                "git",
                "-C",
                str(base),
                "worktree",
                "add",
                "-b",
                task_branch,
                str(worktree),
                base_commit,
            ]
        )
        if created.returncode != 0:
            return TaskWorkspaceResult(
                success=False,
                error=self._error(created, "Cannot create task worktree"),
            )
        return TaskWorkspaceResult(success=True, context=context)

    def integrate(self, context: TaskWorkspaceContext) -> TaskWorkspaceResult:
        base = Path(context.base_workspace)
        task_head = self._run(
            [
                "git",
                "-C",
                context.worktree_path,
                "rev-parse",
                "HEAD",
            ]
        )
        commit_hash = (task_head.stdout or "").strip()
        if task_head.returncode != 0 or not commit_hash:
            return TaskWorkspaceResult(
                success=False,
                context=context,
                error=self._error(task_head, "Cannot determine task commit"),
            )
        branch = self._run(
            ["git", "-C", str(base), "branch", "--show-current"]
        )
        if (branch.stdout or "").strip() != context.delivery_branch:
            return TaskWorkspaceResult(
                success=False,
                context=context,
                error=(
                    "Delivery workspace branch changed while task was running"
                ),
            )
        status = self._run(
            ["git", "-C", str(base), "status", "--porcelain"]
        )
        if status.returncode != 0 or (status.stdout or "").strip():
            return TaskWorkspaceResult(
                success=False,
                context=context,
                error=(
                    "Delivery workspace is not clean; task commit was not "
                    "integrated"
                ),
            )
        merged = self._run(
            [
                "git",
                "-C",
                str(base),
                "merge",
                "--ff-only",
                context.task_branch,
            ]
        )
        if merged.returncode != 0:
            return TaskWorkspaceResult(
                success=False,
                context=context,
                error=self._error(
                    merged,
                    "Task branch cannot be fast-forwarded into delivery branch",
                ),
            )
        self._run(
            [
                "git",
                "-C",
                str(base),
                "worktree",
                "remove",
                "--force",
                context.worktree_path,
            ]
        )
        self._run(
            [
                "git",
                "-C",
                str(base),
                "branch",
                "-d",
                context.task_branch,
            ]
        )
        return TaskWorkspaceResult(
            success=True,
            context=context,
            integrated_commit=commit_hash,
        )

    def _restore_worktree(
        self, context: TaskWorkspaceContext
    ) -> TaskWorkspaceResult:
        worktree = Path(context.worktree_path)
        if worktree.is_dir():
            probe = self._run(
                ["git", "-C", str(worktree), "rev-parse", "--is-inside-work-tree"]
            )
            if probe.returncode == 0:
                return TaskWorkspaceResult(success=True, context=context)
        restored = self._run(
            [
                "git",
                "-C",
                context.base_workspace,
                "worktree",
                "add",
                context.worktree_path,
                context.task_branch,
            ]
        )
        if restored.returncode != 0:
            return TaskWorkspaceResult(
                success=False,
                context=context,
                error=self._error(restored, "Cannot restore task worktree"),
            )
        return TaskWorkspaceResult(success=True, context=context)

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
    def serialize(context: TaskWorkspaceContext) -> str:
        return json.dumps(context.model_dump(), ensure_ascii=False)

    @staticmethod
    def _error(result: Any, fallback: str) -> str:
        return (
            (result.stderr or "").strip()
            or (result.stdout or "").strip()
            or fallback
        )
