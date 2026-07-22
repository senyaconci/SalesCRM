"""End-to-end two-pass extraction orchestration."""

from __future__ import annotations

import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from budget_extractor import __version__
from budget_extractor.aggregation import (
    AGGREGATION_METHOD,
    build_document_quality_issues,
    build_summary,
)
from budget_extractor.checkpoint import CheckpointStore
from budget_extractor.config import AppConfig
from budget_extractor.costing import BudgetExceededError, CostTracker
from budget_extractor.deduplication import consolidate_projects
from budget_extractor.excel_exporter import export_excel_workbook
from budget_extractor.glm_client import GlmClient
from budget_extractor.json_exporter import export_json_outputs
from budget_extractor.logging_utils import StructuredLoggerAdapter
from budget_extractor.ocr_client import OcrClient
from budget_extractor.pdf_processor import (
    TextChunk,
    acquire_pdf,
    apply_ocr_text,
    chunk_pages,
    default_work_dirs,
    extract_native_text,
    mark_ocr_failures,
    suggest_document_title,
)
from budget_extractor.prompts import SCHEMA_SUMMARY, build_extraction_messages, build_repair_messages
from budget_extractor.schemas import (
    DocumentMetadata,
    FinalExtractionOutput,
    ProjectRecord,
    RunStatistics,
    ValidationIssue,
)
from budget_extractor.scouting import (
    ProjectScout,
    ScoutRunResult,
    build_selected_extraction_chunks,
)
from budget_extractor.utils import atomic_write_json, atomic_write_text, pages_to_range_label
from budget_extractor.validation import (
    parse_json_text,
    projects_to_validation_issues,
    validate_chunk_payload,
)


