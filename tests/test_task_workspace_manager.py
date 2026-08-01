import subprocess

from backend.reliability.task_workspace_manager import TaskWorkspaceManager


def run(*command: str) -> str:
    result = subprocess.run(
        list(command),
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def repository(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    run("git", "init", str(workspace))
    run("git", "-C", str(workspace), "config", "user.name", "Auto Dev Test")
    run(
        "git",
        "-C",
        str(workspace),
        "config",
        "user.email",
        "autodev@example.com",
    )
    (workspace / "base.txt").write_text("base\n")
    run("git", "-C", str(workspace), "add", "base.txt")
    run("git", "-C", str(workspace), "commit", "-m", "baseline")
    return workspace


def commit_task_change(context) -> str:
    worktree = context.worktree_path
    with open(f"{worktree}/feature.txt", "w", encoding="utf-8") as handle:
        handle.write("accepted\n")
    run("git", "-C", worktree, "add", "feature.txt")
    run("git", "-C", worktree, "commit", "-m", "task change")
    return run("git", "-C", worktree, "rev-parse", "HEAD")


def test_unaccepted_task_changes_do_not_modify_delivery_workspace(
    tmp_path,
) -> None:
    workspace = repository(tmp_path)
    baseline = run("git", "-C", str(workspace), "rev-parse", "HEAD")
    manager = TaskWorkspaceManager()
    prepared = manager.prepare(
        workspace_path=str(workspace), task_id="blocked-task"
    )
    assert prepared.success and prepared.context is not None

    commit_task_change(prepared.context)

    assert run("git", "-C", str(workspace), "rev-parse", "HEAD") == baseline
    assert not (workspace / "feature.txt").exists()
    assert run(
        "git",
        "-C",
        str(workspace),
        "status",
        "--porcelain",
    ) == ""


def test_only_accepted_task_commit_is_integrated(tmp_path) -> None:
    workspace = repository(tmp_path)
    manager = TaskWorkspaceManager()
    prepared = manager.prepare(
        workspace_path=str(workspace), task_id="accepted-task"
    )
    assert prepared.success and prepared.context is not None
    task_commit = commit_task_change(prepared.context)

    integrated = manager.integrate(prepared.context)

    assert integrated.success
    assert integrated.integrated_commit == task_commit
    assert run("git", "-C", str(workspace), "rev-parse", "HEAD") == task_commit
    assert (workspace / "feature.txt").read_text() == "accepted\n"
