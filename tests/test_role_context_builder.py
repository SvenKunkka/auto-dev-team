import json

from backend.runtime.agent_runtime import RuntimeRequest
from backend.runtime.role_context_builder import RoleContextBuilder


def runtime_request() -> RuntimeRequest:
    developer_output = json.dumps(
        {
            "execution": {
                "output": "CODEX_VERBOSE_OUTPUT_SHOULD_NOT_BE_SENT",
                "commands": [["codex", "exec"]],
            },
            "evidence": {
                "git_commit": "abc123",
                "changed_files": ["app.py"],
                "git_diff": "+def feature(): pass",
                "test_results": [
                    {
                        "command": ["pytest", "-q"],
                        "stdout": "DUPLICATE_TEST_OUTPUT",
                        "exit_code": 0,
                    }
                ],
                "codex_output": "CODEX_RAW_EVIDENCE_SHOULD_NOT_BE_SENT",
                "commands": [["codex", "exec"]],
            },
        }
    )
    return RuntimeRequest(
        task_id="task-context",
        project_name="context",
        workspace_path="/tmp/context",
        goal="实现功能",
        requirements=["保持兼容"],
        previous_outputs={
            "requirement_analyst": json.dumps(
                {
                    "clarified_goal": "实现功能",
                    "constraints": ["保持兼容"],
                }
            ),
            "supervisor": json.dumps(
                {
                    "objective": "实现功能",
                    "acceptance_criteria": ["测试通过"],
                    "required_tests": ["pytest -q"],
                    "ready_for_development": True,
                    "internal_commentary": "不要传递的规划过程",
                }
            ),
            "developer": developer_output,
            "verification_engineer": json.dumps(
                {
                    "verification_result": "PASS",
                    "test_results": [
                        {
                            "command": ["pytest", "-q"],
                            "stdout": "1 passed",
                            "exit_code": 0,
                        }
                    ],
                    "issues": [],
                }
            ),
        },
    )


def test_verification_context_keeps_evidence_without_codex_chatter() -> None:
    deterministic_report = {
        "verification_result": "PASS",
        "required_tests": ["pytest -q"],
        "test_results": [
            {
                "command": ["pytest", "-q"],
                "stdout": "1 passed",
                "exit_code": 0,
            }
        ],
        "issues": [],
    }

    serialized = RoleContextBuilder.compact_json(
        RoleContextBuilder.verification_context(
            runtime_request(), deterministic_report
        )
    )

    assert "+def feature(): pass" in serialized
    assert '"pytest","-q"' in serialized
    assert "1 passed" in serialized
    assert "CODEX_VERBOSE_OUTPUT_SHOULD_NOT_BE_SENT" not in serialized
    assert "CODEX_RAW_EVIDENCE_SHOULD_NOT_BE_SENT" not in serialized
    assert "DUPLICATE_TEST_OUTPUT" not in serialized
    assert "internal_commentary" not in serialized


def test_review_context_keeps_independent_evidence_once() -> None:
    serialized = RoleContextBuilder.compact_json(
        RoleContextBuilder.review_context(runtime_request())
    )

    assert serialized.count("+def feature(): pass") == 1
    assert serialized.count("1 passed") == 1
    assert '"verification_result":"PASS"' in serialized
    assert '"git_commit":"abc123"' in serialized
    assert "CODEX_VERBOSE_OUTPUT_SHOULD_NOT_BE_SENT" not in serialized
    assert "CODEX_RAW_EVIDENCE_SHOULD_NOT_BE_SENT" not in serialized
    assert "DUPLICATE_TEST_OUTPUT" not in serialized
