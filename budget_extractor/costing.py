"""API cost estimation helpers for spend caps."""

from __future__ import annotations

from dataclasses import dataclass


# Official Z.AI list prices (USD per 1M tokens), GLM-5.2 / glm-ocr.
PRICE_INPUT_PER_MTOK = {
    "glm-5.2": 1.40,
    "glm-ocr": 0.03,
}
PRICE_OUTPUT_PER_MTOK = {
    "glm-5.2": 4.40,
    "glm-ocr": 0.03,
}
PRICE_CACHED_INPUT_PER_MTOK = {
    "glm-5.2": 0.26,
    "glm-ocr": 0.03,
}


class BudgetExceededError(RuntimeError):
    """Raised when the configured spend cap would be exceeded."""


@dataclass
class CostTracker:
    """Tracks estimated USD spend from token usage."""

    max_cost_usd: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    ocr_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def estimate_chat_cost(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int = 0,
    ) -> float:
        model_key = (model or "glm-5.2").lower()
        input_rate = PRICE_INPUT_PER_MTOK.get(model_key, PRICE_INPUT_PER_MTOK["glm-5.2"])
        cached_rate = PRICE_CACHED_INPUT_PER_MTOK.get(
            model_key, PRICE_CACHED_INPUT_PER_MTOK["glm-5.2"]
        )
        output_rate = PRICE_OUTPUT_PER_MTOK.get(model_key, PRICE_OUTPUT_PER_MTOK["glm-5.2"])
        billable_prompt = max(0, prompt_tokens - cached_prompt_tokens)
        return (
            (billable_prompt / 1_000_000.0) * input_rate
            + (cached_prompt_tokens / 1_000_000.0) * cached_rate
            + (completion_tokens / 1_000_000.0) * output_rate
        )

    def estimate_ocr_cost(self, total_tokens: int) -> float:
        rate = PRICE_INPUT_PER_MTOK["glm-ocr"]
        # OCR is priced symmetrically at $0.03 / MTok in the public table.
        return (total_tokens / 1_000_000.0) * rate

    def ensure_can_spend(self, additional_usd: float, *, reserve_usd: float = 0.0) -> None:
        if self.max_cost_usd is None:
            return
        projected = self.estimated_cost_usd + additional_usd
        if projected + reserve_usd > self.max_cost_usd:
            raise BudgetExceededError(
                f"Spend cap reached: current=${self.estimated_cost_usd:.4f}, "
                f"additional=${additional_usd:.4f}, reserve=${reserve_usd:.4f}, "
                f"cap=${self.max_cost_usd:.2f}"
            )

    def add_chat_usage(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int = 0,
    ) -> float:
        cost = self.estimate_chat_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
        )
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.cached_prompt_tokens += cached_prompt_tokens
        self.estimated_cost_usd += cost
        return cost

    def add_ocr_usage(self, total_tokens: int) -> float:
        cost = self.estimate_ocr_cost(total_tokens)
        self.ocr_tokens += total_tokens
        self.estimated_cost_usd += cost
        return cost

    def remaining_usd(self) -> float | None:
        if self.max_cost_usd is None:
            return None
        return max(0.0, self.max_cost_usd - self.estimated_cost_usd)
