from types import SimpleNamespace

from backend.evidence.evidence_collector import EvidenceCollector
from backend.evidence.git_collector import GitCollector
from backend.evidence.test_collector import TestCollector as EvidenceTestCollector


def git_runner(command, **kwargs):
    if "branch" in command:
        return SimpleNamespace(returncode=0, stdout="feature/evidence\n", stderr="")
    if "status" in command:
        return SimpleNamespace(
            returncode=0,
            stdout=" M src/app.py\n?? tests/test_app.py\n",
            stderr="",
        )
    if "--cached" in command:
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return SimpleNamespace(
        returncode=0,
        stdout="diff --git a/src/app.py b/src/app.py\n+changed\n",
        stderr="",
    )


def test_evidence_collector_combines_git_tests_and_codex_output(
    tmp_path,
) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    test_runner = lambda *args, **kwargs: SimpleNamespace(
        returncode=0,
        stdout="3 passed",
        stderr="",
    )
    collector = EvidenceCollector(
        git_collector=GitCollector(git_runner),
        test_collector=EvidenceTestCollector(test_runner),
    )

    evidence = collector.collect(
        workspace_path=workspace,
        required_tests=["pytest -q"],
        codex_output="实现完成",
        codex_commands=[["codex", "exec"]],
    )

    assert evidence.git_branch == "feature/evidence"
    assert evidence.changed_files == ["src/app.py", "tests/test_app.py"]
    assert evidence.git_diff.startswith("diff --git")
    assert evidence.test_results[0].exit_code == 0
    assert evidence.test_results[0].stdout == "3 passed"
    assert evidence.commands == [["codex", "exec"], ["pytest", "-q"]]
    assert evidence.codex_output == "实现完成"


def test_failed_test_is_recorded(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    collector = EvidenceCollector(
        git_collector=GitCollector(git_runner),
        test_collector=EvidenceTestCollector(
            lambda *args, **kwargs: SimpleNamespace(
                returncode=1,
                stdout="1 failed",
                stderr="assertion failed",
            )
        ),
    )

    evidence = collector.collect(
        workspace_path=workspace,
        required_tests=["uv run pytest -q"],
        codex_output="实现完成",
        codex_commands=[],
    )

    assert evidence.test_results[0].exit_code == 1
    assert evidence.test_results[0].stdout == "1 failed"
    assert evidence.test_results[0].stderr == "assertion failed"


def test_empty_git_diff_is_valid(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    def empty_git_runner(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    evidence = EvidenceCollector(
        git_collector=GitCollector(empty_git_runner),
        test_collector=EvidenceTestCollector(),
    ).collect(
        workspace_path=workspace,
        required_tests=[],
        codex_output="无文件变更",
        codex_commands=[],
    )

    assert evidence.git_diff == ""
    assert evidence.changed_files == []
    assert evidence.test_results == []


def test_disallowed_test_command_is_not_executed(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    called = False

    def test_runner(*args, **kwargs):
        nonlocal called
        called = True

    results = EvidenceTestCollector(test_runner).collect(
        workspace, ["rm -rf build"]
    )

    assert called is False
    assert results[0].exit_code is None
    assert results[0].error == "Test command is not allowed"


def test_python_unittest_command_is_allowed(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    calls = []

    def test_runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    results = EvidenceTestCollector(test_runner).collect(
        workspace, ["python -m unittest -v"]
    )

    assert results[0].exit_code == 0
    assert results[0].error is None
    assert calls[0][0] == ["python", "-m", "unittest", "-v"]
    assert calls[0][1]["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_npm_build_and_lint_commands_are_allowed(tmp_path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    calls = []

    def test_runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    results = EvidenceTestCollector(test_runner).collect(
        workspace,
        [
            "npm run build",
            "npm run lint",
            "npm run test:postgres-schema",
            "npm run test:postgres",
        ],
    )

    assert [result.error for result in results] == [None, None, None, None]
    assert calls == [
        ["npm", "run", "build"],
        ["npm", "run", "lint"],
        ["npm", "run", "test:postgres-schema"],
        ["npm", "run", "test:postgres"],
    ]
