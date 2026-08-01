from __future__ import annotations

import json
from typing import Any

from backend.runtime.agent_runtime import RuntimeRequest


class RoleContextBuilder:
    """Build minimal sufficient, evidence-preserving views per role."""

    @classmethod
    def verification_context(
        cls,
        request: RuntimeRequest,
        deterministic_report: dict[str, Any],
    ) -> dict[str, Any]:
        evidence = cls._developer_evidence(request)
        return {
            "task": cls._task_context(request),
            "requirement_spec": cls._structured_output(
                request.previous_outputs.get("requirement_analyst", "")
            ),
            "supervisor_plan": cls._supervisor_plan(request),
            "delivery_evidence": {
                "git_diff": evidence.get("git_diff", ""),
            },
            "deterministic_report": deterministic_report,
        }

    @classmethod
    def review_context(cls, request: RuntimeRequest) -> dict[str, Any]:
        evidence = cls._developer_evidence(request)
        verification_report = cls._structured_output(
            request.previous_outputs.get("verification_engineer", "")
        )
        return {
            "task": cls._task_context(request),
            "requirement_spec": cls._structured_output(
                request.previous_outputs.get("requirement_analyst", "")
            ),
            "supervisor_plan": cls._supervisor_plan(request),
            "delivery_evidence": {
                "git_commit": evidence.get("git_commit"),
                "changed_files": evidence.get("changed_files", []),
                "git_diff": evidence.get("git_diff", ""),
            },
            "verification_report": verification_report,
        }

    @staticmethod
    def compact_json(value: dict[str, Any]) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def _task_context(cls, request: RuntimeRequest) -> dict[str, Any]:
        return {
            "task_id": request.task_id,
            "project_name": request.project_name,
            "goal": request.goal,
            "original_requirements": request.requirements,
        }

    @classmethod
    def _supervisor_plan(
        cls, request: RuntimeRequest
    ) -> dict[str, Any] | str:
        value = cls._structured_output(
            request.previous_outputs.get("supervisor", "")
        )
        if not isinstance(value, dict):
            return value
        allowed = (
            "objective",
            "confirmed_requirements",
            "deliverables",
            "acceptance_criteria",
            "forbidden_scope",
            "blockers",
            "ready_for_development",
        )
        return {key: value[key] for key in allowed if key in value}

    @classmethod
    def _developer_evidence(
        cls, request: RuntimeRequest
    ) -> dict[str, Any]:
        developer = cls._structured_output(
            request.previous_outputs.get("developer", "")
        )
        if not isinstance(developer, dict):
            return {}
        evidence = developer.get("evidence", {})
        return evidence if isinstance(evidence, dict) else {}

    @staticmethod
    def _structured_output(value: str) -> dict[str, Any] | str:
        if not value:
            return ""
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
        return parsed if isinstance(parsed, dict) else value
