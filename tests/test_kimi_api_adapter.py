from backend.adapters.kimi_api_adapter import (
    KimiAPIAdapter,
    KimiVerificationRequest,
    KimiVerificationStatus,
)


class FakeResponse:
    def __init__(self, status_code: int, data: dict) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> dict:
        return self._data


def test_kimi_adapter_passes_verification_context() -> None:
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            200,
            {
                "model": "kimi-k3",
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"verification_result":"PASS",'
                                '"blocking_issues":[],"warnings":[],'
                                '"assessment":"通过"}'
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 120},
            },
        )

    result = KimiAPIAdapter(
        api_key="secret-key",
        base_url="https://api.moonshot.cn/v1/",
        model="kimi-k3",
        reasoning_effort="high",
        http_post=post,
    ).verify(KimiVerificationRequest(prompt="验证开发证据"))

    assert result.status is KimiVerificationStatus.COMPLETED
    assert result.model == "kimi-k3"
    assert result.usage["total_tokens"] == 120
    url, kwargs = calls[0]
    assert url == "https://api.moonshot.cn/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert kwargs["json"]["model"] == "kimi-k3"
    assert kwargs["json"]["reasoning_effort"] == "high"
    assert "验证开发证据" in kwargs["json"]["messages"][1]["content"]


def test_kimi_adapter_handles_api_error_without_exposing_key() -> None:
    result = KimiAPIAdapter(
        api_key="do-not-expose",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k3",
        http_post=lambda *args, **kwargs: FakeResponse(
            401, {"error": {"message": "Invalid Authentication"}}
        ),
    ).verify(KimiVerificationRequest(prompt="verify"))

    assert result.status is KimiVerificationStatus.FAILED
    assert result.error == (
        "Kimi API returned 401: Invalid Authentication"
    )
    assert "do-not-expose" not in result.error


def test_kimi_adapter_rejects_invalid_reasoning_effort() -> None:
    result = KimiAPIAdapter(
        api_key="secret",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k3",
        reasoning_effort="medium",
    ).verify(KimiVerificationRequest(prompt="verify"))

    assert result.status is KimiVerificationStatus.FAILED
    assert result.error == (
        "KIMI_REASONING_EFFORT must be low, high, or max"
    )
