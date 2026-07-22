"""High-recall cheap-model routing before detailed GLM extraction."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from budget_extractor.checkpoint import CheckpointStore
from budget_extractor.config import AppConfig
from budget_extractor.costing import BudgetExceededError, CostTracker
from budget_extractor.glm_client import GlmClient
from budget_extractor.logging_utils import StructuredLoggerAdapter
from budget_extractor.pdf_processor import PageTextInfo, TextChunk, chunk_pages
from budget_extractor.prompts import load_prompt
from budget_extractor.utils import chunk_id_for_index, read_json
from budget_extractor.validation import parse_json_text


class ScoutCandidate(BaseModel):
    """A lightweight project signal returned by the scout."""

    model_config = ConfigDict(extra="ignore")

    project_name: str | None = None
    project_id: str | None = None
    pages: list[int] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    confidence: float = 0.5

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class ScoutChunkResult(BaseModel):
    """Validated routing decision for one scout window."""

    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    candidate_pages: list[int] = Field(default_factory=list)
    uncertain_pages: list[int] = Field(default_factory=list)
    continuation_pages: list[int] = Field(default_factory=list)
    candidates: list[ScoutCandidate] = Field(default_factory=list)
    notes: str | None = None

    @property
    def routed_pages(self) -> set[int]:
        pages = set(self.candidate_pages)
        pages.update(self.uncertain_pages)
        pages.update(self.continuation_pages)
        for candidate in self.candidates:
            pages.update(candidate.pages)
        return pages


class ScoutRunResult(BaseModel):
    """Auditable result of both scout passes."""

    model_config = ConfigDict(extra="ignore")

    document_hash: str
    configuration_hash: str
    scout_model: str
    total_pages_considered: int
    primary_windows: int = 0
    audit_windows: int = 0
    failed_windows: list[str] = Field(default_factory=list)
    deterministic_pages: list[int] = Field(default_factory=list)
    candidate_pages: list[int] = Field(default_factory=list)
    selected_pages: list[int] = Field(default_factory=list)
    filtered_pages: list[int] = Field(default_factory=list)
    primary_results: list[ScoutChunkResult] = Field(default_factory=list)
    audit_results: list[ScoutChunkResult] = Field(default_factory=list)
    fail_open: bool = False
    cache_used: bool = False
    completed_at: str = ""


class ProjectScout:
    """Runs a cheap high-recall pass and an audit pass over rejected windows."""

    def __init__(
        self,
        config: AppConfig,
        checkpoint: CheckpointStore,
        logger: StructuredLoggerAdapter,
        *,
        cost_tracker: CostTracker,
        client: GlmClient | None = None,
    ):
        self.config = config
        self.checkpoint = checkpoint
        self.logger = logger
        scout_config = replace(
            config,
            model=config.scout_model,
            reasoning_effort="low",
            max_output_tokens=config.scout_max_output_tokens,
            temperature=0.0,
            top_p=0.1,
            thinking_enabled=False,
            scout_mode="never",
        )
        self.client = client or GlmClient(scout_config, cost_tracker=cost_tracker)

    def run(
        self,
        pages: list[PageTextInfo],
        *,
        document_hash: str,
    ) -> ScoutRunResult:
        cached = self._load_cached_result(document_hash)
        if cached is not None:
            self.logger.event(
                "INFO",
                (
                    f"Loaded scout checkpoint: {len(cached.selected_pages)}/"
                    f"{cached.total_pages_considered} pages selected"
                ),
                stage="scout",
                status="cached",
            )
            return cached

        primary_windows = build_scout_windows(
            pages,
            chunk_size=self.config.scout_chunk_pages,
            overlap=self.config.scout_overlap_pages,
            pass_name="primary",
        )
        deterministic_pages = detect_signal_pages(pages)
        primary_results, primary_failures = self._run_windows(
            primary_windows,
            pass_name="primary",
        )
        primary_candidates = _collect_routed_pages(primary_results)
        primary_candidates.update(deterministic_pages)

        audit_windows: list[TextChunk] = []
        audit_results: list[ScoutChunkResult] = []
        audit_failures: list[str] = []
        if self.config.scout_audit_negatives:
            audit_windows = [
                _rename_window(window, pass_name="audit", index=index)
                for index, window in enumerate(primary_windows, start=1)
                if not (set(window.page_numbers) & primary_candidates)
            ]
            audit_results, audit_failures = self._run_windows(
                audit_windows,
                pass_name="audit",
            )

        candidate_pages = set(primary_candidates)
        candidate_pages.update(_collect_routed_pages(audit_results))
        candidate_pages.update(_pages_from_failed_windows(primary_windows, primary_failures))
        candidate_pages.update(_pages_from_failed_windows(audit_windows, audit_failures))

        available_pages = sorted(page.page_number for page in pages)
        selected_pages = expand_candidate_pages(
            candidate_pages,
            available_pages=available_pages,
            context_pages=self.config.scout_context_pages,
        )
        filtered_pages = sorted(set(available_pages) - set(selected_pages))
        failed_windows = sorted(set(primary_failures + audit_failures))

        result = ScoutRunResult(
            document_hash=document_hash,
            configuration_hash=self.config.configuration_hash(),
            scout_model=self.config.scout_model,
            total_pages_considered=len(available_pages),
            primary_windows=len(primary_windows),
            audit_windows=len(audit_windows),
            failed_windows=failed_windows,
            deterministic_pages=sorted(deterministic_pages),
            candidate_pages=sorted(candidate_pages),
            selected_pages=selected_pages,
            filtered_pages=filtered_pages,
            primary_results=primary_results,
            audit_results=audit_results,
            fail_open=bool(failed_windows),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.checkpoint.save_scout_result(result.model_dump(mode="json"))
        self.logger.event(
            "INFO",
            (
                f"Scout selected {len(selected_pages)}/{len(available_pages)} pages; "
                f"filtered {len(filtered_pages)}"
            ),
            stage="scout",
            model=self.config.scout_model,
            status="ok" if not failed_windows else "fail_open",
        )
        return result

    def _load_cached_result(self, document_hash: str) -> ScoutRunResult | None:
        if not self.config.resume or self.config.force:
            return None
        path = self.checkpoint.scout_result_path
        if not path.exists():
            return None
        try:
            result = ScoutRunResult.model_validate(read_json(path))
        except Exception:  # noqa: BLE001
            return None
        if result.document_hash != document_hash:
            return None
        if result.configuration_hash != self.config.configuration_hash():
            return None
        result.cache_used = True
        return result

    def _run_windows(
        self,
        windows: list[TextChunk],
        *,
        pass_name: str,
    ) -> tuple[list[ScoutChunkResult], list[str]]:
        results: list[ScoutChunkResult] = []
        failures: list[str] = []
        for index, window in enumerate(windows):
            try:
                result = self._classify_window(window, pass_name=pass_name)
                results.append(result)
            except BudgetExceededError:
                raise
            except Exception as exc:  # noqa: BLE001
                remaining = windows[index:] if _is_fatal_scout_error(exc) else [window]
                for failed_window in remaining:
                    failures.append(failed_window.chunk_id)
                    results.append(
                        ScoutChunkResult(
                            chunk_id=failed_window.chunk_id,
                            candidate_pages=list(failed_window.page_numbers),
                            uncertain_pages=list(failed_window.page_numbers),
                            notes=f"Scout failed; fail-open routing used: {exc}",
                        )
                    )
                    self.checkpoint.write_scout_status(
                        failed_window.chunk_id,
                        {
                            "chunk_id": failed_window.chunk_id,
                            "pass": pass_name,
                            "pages": failed_window.page_numbers,
                            "status": "failed_open",
                            "error": str(exc),
                        },
                    )
                self.logger.event(
                    "WARNING",
                    (
                        f"Scout window failed open: {exc}"
                        + (
                            "; remaining windows also routed open"
                            if len(remaining) > 1
                            else ""
                        )
                    ),
                    stage="scout",
                    chunk_id=window.chunk_id,
                    page_range=f"{window.start_page}-{window.end_page}",
                    model=self.config.scout_model,
                    status="failed_open",
                )
                if len(remaining) > 1:
                    break
        return results, failures

    def _classify_window(
        self,
        window: TextChunk,
        *,
        pass_name: str,
    ) -> ScoutChunkResult:
        messages = build_scout_messages(
            prompts_dir=self.config.prompts_dir,
            window=window,
            audit=pass_name == "audit",
        )
        completion = self.client.complete_json(messages)
        self.checkpoint.write_scout_raw_response(
            window.chunk_id,
            {
                "request_id": completion.request_id,
                "finish_reason": completion.finish_reason,
                "content": completion.content,
                "raw_response": completion.raw_response,
            },
        )
        if completion.truncated:
            raise ValueError("scout completion was truncated")

        parsed = parse_json_text(completion.content)
        if not isinstance(parsed, dict):
            raise ValueError("scout response root must be an object")
        parsed.setdefault("chunk_id", window.chunk_id)
        result = ScoutChunkResult.model_validate(parsed)
        result = sanitize_scout_result(result, allowed_pages=set(window.page_numbers))
        self.checkpoint.write_scout_validated(
            window.chunk_id,
            result.model_dump(mode="json"),
        )
        self.checkpoint.write_scout_status(
            window.chunk_id,
            {
                "chunk_id": window.chunk_id,
                "pass": pass_name,
                "pages": window.page_numbers,
                "status": "ok",
                "request_id": completion.request_id,
                "candidate_pages": sorted(result.routed_pages),
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
            },
        )
        return result


def build_scout_messages(
    *,
    prompts_dir: str | Path,
    window: TextChunk,
    audit: bool,
) -> list[dict[str, str]]:
    system_prompt = load_prompt(prompts_dir, "project_scout.md")
    if audit:
        task = (
            "This is an independent false-negative audit of a window rejected by "
            "the first scout. Search especially for continuation pages, terse table "
            "rows, capital outlay, studies, technology, equipment, land, and project IDs."
        )
    else:
        task = (
            "Perform the primary high-recall routing pass. Include uncertain pages "
            "rather than risking a false negative."
        )
    user_prompt = (
        f"{task}\n\n"
        f"Chunk ID: {window.chunk_id}\n"
        f"Pages: {window.start_page}-{window.end_page}\n\n"
        "Return JSON only.\n\n"
        f"PAGE TEXT START\n{window.text}\nPAGE TEXT END"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_scout_windows(
    pages: list[PageTextInfo],
    *,
    chunk_size: int,
    overlap: int,
    pass_name: str,
) -> list[TextChunk]:
    base_windows = chunk_pages(
        pages,
        chunk_pages=chunk_size,
        overlap_pages=overlap,
    )
    return [
        _rename_window(window, pass_name=pass_name, index=index)
        for index, window in enumerate(base_windows, start=1)
    ]


def build_selected_extraction_chunks(
    pages: list[PageTextInfo],
    *,
    selected_pages: list[int],
    chunk_size: int,
    overlap: int,
) -> list[TextChunk]:
    """Build contiguous heavy-model chunks from selected page ranges."""
    selected = set(selected_pages)
    page_map = {page.page_number: page for page in pages}
    available = sorted(selected & set(page_map))
    if not available:
        return []

    runs: list[list[int]] = []
    current: list[int] = []
    for page_number in available:
        if current and page_number != current[-1] + 1:
            runs.append(current)
            current = []
        current.append(page_number)
    if current:
        runs.append(current)

    chunks: list[TextChunk] = []
    for run in runs:
        run_pages = [page_map[page_number] for page_number in run]
        chunks.extend(
            chunk_pages(
                run_pages,
                chunk_pages=chunk_size,
                overlap_pages=overlap,
            )
        )

    return [
        TextChunk(
            chunk_id=chunk_id_for_index(index),
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            text=chunk.text,
            page_numbers=chunk.page_numbers,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def sanitize_scout_result(
    result: ScoutChunkResult,
    *,
    allowed_pages: set[int],
) -> ScoutChunkResult:
    result.candidate_pages = _sanitize_pages(result.candidate_pages, allowed_pages)
    result.uncertain_pages = _sanitize_pages(result.uncertain_pages, allowed_pages)
    result.continuation_pages = _sanitize_pages(result.continuation_pages, allowed_pages)
    for candidate in result.candidates:
        candidate.pages = _sanitize_pages(candidate.pages, allowed_pages)
    return result


def detect_signal_pages(pages: list[PageTextInfo]) -> set[int]:
    """Deterministic safety net independent of model classification."""
    result: set[int] = set()
    for page in pages:
        text = page.text or ""
        lowered = text.lower()
        if any(pattern.search(lowered) for pattern in _STRONG_SIGNAL_PATTERNS):
            result.add(page.page_number)
            continue

        score = 0
        if _PROJECT_TERM_RE.search(lowered):
            score += 1
        if _BUDGET_TERM_RE.search(lowered):
            score += 1
        if _SCOPE_TERM_RE.search(lowered):
            score += 1
        if _SCHEDULE_TERM_RE.search(lowered):
            score += 1
        if _PROJECT_ID_RE.search(text):
            score += 1
        if score >= 3:
            result.add(page.page_number)
    return result


def expand_candidate_pages(
    candidate_pages: set[int],
    *,
    available_pages: list[int],
    context_pages: int,
) -> list[int]:
    available = set(available_pages)
    expanded: set[int] = set()
    for page in candidate_pages:
        for candidate in range(page - context_pages, page + context_pages + 1):
            if candidate in available:
                expanded.add(candidate)
    return sorted(expanded)


def _rename_window(window: TextChunk, *, pass_name: str, index: int) -> TextChunk:
    return TextChunk(
        chunk_id=f"scout_{pass_name}_{index:04d}",
        start_page=window.start_page,
        end_page=window.end_page,
        text=window.text,
        page_numbers=window.page_numbers,
    )


def _collect_routed_pages(results: list[ScoutChunkResult]) -> set[int]:
    pages: set[int] = set()
    for result in results:
        pages.update(result.routed_pages)
    return pages


def _pages_from_failed_windows(
    windows: list[TextChunk],
    failed_window_ids: list[str],
) -> set[int]:
    failed = set(failed_window_ids)
    return {
        page
        for window in windows
        if window.chunk_id in failed
        for page in window.page_numbers
    }


def _sanitize_pages(pages: list[int], allowed_pages: set[int]) -> list[int]:
    sanitized: set[int] = set()
    for value in pages:
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page in allowed_pages:
            sanitized.add(page)
    return sorted(sanitized)


def _is_fatal_scout_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "api key",
            "authentication",
            "unauthorized",
            "forbidden",
            "model not found",
            "invalid model",
            "invalid request",
            "401",
            "403",
        )
    )


_STRONG_SIGNAL_PATTERNS = [
    re.compile(r"\bproject details\b"),
    re.compile(r"\bproject description\s*:"),
    re.compile(r"\bproject funding information\b"),
    re.compile(r"\bfuture appropriations\b"),
    re.compile(r"\bcapital improvement projects?\b"),
    re.compile(r"\b(?:cip|project)\s*(?:number|no\.?|#|id)\b"),
]
_PROJECT_TERM_RE = re.compile(
    r"\b(project|initiative|capital outlay|feasibility study|master plan)\b"
)
_BUDGET_TERM_RE = re.compile(
    r"(\$[\d,.]+|\bappropriat(?:ed|ion)|\bbudget\b|\bfunding\b|\bcost\b)"
)
_SCOPE_TERM_RE = re.compile(
    r"\b(construction|replacement|rehabilitation|renovation|acquisition|"
    r"implementation|upgrade|improvement|design|engineering)\b"
)
_SCHEDULE_TERM_RE = re.compile(
    r"\b(start date|completion date|anticipated completion|future year|fy\s*20\d{2})\b"
)
_PROJECT_ID_RE = re.compile(r"\b[A-Z]{1,5}[- ]?\d{3,6}\b")
