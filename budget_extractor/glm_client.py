"""Z.AI GLM chat-completion client for factual JSON extraction."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from budget_extractor.config import AppConfig
from budget_extractor.costing import BudgetExceededError, CostTracker

LOGGER = logging.getLogger(__name__)


@dataclass
class GlmCompletionResult:
    content: str
    request_id: str
    finish_reason: str | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False


def _is_retryable(exc: BaseException) -> bool:
    # Do not retry auth / invalid-request style errors forever.
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if any(token in message for token in ("api key", "unauthorized", "authentication", "forbidden")):
        return False
    if "invalid" in message and "request" in message:
        return False
    if "401" in message or "403" in message:
        return False
    if "timeout" in name or "timeout" in message:
        return True
    if "rate" in message or "429" in message:
        return True
    if "503" in message or "502" in message or "500" in message:
        return True
    if "connection" in message or "temporarily" in message:
        return True
    return False


class GlmClient:
    """Thin wrapper around official `zai-sdk` chat completions."""

    def __init__(self, config: AppConfig, cost_tracker: CostTracker | None = None):
        self.config = config
        self.cost_tracker = cost_tracker or CostTracker(max_cost_usd=config.max_cost_usd)
        self._client: Any | None = None
        self.api_requests = 0
        self.api_retries = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def _get_client(self) -> Any:
        if self._client is None:
            from zai import ZaiClient

            self._client = ZaiClient(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.request_timeout_seconds,
                max_retries=0,
            )
        return self._client

    def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        request_id: str | None = None,
        max_tokens: int | None = None,
    ) -> GlmCompletionResult:
        request_id = request_id or f"budget-ext-{uuid.uuid4().hex}"

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.config.max_api_retries),
            wait=wait_exponential_jitter(initial=2, max=90),
            retry=retry_if_exception(_is_retryable),
            before_sleep=lambda rs: setattr(self, "api_retries", self.api_retries + 1),
        )
        def _invoke() -> GlmCompletionResult:
            # Conservative pre-flight reserve so a single call cannot blow the cap.
            if self.cost_tracker.max_cost_usd is not None:
                remaining = self.cost_tracker.remaining_usd() or 0.0
                # Assume up to ~12k prompt + configured max output as worst case.
                worst = self.cost_tracker.estimate_chat_cost(
                    model=self.config.model,
                    prompt_tokens=12_000,
                    completion_tokens=min(self.config.max_output_tokens, 8_000),
                )
                if remaining < min(worst, 0.15):
                    raise BudgetExceededError(
                        f"Insufficient remaining budget for another GLM call "
                        f"(remaining=${remaining:.4f}, cap=${self.cost_tracker.max_cost_usd:.2f})"
                    )
            self.api_requests += 1
            client = self._get_client()
            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "max_tokens": max_tokens or self.config.max_output_tokens,
                "response_format": {"type": "json_object"},
                "thinking": {
                    "type": "enabled" if self.config.thinking_enabled else "disabled"
                },
                "request_id": request_id,
            }
            if self.config.thinking_enabled:
                kwargs["reasoning_effort"] = self.config.reasoning_effort
            try:
                response = client.chat.completions.create(**kwargs)
            except TypeError:
                # Older SDK builds may not accept every keyword.
                kwargs.pop("reasoning_effort", None)
                try:
                    response = client.chat.completions.create(**kwargs)
                except TypeError:
                    kwargs.pop("thinking", None)
                    response = client.chat.completions.create(**kwargs)

            return self._normalize_response(response, request_id=request_id)

        return _invoke()

    def _normalize_response(self, response: Any, *, request_id: str) -> GlmCompletionResult:
        raw = _to_dict(response)
        choices = raw.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        content = message.get("content")
        if content is None:
            content = ""
        if isinstance(content, list):
            # Some SDKs return multimodal-style content lists.
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )

        finish_reason = choice.get("finish_reason")
        usage = raw.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens

        cached_prompt_tokens = 0
        details = usage.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            cached_prompt_tokens = int(details.get("cached_tokens") or 0)
        cost = self.cost_tracker.add_chat_usage(
            model=self.config.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
        )
        LOGGER.info(
            "GLM usage prompt=%s completion=%s cost=$%.4f cumulative=$%.4f",
            prompt_tokens,
            completion_tokens,
            cost,
            self.cost_tracker.estimated_cost_usd,
        )

        truncated = finish_reason in {"length", "max_tokens"}
        actual_request_id = raw.get("request_id") or raw.get("id") or request_id

        return GlmCompletionResult(
            content=str(content).strip(),
            request_id=str(actual_request_id),
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=raw,
            truncated=truncated,
        )


def _to_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    # Fallback attribute access used by some SDK versions.
    data: dict[str, Any] = {}
    for attr in ("id", "request_id", "model", "usage", "choices", "created"):
        if hasattr(response, attr):
            value = getattr(response, attr)
            data[attr] = value
    if "choices" in data and data["choices"] and not isinstance(data["choices"][0], dict):
        normalized_choices = []
        for choice in data["choices"]:
            message = getattr(choice, "message", None)
            normalized_choices.append(
                {
                    "finish_reason": getattr(choice, "finish_reason", None),
                    "message": {
                        "role": getattr(message, "role", None),
                        "content": getattr(message, "content", None),
                        "reasoning_content": getattr(message, "reasoning_content", None),
                    },
                }
            )
        data["choices"] = normalized_choices
    if "usage" in data and data["usage"] is not None and not isinstance(data["usage"], dict):
        usage = data["usage"]
        data["usage"] = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }
    return data
