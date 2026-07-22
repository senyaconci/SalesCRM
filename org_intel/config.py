"""Application configuration loaded from environment and CLI overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RunMode = Literal["discover", "project-map", "full", "refresh", "deep-enrich"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Runtime settings. Never hardcode API keys."""

    model_config = SettingsConfigDict(
        env_prefix="ORG_INTEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "glm"
    glm_api_key: str | None = None
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_cheap_model: str = "glm-4-flash"
    glm_structured_model: str = "glm-4-air"
    glm_reasoning_model: str = "glm-4-plus"
    glm_ocr_model: str = "glm-4v"
    glm_json_repair_model: str = "glm-4-flash"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    max_cost_usd: float = 25.0
    max_documents: int = 200
    max_pages: int = 5000
    max_searches: int = 100
    max_workers: int = 4
    official_sources_only: bool = True
    include_third_party_sources: bool = False

    user_agent: str = "OrganizationCapitalIntelligence/1.0 (+research; respectful crawler)"
    request_timeout_seconds: float = 45.0
    cache_dir: Path = Path(".org_intel_cache")
    database_url: str = "sqlite:///./org_intel.db"
    log_level: LogLevel = "INFO"
    respect_robots: bool = True

    # Per-role estimated USD per 1M tokens (defaults; overridable via env if needed)
    cheap_input_cost_per_m: float = 0.10
    cheap_output_cost_per_m: float = 0.10
    structured_input_cost_per_m: float = 0.50
    structured_output_cost_per_m: float = 1.50
    reasoning_input_cost_per_m: float = 3.00
    reasoning_output_cost_per_m: float = 10.00


class RunConfig(BaseSettings):
    """Per-run CLI configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    org_url: str | None = None
    org_name: str | None = None
    org_type: str | None = None
    output_dir: Path = Path("./outputs/run")
    mode: RunMode = "full"
    resume: bool = False
    force: bool = False
    max_cost_usd: float | None = None
    max_documents: int | None = None
    max_pages: int | None = None
    max_searches: int | None = None
    max_workers: int | None = None
    official_sources_only: bool | None = None
    include_third_party_sources: bool | None = None
    project_id: list[str] = Field(default_factory=list)
    project_category: list[str] = Field(default_factory=list)
    min_project_value: float | None = None
    include_completed: bool = False
    log_level: LogLevel | None = None
    keep_intermediate: bool = False

    @field_validator("output_dir", mode="before")
    @classmethod
    def _as_path(cls, value: object) -> Path:
        return Path(value) if not isinstance(value, Path) else value


def merge_settings(settings: Settings, run: RunConfig) -> Settings:
    """Apply CLI overrides onto base settings."""
    data = settings.model_dump()
    overrides = {
        "max_cost_usd": run.max_cost_usd,
        "max_documents": run.max_documents,
        "max_pages": run.max_pages,
        "max_searches": run.max_searches,
        "max_workers": run.max_workers,
        "official_sources_only": run.official_sources_only,
        "include_third_party_sources": run.include_third_party_sources,
        "log_level": run.log_level,
    }
    for key, value in overrides.items():
        if value is not None:
            data[key] = value
    return Settings(**data)
