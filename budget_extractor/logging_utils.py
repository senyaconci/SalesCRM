"""Structured logging helpers and in-memory run log for Excel export."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunLogEntry:
    timestamp: str
    level: str
    stage: str
    chunk_id: str | None = None
    page_range: str | None = None
    request_id: str | None = None
    model: str | None = None
    attempt: int | None = None
    status: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    message: str = ""


@dataclass
class RunLogBuffer:
    """Collects structured run events for the Excel Run Log sheet."""

    entries: list[RunLogEntry] = field(default_factory=list)

    def add(self, entry: RunLogEntry) -> None:
        self.entries.append(entry)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [entry.__dict__.copy() for entry in self.entries]


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that also writes selected events into a RunLogBuffer."""

    def __init__(self, logger: logging.Logger, run_log: RunLogBuffer):
        super().__init__(logger, {})
        self.run_log = run_log

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        return msg, kwargs

    def event(
        self,
        level: str,
        message: str,
        *,
        stage: str,
        chunk_id: str | None = None,
        page_range: str | None = None,
        request_id: str | None = None,
        model: str | None = None,
        attempt: int | None = None,
        status: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        entry = RunLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.upper(),
            stage=stage,
            chunk_id=chunk_id,
            page_range=page_range,
            request_id=request_id,
            model=model,
            attempt=attempt,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            message=message,
        )
        self.run_log.add(entry)
        log_fn = getattr(self.logger, level.lower(), self.logger.info)
        extras = []
        if chunk_id:
            extras.append(f"chunk={chunk_id}")
        if page_range:
            extras.append(f"pages={page_range}")
        if request_id:
            extras.append(f"request_id={request_id}")
        if status:
            extras.append(f"status={status}")
        suffix = f" ({', '.join(extras)})" if extras else ""
        log_fn("%s%s", message, suffix)


def setup_logging(level: str = "INFO") -> logging.Logger:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)

    # Quiet noisy HTTP libraries unless debugging.
    if level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logging.getLogger("budget_extractor")


def create_app_logger(level: str = "INFO") -> StructuredLoggerAdapter:
    base = setup_logging(level)
    return StructuredLoggerAdapter(base, RunLogBuffer())
