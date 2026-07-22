"""GLM / Z.AI OpenAI-compatible chat completions provider."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from org_intel.llm.base import LLMProvider, LLMRequest, LLMResponse
from org_intel.utils.logging import get_logger

logger = get_logger(__name__)


class GLMProvider(LLMProvider):
    name = "glm"

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        timeout: float = 90.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("GLM API key is not configured (ORG_INTEL_GLM_API_KEY).")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=model,
            role=request.role,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            raw=data,
        )


class MockLLMProvider(LLMProvider):
    """Deterministic mock provider for tests and offline runs."""

    name = "mock"

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[LLMRequest] = []

    def is_available(self) -> bool:
        return True

    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        self.calls.append(request)
        key = request.metadata.get("mock_key") or request.role.value
        content = self.responses.get(key) or self.responses.get("default") or "{}"
        # Rough token estimate
        prompt_chars = sum(len(m.content) for m in request.messages)
        return LLMResponse(
            content=content,
            model=model,
            role=request.role,
            input_tokens=max(1, prompt_chars // 4),
            output_tokens=max(1, len(content) // 4),
            estimated_cost=0.0,
        )
