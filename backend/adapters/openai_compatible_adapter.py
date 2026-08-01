from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, Field


class LLMExecutionResult(BaseModel):
    completed: bool
    output: str = ""
    error: str | None = None
    model: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


HttpPost = Callable[..., Any]


class OpenAICompatibleAdapter:
    """Minimal text adapter for configured DeepSeek and Moonshot models."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        provider: str,
        max_tokens: int = 3000,
        timeout_seconds: float = 180.0,
        http_post: HttpPost = httpx.post,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.provider = provider.strip().lower()
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post

    def execute(self, *, system_prompt: str, prompt: str) -> LLMExecutionResult:
        if not self.api_key:
            return self._failure(f"{self.provider} API key is not configured")
        if not self.model:
            return self._failure(f"{self.provider} model is not configured")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.provider == "kimi":
            payload["reasoning_effort"] = "high"
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
        if not 200 <= response.status_code < 300:
            return self._failure(
                f"{self.provider} API returned {response.status_code}: "
                f"{self._error_message(response)}"
            )
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return self._failure(f"Invalid {self.provider} response: {exc}")
        output = "" if content is None else str(content).strip()
        if not output:
            return self._failure("Agent returned empty output")
        return LLMExecutionResult(
            completed=True,
            output=output,
            model=str(data.get("model", self.model)),
            usage=(
                data.get("usage", {})
                if isinstance(data.get("usage"), dict)
                else {}
            ),
        )

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            data = response.json()
            error = data.get("error", {})
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])[:400]
        except (TypeError, ValueError):
            pass
        return "unknown error"

    @staticmethod
    def _failure(error: str) -> LLMExecutionResult:
        return LLMExecutionResult(completed=False, error=error)
