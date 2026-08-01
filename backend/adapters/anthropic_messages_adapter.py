from __future__ import annotations

from typing import Any

import httpx

from backend.adapters.openai_compatible_adapter import LLMExecutionResult


class AnthropicMessagesAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        max_tokens: int = 3000,
        timeout_seconds: float = 180.0,
        http_post=httpx.post,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post

    def execute(self, *, system_prompt: str, prompt: str) -> LLMExecutionResult:
        if not self.api_key:
            return LLMExecutionResult(
                completed=False,
                error="anthropic API key is not configured",
            )
        try:
            response = self._http_post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self.max_tokens,
                },
                timeout=self.timeout_seconds,
            )
        except (httpx.HTTPError, OSError) as exc:
            return LLMExecutionResult(completed=False, error=str(exc))
        if not 200 <= response.status_code < 300:
            return LLMExecutionResult(
                completed=False,
                error=f"anthropic API returned {response.status_code}",
            )
        try:
            data: dict[str, Any] = response.json()
            output = "\n".join(
                str(block.get("text", ""))
                for block in data.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
        except (TypeError, ValueError) as exc:
            return LLMExecutionResult(
                completed=False,
                error=f"Invalid anthropic response: {exc}",
            )
        if not output:
            return LLMExecutionResult(
                completed=False, error="Agent returned empty output"
            )
        return LLMExecutionResult(
            completed=True,
            output=output,
            model=str(data.get("model", self.model)),
            usage=data.get("usage", {}),
        )
