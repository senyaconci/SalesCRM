"""Application configuration loaded from environment and CLI overrides."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

OcrMode = Literal["auto", "always", "never"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_MODEL = "glm-5.2"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MAX_OUTPUT_TOKENS = 32768
DEFAULT_CHUNK_PAGES = 20
DEFAULT_OVERLAP_PAGES = 2
DEFAULT_OCR_CHUNK_PAGES = 20
DEFAULT_MAX_RETRIES = 5
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_MAX_WORKERS = 1


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


@dataclass
class AppConfig:
    """Runtime configuration for a single extraction run."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    chunk_pages: int = DEFAULT_CHUNK_PAGES
    overlap_pages: int = DEFAULT_OVERLAP_PAGES
    ocr_chunk_pages: int = DEFAULT_OCR_CHUNK_PAGES
    max_api_retries: int = DEFAULT_MAX_RETRIES
    request_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_workers: int = DEFAULT_MAX_WORKERS
    ocr_mode: OcrMode = "auto"
    resume: bool = False
    force: bool = False
    start_page: int | None = None
    end_page: int | None = None
    log_level: LogLevel = "INFO"
    keep_intermediate: bool = False
    temperature: float = 0.1
    top_p: float = 0.2
    prompts_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "prompts")

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError(
                "Missing ZAI_API_KEY. Set it in the environment or a local .env file."
            )
        if self.chunk_pages < 1:
            raise ValueError("chunk_pages must be >= 1")
        if self.overlap_pages < 0:
            raise ValueError("overlap_pages must be >= 0")
        if self.overlap_pages >= self.chunk_pages:
            raise ValueError("overlap_pages must be smaller than chunk_pages")
        if self.ocr_chunk_pages < 1 or self.ocr_chunk_pages > 20:
            raise ValueError("ocr_chunk_pages must be between 1 and 20")
        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if self.start_page is not None and self.start_page < 1:
            raise ValueError("start_page must be >= 1")
        if self.end_page is not None and self.end_page < 1:
            raise ValueError("end_page must be >= 1")
        if (
            self.start_page is not None
            and self.end_page is not None
            and self.end_page < self.start_page
        ):
            raise ValueError("end_page must be >= start_page")
        if self.ocr_mode not in {"auto", "always", "never"}:
            raise ValueError("ocr_mode must be auto, always, or never")

    def compatibility_dict(self) -> dict[str, Any]:
        """Fields that must match for a safe resume."""
        return {
            "model": self.model,
            "chunk_pages": self.chunk_pages,
            "overlap_pages": self.overlap_pages,
            "ocr_mode": self.ocr_mode,
            "ocr_chunk_pages": self.ocr_chunk_pages,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "reasoning_effort": self.reasoning_effort,
        }

    def configuration_hash(self) -> str:
        payload = json.dumps(self.compatibility_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def masked_api_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["api_key"] = self.masked_api_key()
        data["prompts_dir"] = str(self.prompts_dir)
        return data


def load_config(
    *,
    model: str | None = None,
    chunk_pages: int | None = None,
    overlap_pages: int | None = None,
    ocr_mode: OcrMode | None = None,
    resume: bool = False,
    force: bool = False,
    start_page: int | None = None,
    end_page: int | None = None,
    max_workers: int | None = None,
    log_level: LogLevel | None = None,
    keep_intermediate: bool = False,
    dotenv_path: str | Path | None = None,
) -> AppConfig:
    """Load configuration from .env / environment, then apply CLI overrides."""
    if dotenv_path is not None:
        load_dotenv(dotenv_path, override=False)
    else:
        load_dotenv(override=False)

    config = AppConfig(
        api_key=_env_str("ZAI_API_KEY", ""),
        base_url=_env_str("ZAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        model=model or _env_str("GLM_MODEL", DEFAULT_MODEL),
        reasoning_effort=_env_str("GLM_REASONING_EFFORT", DEFAULT_REASONING_EFFORT),
        max_output_tokens=_env_int("GLM_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS),
        chunk_pages=chunk_pages if chunk_pages is not None else _env_int("PDF_CHUNK_PAGES", DEFAULT_CHUNK_PAGES),
        overlap_pages=(
            overlap_pages
            if overlap_pages is not None
            else _env_int("PDF_OVERLAP_PAGES", DEFAULT_OVERLAP_PAGES)
        ),
        ocr_chunk_pages=_env_int("OCR_CHUNK_PAGES", DEFAULT_OCR_CHUNK_PAGES),
        max_api_retries=_env_int("MAX_API_RETRIES", DEFAULT_MAX_RETRIES),
        request_timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        max_workers=max_workers if max_workers is not None else _env_int("MAX_WORKERS", DEFAULT_MAX_WORKERS),
        ocr_mode=ocr_mode or "auto",
        resume=resume,
        force=force,
        start_page=start_page,
        end_page=end_page,
        log_level=log_level or "INFO",
        keep_intermediate=keep_intermediate,
    )
    return config
