from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from backend.evidence.git_collector import GitCollector
from backend.evidence.test_collector import TestCollector, TestExecutionResult


class DeveloperEvidence(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    git_branch: str = ""
    git_status: str = ""
    git_diff: str = ""
    test_results: list[TestExecutionResult] = Field(default_factory=list)
    commands: list[list[str]] = Field(default_factory=list)
    codex_output: str = ""


class EvidenceCollector:
    """组合只读Git证据与受控测试结果。"""

    def __init__(
        self,
        git_collector: GitCollector | None = None,
        test_collector: TestCollector | None = None,
    ) -> None:
        self.git_collector = git_collector or GitCollector()
        self.test_collector = test_collector or TestCollector()

    def collect(
        self,
        *,
        workspace_path: str | Path,
        required_tests: list[str],
        codex_output: str,
        codex_commands: list[list[str]],
    ) -> DeveloperEvidence:
        git_evidence = self.git_collector.collect(workspace_path)
        test_results = self.test_collector.collect(
            workspace_path, required_tests
        )
        return DeveloperEvidence(
            changed_files=git_evidence.changed_files,
            git_branch=git_evidence.branch,
            git_status=git_evidence.status,
            git_diff=git_evidence.git_diff,
            test_results=test_results,
            commands=[
                *codex_commands,
                *(result.command for result in test_results if result.command),
            ],
            codex_output=codex_output,
        )