class ExtractionPipeline:
    """Checkpointed Pass A / Pass B capital-project extractor."""

    def __init__(
        self,
        config: AppConfig,
        logger: StructuredLoggerAdapter,
        *,
        glm_client: GlmClient | None = None,
        ocr_client: OcrClient | None = None,
        scout_client: GlmClient | None = None,
    ):
        self.config = config
        self.logger = logger
        self.cost_tracker = CostTracker(max_cost_usd=config.max_cost_usd)
        self.glm = glm_client or GlmClient(config, cost_tracker=self.cost_tracker)
        if glm_client is not None and getattr(glm_client, "cost_tracker", None) is None:
            glm_client.cost_tracker = self.cost_tracker  # type: ignore[attr-defined]
        self.ocr: OcrClient | None = None
        self._ocr_factory = ocr_client
        self.scout_client = scout_client
        self.stats = RunStatistics()
        self.budget_stopped = False

    def run(self, input_path: str, output_dir: str | Path) -> tuple[FinalExtractionOutput, dict[str, Path], int]:
        started = datetime.now(timezone.utc)
        dirs = default_work_dirs(output_dir)
        checkpoint = CheckpointStore(dirs["output"])

        self.logger.event("INFO", "Starting extraction run", stage="startup")
        document = acquire_pdf(input_path, dirs["downloads"])
        checkpoint.load_or_create(
            document_hash=document.sha256,
            configuration_hash=self.config.configuration_hash(),
            resume=self.config.resume,
            force=self.config.force,
        )

        extracted = extract_native_text(
            document,
            start_page=self.config.start_page,
            end_page=self.config.end_page,
        )
        self.logger.event(
            "INFO",
            f"Extracted native text for {len(extracted.pages)} pages",
            stage="pdf_text",
        )

        # OCR stage
        self.ocr = self._ocr_factory or OcrClient(
            self.config, checkpoint, cost_tracker=self.cost_tracker
        )
        ocr_pages = self.ocr.select_ocr_pages(extracted.pages, mode=self.config.ocr_mode)
        ocr_result = self.ocr.run_ocr(
            source_pdf=document.local_path,
            page_numbers=ocr_pages,
            ocr_dir=dirs["ocr"],
        )
        if ocr_result.page_texts:
            extracted = apply_ocr_text(extracted, ocr_result.page_texts)
        if ocr_result.failed_pages:
            extracted = mark_ocr_failures(extracted, ocr_result.failed_pages)
            for page in ocr_result.failed_pages:
                self.logger.event(
                    "WARNING",
                    f"OCR failed for page {page}",
                    stage="ocr",
                    status="failed",
                )

        if self.config.keep_intermediate:
            atomic_write_text(dirs["intermediate"] / "full_text.txt", extracted.full_text)

        pages_native = sum(1 for p in extracted.pages if not p.used_ocr and not p.is_empty)
        pages_ocr = sum(1 for p in extracted.pages if p.used_ocr)
        pages_failed = sorted(
            {p.page_number for p in extracted.pages if p.ocr_failed}
            | set(ocr_result.failed_pages)
        )
        self.stats.pages_native_text = pages_native
        self.stats.pages_ocr = pages_ocr
        self.stats.pages_failed = len(pages_failed)

        scout_result: ScoutRunResult | None = None
        if self.config.scout_mode == "auto":
            self.stats.scout_enabled = True
            self.stats.scout_model = self.config.scout_model
            try:
                scout = ProjectScout(
                    self.config,
                    checkpoint,
                    self.logger,
                    cost_tracker=self.cost_tracker,
                    client=self.scout_client,
                )
                scout_result = scout.run(
                    extracted.pages,
                    document_hash=document.sha256,
                )
                self.scout_client = scout.client
                chunks = build_selected_extraction_chunks(
                    extracted.pages,
                    selected_pages=scout_result.selected_pages,
                    chunk_size=self.config.chunk_pages,
                    overlap=self.config.overlap_pages,
                )
                self.stats.scout_primary_windows = scout_result.primary_windows
                self.stats.scout_audit_windows = scout_result.audit_windows
                self.stats.scout_failed_windows = len(scout_result.failed_windows)
                self.stats.scout_candidate_pages = len(scout_result.candidate_pages)
                self.stats.heavy_pages_selected = len(scout_result.selected_pages)
                self.stats.pages_filtered_before_extraction = len(
                    scout_result.filtered_pages
                )
            except BudgetExceededError:
                raise
            except Exception as exc:  # noqa: BLE001
                # Scouting is an optimization. Failure must not suppress projects.
                self.logger.event(
                    "WARNING",
                    f"Scout stage failed; processing all pages: {exc}",
                    stage="scout",
                    model=self.config.scout_model,
                    status="failed_open",
                )
                chunks = chunk_pages(
                    extracted.pages,
                    chunk_pages=self.config.chunk_pages,
                    overlap_pages=self.config.overlap_pages,
                )
                self.stats.scout_failed_windows += 1
                self.stats.heavy_pages_selected = len(extracted.pages)
        else:
            chunks = chunk_pages(
                extracted.pages,
                chunk_pages=self.config.chunk_pages,
                overlap_pages=self.config.overlap_pages,
            )
            self.stats.heavy_pages_selected = len(extracted.pages)
        self.stats.chunks_total = len(chunks)
        self.logger.event(
            "INFO",
            f"Created {len(chunks)} detailed extraction chunks",
            stage="chunking",
        )

        # Pass A
        validation_issues: list[ValidationIssue] = []
        for page in pages_failed:
            validation_issues.append(
                ValidationIssue(
                    severity="warning",
                    issue_type="unreadable_source_page",
                    pages=[page],
                    description=f"Page {page} was unreadable or OCR failed.",
                    recommended_review="Inspect the original PDF page and consider manual OCR.",
                )
            )
            # Annotate page quality for later project flags where relevant.

        chunk_results = self._process_chunks(
            chunks=chunks,
            checkpoint=checkpoint,
            document_title=suggest_document_title(document),
            total_pages=document.total_pages,
            document_hash=document.sha256,
        )

        raw_projects: list[ProjectRecord] = []
        for chunk_id, result in chunk_results.items():
            if result is None:
                continue
            raw_projects.extend(result.projects)
            validation_issues.extend(
                projects_to_validation_issues(chunk_id, result.chunk_validation_issues)
            )

        # Flag OCR-derived projects
        ocr_page_set = {p.page_number for p in extracted.pages if p.used_ocr}
        for project in raw_projects:
            if set(project.source_pages) & ocr_page_set:
                if "ocr_derived_text" not in project.quality_flags:
                    project.quality_flags.append("ocr_derived_text")
            if set(project.source_pages) & set(pages_failed):
                if "unreadable_source_page" not in project.quality_flags:
                    project.quality_flags.append("unreadable_source_page")

        # Pass B
        self.logger.event("INFO", "Starting consolidation pass", stage="consolidation")
        use_llm_dupes = True
        if self.cost_tracker.max_cost_usd is not None:
            remaining = self.cost_tracker.remaining_usd() or 0.0
            if remaining < 0.25:
                use_llm_dupes = False
                self.logger.event(
                    "WARNING",
                    "Skipping GLM duplicate resolution to preserve spend cap",
                    stage="budget",
                    status="skipped",
                )
        try:
            final_projects, duplicate_audit = consolidate_projects(
                raw_projects,
                document_hash=document.sha256,
                glm_client=self.glm,
                prompts_dir=str(self.config.prompts_dir),
                use_llm_for_ambiguous=use_llm_dupes,
            )
        except BudgetExceededError as exc:
            self.budget_stopped = True
            self.logger.event(
                "WARNING",
                f"Consolidation hit spend cap; falling back to deterministic merges: {exc}",
                stage="budget",
                status="stopped",
            )
            final_projects, duplicate_audit = consolidate_projects(
                raw_projects,
                document_hash=document.sha256,
                glm_client=None,
                use_llm_for_ambiguous=False,
            )
        checkpoint.mark_consolidation_completed()

        merged_count = max(0, len(raw_projects) - len(final_projects))
        summary = build_summary(
            raw_count=len(raw_projects),
            projects=final_projects,
            duplicate_merged_count=merged_count,
        )
        validation_issues.extend(build_document_quality_issues(final_projects))
        if self.budget_stopped and self.stats.chunks_completed < self.stats.chunks_total:
            validation_issues.append(
                ValidationIssue(
                    severity="warning",
                    issue_type="budget_cap_stop",
                    description=(
                        f"Processing stopped early to respect spend cap "
                        f"(${self.config.max_cost_usd:.2f}). "
                        f"Estimated spend ${self.cost_tracker.estimated_cost_usd:.4f}. "
                        f"Completed {self.stats.chunks_completed}/{self.stats.chunks_total} chunks."
                    ),
                    recommended_review="Raise --max-cost-usd or resume later to finish remaining chunks.",
                )
            )

        completed = datetime.now(timezone.utc)
        self._refresh_api_stats()

        org_guess = (
            (document.metadata.get("author") or "")
            or _guess_organization(suggest_document_title(document))
        )
        fy_guess = _guess_fiscal_year(suggest_document_title(document), extracted.full_text[:5000])

        final = FinalExtractionOutput(
            document_metadata=DocumentMetadata(
                document_title=suggest_document_title(document),
                organization_name=org_guess,
                fiscal_year_or_period=fy_guess,
                source_file=document.filename,
                source_url=document.source_url,
                file_sha256=document.sha256,
                total_pages=document.total_pages,
                processed_pages=len(extracted.pages),
                ocr_pages=sorted(ocr_page_set),
                failed_pages=pages_failed,
                processing_started_at=started.isoformat(),
                processing_completed_at=completed.isoformat(),
                model=self.config.model,
                application_version=__version__,
                aggregation_method=AGGREGATION_METHOD,
            ),
            summary=summary,
            projects=final_projects,
            validation_issues=validation_issues,
            duplicate_audit=duplicate_audit,
            run_statistics=self.stats,
        )

        paths = export_json_outputs(final, dirs["output"], source_filename=document.filename)
        xlsx_path = export_excel_workbook(
            final,
            dirs["output"],
            source_filename=document.filename,
            run_log=self.logger.run_log.entries,
        )
        paths["xlsx"] = xlsx_path
        checkpoint.mark_exports_completed()

        exit_code = 0
        if self.stats.chunks_failed or self.budget_stopped:
            exit_code = 2

        self.logger.event(
            "INFO",
            f"Extraction complete: {summary.final_project_count} projects "
            f"({self.stats.chunks_failed} failed chunks); "
            f"estimated API cost ${self.cost_tracker.estimated_cost_usd:.4f}",
            stage="complete",
            status="ok" if exit_code == 0 else "partial",
        )
        print(
            f"Estimated API cost: ${self.cost_tracker.estimated_cost_usd:.4f}"
            + (
                f" / cap ${self.config.max_cost_usd:.2f}"
                if self.config.max_cost_usd is not None
                else ""
            )
        )
        return final, paths, exit_code

    def _process_chunks(
        self,
        *,
        chunks: list[TextChunk],
        checkpoint: CheckpointStore,
        document_title: str,
        total_pages: int,
        document_hash: str,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        def handle(chunk: TextChunk) -> tuple[str, Any]:
            return chunk.chunk_id, self._process_single_chunk(
                chunk=chunk,
                checkpoint=checkpoint,
                document_title=document_title,
                total_pages=total_pages,
                document_hash=document_hash,
            )

        pending = []
        for chunk in chunks:
            if (
                self.config.resume
                and not self.config.force
                and checkpoint.is_chunk_completed(chunk.chunk_id)
            ):
                validated = checkpoint.chunk_paths(chunk.chunk_id)["validated"]
                payload = json.loads(validated.read_text(encoding="utf-8"))
                # Rehydrate through validator for typed objects.
                result, _, _ = validate_chunk_payload(
                    payload,
                    chunk_id=chunk.chunk_id,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    document_hash=document_hash,
                    total_pages=total_pages,
                )
                results[chunk.chunk_id] = result
                self.stats.chunks_completed += 1
                self.logger.event(
                    "INFO",
                    "Skipping completed chunk",
                    stage="pass_a",
                    chunk_id=chunk.chunk_id,
                    page_range=pages_to_range_label(chunk.start_page, chunk.end_page),
                    status="skipped",
                )
            else:
                pending.append(chunk)

        if self.config.max_workers <= 1 or len(pending) <= 1:
            for chunk in pending:
                try:
                    chunk_id, result = handle(chunk)
                except BudgetExceededError as exc:
                    self.budget_stopped = True
                    self.logger.event(
                        "WARNING",
                        f"Stopping Pass A due to spend cap: {exc}",
                        stage="budget",
                        status="stopped",
                    )
                    break
                results[chunk_id] = result
        else:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {executor.submit(handle, chunk): chunk for chunk in pending}
                for future in as_completed(futures):
                    try:
                        chunk_id, result = future.result()
                    except BudgetExceededError as exc:
                        self.budget_stopped = True
                        self.logger.event(
                            "WARNING",
                            f"Stopping Pass A due to spend cap: {exc}",
                            stage="budget",
                            status="stopped",
                        )
                        break
                    results[chunk_id] = result

        return results

    def _process_single_chunk(
        self,
        *,
        chunk: TextChunk,
        checkpoint: CheckpointStore,
        document_title: str,
        total_pages: int,
        document_hash: str,
    ) -> Any:
        paths = checkpoint.chunk_paths(chunk.chunk_id)
        checkpoint.write_chunk_input(chunk.chunk_id, chunk.text)
        started = datetime.now(timezone.utc).isoformat()
        attempts = 0
        request_ids: list[str] = []
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        page_range = pages_to_range_label(chunk.start_page, chunk.end_page)

        status: dict[str, Any] = {
            "chunk_id": chunk.chunk_id,
            "page_range": [chunk.start_page, chunk.end_page],
            "started_timestamp": started,
            "completed_timestamp": None,
            "number_of_attempts": 0,
            "request_ids": [],
            "token_usage": token_usage,
            "number_of_projects_extracted": 0,
            "validation_status": "pending",
            "error_details": None,
        }

        try:
            messages = build_extraction_messages(
                prompts_dir=self.config.prompts_dir,
                chunk=chunk,
                document_title=document_title,
                total_pages=total_pages,
            )
            attempts += 1
            completion = self.glm.complete_json(messages)
            request_ids.append(completion.request_id)
            token_usage["prompt_tokens"] += completion.prompt_tokens
            token_usage["completion_tokens"] += completion.completion_tokens
            token_usage["total_tokens"] += completion.total_tokens

            raw_payload = {
                "request_id": completion.request_id,
                "finish_reason": completion.finish_reason,
                "truncated": completion.truncated,
                "content": completion.content,
                "raw_response": completion.raw_response,
            }
            atomic_write_json(paths["raw_response"], raw_payload)

            if completion.truncated:
                raise ValueError(f"Model output truncated (finish_reason={completion.finish_reason})")

            try:
                parsed = parse_json_text(completion.content)
            except Exception as parse_exc:
                # Repair pass
                self.logger.event(
                    "WARNING",
                    f"Invalid JSON for {chunk.chunk_id}; attempting repair",
                    stage="repair",
                    chunk_id=chunk.chunk_id,
                    page_range=page_range,
                    request_id=completion.request_id,
                )
                repair_messages = build_repair_messages(
                    prompts_dir=self.config.prompts_dir,
                    invalid_json=completion.content[:120000],
                    validation_errors=str(parse_exc),
                    schema_summary=SCHEMA_SUMMARY,
                )
                attempts += 1
                repair = self.glm.complete_json(repair_messages)
                request_ids.append(repair.request_id)
                token_usage["prompt_tokens"] += repair.prompt_tokens
                token_usage["completion_tokens"] += repair.completion_tokens
                token_usage["total_tokens"] += repair.total_tokens
                atomic_write_json(
                    paths["raw_response"].with_name(f"{chunk.chunk_id}_raw_response_repair.json"),
                    {
                        "request_id": repair.request_id,
                        "content": repair.content,
                        "raw_response": repair.raw_response,
                    },
                )
                parsed = parse_json_text(repair.content)

            result, project_errors, accepted = validate_chunk_payload(
                parsed,
                chunk_id=chunk.chunk_id,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                document_hash=document_hash,
                total_pages=total_pages,
            )

            raw_project_count = 0
            if isinstance(parsed, dict) and isinstance(parsed.get("projects"), list):
                raw_project_count = len(parsed.get("projects") or [])

            needs_repair = result is None or (
                raw_project_count > 0 and len(accepted) == 0 and bool(project_errors)
            )
            if needs_repair:
                # Root invalid or every project failed local validation — ask GLM to repair.
                repair_messages = build_repair_messages(
                    prompts_dir=self.config.prompts_dir,
                    invalid_json=json.dumps(parsed, ensure_ascii=False)[:120000]
                    if not isinstance(parsed, str)
                    else str(parsed)[:120000],
                    validation_errors="; ".join(project_errors) or "Root validation failed",
                    schema_summary=SCHEMA_SUMMARY,
                )
                attempts += 1
                repair = self.glm.complete_json(repair_messages)
                request_ids.append(repair.request_id)
                token_usage["prompt_tokens"] += repair.prompt_tokens
                token_usage["completion_tokens"] += repair.completion_tokens
                token_usage["total_tokens"] += repair.total_tokens
                atomic_write_json(
                    paths["raw_response"].with_name(f"{chunk.chunk_id}_raw_response_repair.json"),
                    {
                        "request_id": repair.request_id,
                        "content": repair.content,
                        "raw_response": repair.raw_response,
                    },
                )
                parsed = parse_json_text(repair.content)
                result, project_errors, accepted = validate_chunk_payload(
                    parsed,
                    chunk_id=chunk.chunk_id,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    document_hash=document_hash,
                    total_pages=total_pages,
                )

            if result is None:
                raise ValueError(
                    "Chunk validation failed after repair: " + "; ".join(project_errors)
                )

            # Persist validated payload (even if some projects were rejected as issues).
            atomic_write_json(paths["validated"], result.model_dump(mode="json"))
            status.update(
                {
                    "completed_timestamp": datetime.now(timezone.utc).isoformat(),
                    "number_of_attempts": attempts,
                    "request_ids": request_ids,
                    "token_usage": token_usage,
                    "number_of_projects_extracted": len(result.projects),
                    "validation_status": "ok" if not project_errors else "partial",
                    "error_details": "; ".join(project_errors) if project_errors else None,
                }
            )
            atomic_write_json(paths["status"], status)
            checkpoint.mark_chunk_completed(chunk.chunk_id)
            self.stats.chunks_completed += 1
            self.logger.event(
                "INFO",
                f"Extracted {len(result.projects)} projects",
                stage="pass_a",
                chunk_id=chunk.chunk_id,
                page_range=page_range,
                request_id=request_ids[-1] if request_ids else None,
                model=self.config.model,
                attempt=attempts,
                status=status["validation_status"],
                prompt_tokens=token_usage["prompt_tokens"],
                completion_tokens=token_usage["completion_tokens"],
            )
            return result

        except BudgetExceededError:
            raise
        except Exception as exc:  # noqa: BLE001
            status.update(
                {
                    "completed_timestamp": datetime.now(timezone.utc).isoformat(),
                    "number_of_attempts": attempts,
                    "request_ids": request_ids,
                    "token_usage": token_usage,
                    "validation_status": "failed",
                    "error_details": f"{exc}\n{traceback.format_exc(limit=3)}",
                }
            )
            atomic_write_json(paths["status"], status)
            checkpoint.mark_chunk_failed(chunk.chunk_id)
            self.stats.chunks_failed += 1
            self.logger.event(
                "ERROR",
                f"Chunk failed: {exc}",
                stage="pass_a",
                chunk_id=chunk.chunk_id,
                page_range=page_range,
                attempt=attempts,
                status="failed",
            )
            return None

    def _refresh_api_stats(self) -> None:
        scout_requests = self.scout_client.api_requests if self.scout_client else 0
        scout_retries = self.scout_client.api_retries if self.scout_client else 0
        scout_prompt = self.scout_client.prompt_tokens if self.scout_client else 0
        scout_completion = self.scout_client.completion_tokens if self.scout_client else 0
        scout_total = self.scout_client.total_tokens if self.scout_client else 0

        self.stats.scout_api_requests = scout_requests
        self.stats.scout_prompt_tokens = scout_prompt
        self.stats.scout_completion_tokens = scout_completion
        self.stats.api_requests = (
            self.glm.api_requests
            + scout_requests
            + (self.ocr.api_requests if self.ocr else 0)
        )
        self.stats.api_retries = (
            self.glm.api_retries
            + scout_retries
            + (self.ocr.api_retries if self.ocr else 0)
        )
        self.stats.prompt_tokens = self.glm.prompt_tokens + scout_prompt
        self.stats.completion_tokens = self.glm.completion_tokens + scout_completion
        self.stats.total_tokens = self.glm.total_tokens + scout_total


def _guess_organization(title: str) -> str:
    text = title.lower()
    if "columbia" in text or "como" in text:
        return "City of Columbia, Missouri"
    return ""


def _guess_fiscal_year(title: str, sample_text: str) -> str:
    import re

    for source in (title, sample_text):
        match = re.search(r"\bFY\s?20?(\d{2})\b", source, flags=re.IGNORECASE)
        if match:
            year = match.group(1)
            return f"FY20{year}" if len(year) == 2 else f"FY{year}"
        match = re.search(r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", source)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
    return ""
