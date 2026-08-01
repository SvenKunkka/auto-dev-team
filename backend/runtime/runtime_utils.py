from __future__ import annotations

import json
import re


def extract_required_tests(supervisor_output: str) -> list[str]:
    candidates = [supervisor_output]
    candidates.extend(
        match.group(1)
        for match in re.finditer(
            r"```(?:json)?\s*(.*?)```",
            supervisor_output,
            flags=re.DOTALL | re.IGNORECASE,
        )
    )
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and isinstance(
            parsed.get("required_tests"), list
        ):
            return [
                str(command)
                for command in parsed["required_tests"]
                if str(command).strip()
            ]

    return [
        match.group(1).strip()
        for match in re.finditer(
            r"(?im)^\s*REQUIRED_TEST\s*:\s*(.+?)\s*$",
            supervisor_output,
        )
        if match.group(1).strip()
    ]
