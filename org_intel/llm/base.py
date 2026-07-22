"""Provider-independent LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelRole(str, Enum):
    CHEAP_CLASSIFIER = "cheap_classifier"
    STRUCTURED_EXTRACTOR = "structured_extractor"
    REASONING_MODEL = "reasoning_model"
    OCR_MODEL = "ocr_model"
    JSON_REPAIR_MODEL = "json_repair_model"


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMRequest(BaseModel):
    role: ModelRole
    messages: list[LLMMessage]
    temperature: float = 0.1
    max_tokens: int = 4096
    response_format: str | None = "json"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str
    model: str
    role: ModelRole
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    cache_hit: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError
