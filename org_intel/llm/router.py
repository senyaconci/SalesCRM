"""LLM router with role-based model selection, caching, and cost tracking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select

from org_intel.config import Settings
from org_intel.database import Database, LLMCacheRow
from org_intel.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMResponse, ModelRole
from org_intel.llm.glm_provider import GLMProvider, MockLLMProvider
from org_intel.llm.json_repair import loads_json
from org_intel.schemas.evidence import CostLedgerEntry
from org_intel.utils.ids import new_id
from org_intel.utils.logging import get_logger

logger = get_logger(__name__)


class CostLimitExceeded(RuntimeError):
    def __init__(self, message: str, spent: float, limit: float) -> None:
        super().__init__(message)
        self.spent = spent
        self.limit = limit


class CostTracker:
    def __init__(self, db: Database, run_id: str, max_cost_usd: float) -> None:
        self.db = db
        self.run_id = run_id
        self.max_cost_usd = max_cost_usd

    @property
    def spent(self) -> float:
        return self.db.total_cost(self.run_id)

    def remaining(self) -> float:
        return max(0.0, self.max_cost_usd - self.spent)

    def can_afford(self, estimated: float) -> bool:
        return self.spent + estimated <= self.max_cost_usd

    def record(self, entry: CostLedgerEntry) -> None:
        if not self.can_afford(entry.actual_cost or entry.estimated_cost):
            # Still record for audit, then raise
            self.db.add_cost(self.run_id, entry.model_dump(mode="json", exclude={"created_at"}))
            raise CostLimitExceeded(
                f"Cost limit reached: spent={self.spent:.4f} limit={self.max_cost_usd:.4f}",
                spent=self.spent,
                limit=self.max_cost_usd,
            )
        payload = entry.model_dump(mode="json")
        payload.pop("created_at", None)
        self.db.add_cost(self.run_id, payload)


class LLMRouter:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        cost_tracker: CostTracker,
        provider: LLMProvider | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self.settings = settings
        self.db = db
        self.cost_tracker = cost_tracker
        self.cache_enabled = cache_enabled
        if provider is not None:
            self.provider = provider
        elif settings.llm_provider == "mock" or not settings.glm_api_key:
            logger.warning("llm_using_mock_provider", reason="no_api_key_or_mock")
            self.provider = MockLLMProvider()
        else:
            self.provider = GLMProvider(
                api_key=settings.glm_api_key,
                base_url=settings.glm_base_url,
                timeout=settings.request_timeout_seconds,
            )
        self.role_models = {
            ModelRole.CHEAP_CLASSIFIER: settings.glm_cheap_model,
            ModelRole.STRUCTURED_EXTRACTOR: settings.glm_structured_model,
            ModelRole.REASONING_MODEL: settings.glm_reasoning_model,
            ModelRole.OCR_MODEL: settings.glm_ocr_model,
            ModelRole.JSON_REPAIR_MODEL: settings.glm_json_repair_model,
        }

    def model_for(self, role: ModelRole) -> str:
        return self.role_models[role]

    def estimate_cost(self, role: ModelRole, input_tokens: int, output_tokens: int) -> float:
        if role in {ModelRole.CHEAP_CLASSIFIER, ModelRole.JSON_REPAIR_MODEL}:
            inp, out = self.settings.cheap_input_cost_per_m, self.settings.cheap_output_cost_per_m
        elif role == ModelRole.STRUCTURED_EXTRACTOR:
            inp = self.settings.structured_input_cost_per_m
            out = self.settings.structured_output_cost_per_m
        else:
            inp = self.settings.reasoning_input_cost_per_m
            out = self.settings.reasoning_output_cost_per_m
        return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * out

    def complete(
        self,
        role: ModelRole,
        system: str,
        user: str,
        *,
        task_type: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        organization_id: str | None = None,
        document_id: str | None = None,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        require_json: bool = True,
    ) -> LLMResponse:
        request = LLMRequest(
            role=role,
            messages=[
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=user),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format="json" if require_json else None,
            metadata=metadata or {},
        )
        model = self.model_for(role)
        cache_key = self._cache_key(model, request)
        if self.cache_enabled:
            cached = self._get_cache(cache_key)
            if cached is not None:
                entry = CostLedgerEntry(
                    task_id=new_id("TASK"),
                    task_type=task_type,
                    model=model,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost=0.0,
                    actual_cost=0.0,
                    cache_hit=True,
                    organization_id=organization_id,
                    document_id=document_id,
                    project_id=project_id,
                )
                self.cost_tracker.record(entry)
                return LLMResponse(
                    content=cached,
                    model=model,
                    role=role,
                    cache_hit=True,
                )

        # Preflight rough estimate (assume 1k out)
        est_in = max(1, (len(system) + len(user)) // 4)
        est = self.estimate_cost(role, est_in, 1000)
        if not self.cost_tracker.can_afford(est):
            raise CostLimitExceeded(
                f"Cannot afford estimated LLM call ({est:.4f}); remaining "
                f"{self.cost_tracker.remaining():.4f}",
                spent=self.cost_tracker.spent,
                limit=self.cost_tracker.max_cost_usd,
            )

        response = self.provider.complete(request, model)
        cost = self.estimate_cost(role, response.input_tokens, response.output_tokens)
        response.estimated_cost = cost
        entry = CostLedgerEntry(
            task_id=new_id("TASK"),
            task_type=task_type,
            model=model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=cost,
            actual_cost=cost,
            cache_hit=False,
            organization_id=organization_id,
            document_id=document_id,
            project_id=project_id,
        )
        self.cost_tracker.record(entry)
        if self.cache_enabled:
            self._set_cache(cache_key, role.value, model, response.content)
        return response

    def complete_json(
        self,
        role: ModelRole,
        system: str,
        user: str,
        **kwargs: Any,
    ) -> Any:
        response = self.complete(role, system, user, require_json=True, **kwargs)
        data = loads_json(response.content, default=None)
        if data is None and role != ModelRole.JSON_REPAIR_MODEL:
            repair = self.complete(
                ModelRole.JSON_REPAIR_MODEL,
                "Repair the following into valid JSON. Return JSON only.",
                response.content,
                task_type="json_repair",
                organization_id=kwargs.get("organization_id"),
            )
            data = loads_json(repair.content, default={})
        return data if data is not None else {}

    def _cache_key(self, model: str, request: LLMRequest) -> str:
        payload = {
            "model": model,
            "role": request.role.value,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest

    def _get_cache(self, cache_key: str) -> str | None:
        with self.db.session() as session:
            row = session.scalar(
                select(LLMCacheRow).where(LLMCacheRow.cache_key == cache_key)
            )
            return row.response_json if row else None

    def _set_cache(self, cache_key: str, role: str, model: str, content: str) -> None:
        with self.db.session() as session:
            existing = session.scalar(
                select(LLMCacheRow).where(LLMCacheRow.cache_key == cache_key)
            )
            if existing:
                existing.response_json = content
            else:
                session.add(
                    LLMCacheRow(
                        cache_key=cache_key,
                        role=role,
                        model=model,
                        response_json=content,
                    )
                )
            session.commit()


def build_router(
    settings: Settings,
    db: Database,
    run_id: str,
    provider: LLMProvider | None = None,
) -> LLMRouter:
    tracker = CostTracker(db, run_id, settings.max_cost_usd)
    return LLMRouter(settings, db, tracker, provider=provider)
