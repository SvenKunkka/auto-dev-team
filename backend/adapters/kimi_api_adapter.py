from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field


class KimiVerificationStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class KimiVerificationRequest(BaseModel):
    prompt: str


class KimiVerificationResult(BaseModel):
    status: KimiVerificationStatus
    output: str
    error: str | None = None
    model: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


HttpPost = Callable[..., Any]


class KimiAPIAdapter:
    """Call Kimi through its OpenAI-compatible, text-only API."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "high",
        max_tokens: int = 4096,
        timeout_seconds: float = 180.0,
        http_post: HttpPost = httpx.post,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.reasoning_effort = reasoning_effort.strip().lower()
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post

    def verify(
        self, request: KimiVerificationRequest
    ) -> KimiVerificationResult:
        if not self.api_key:
            return self._failure("KIMI_API_KEY is not configured")
        if not self.base_url:
            return self._failure("KIMI_BASE_URL is not configured")
        if not self.model:
            return self._failure("KIMI_MODEL is not configured")
        if self.reasoning_effort not in {"low", "high", "max"}:
            return self._failure(
                "KIMI_REASONING_EFFORT must be low, high, or max"
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是独立软件验证工程师。只根据传入证据判断，"
                        "不得声称执行了未提供结果的命令。只输出JSON。"
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        try:
            response = self._http_post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
        except (httpx.HTTPError, OSError) as exc:
            return self._failure(str(exc))

        if response.status_code < 200 or response.status_code >= 300:
            return self._failure(
                self._response_error(response),
            )
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return self._failure(f"Invalid Kimi response: {exc}")
        output = "" if content is None else str(content).strip()
        if not output:
            return self._failure("Agent returned empty output")
        return KimiVerificationResult(
            status=KimiVerificationStatus.COMPLETED,
            output=output,
            model=str(data.get("model", self.model)),
            usage=(
                data.get("usage", {})
                if isinstance(data.get("usage"), dict)
                else {}
            ),
        )

    @staticmethod
    def _response_error(response: Any) -> str:
        try:
            data = response.json()
            error = data.get("error", {})
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return (
                        f"Kimi API returned {response.status_code}: "
                        f"{str(message)[:400]}"
                    )
        except (TypeError, ValueError):
            pass
        return f"Kimi API returned {response.status_code}"

    @staticmethod
    def _failure(error: str) -> KimiVerificationResult:
        return KimiVerificationResult(
            status=KimiVerificationStatus.FAILED,
            output="",
            error=error,
        )
