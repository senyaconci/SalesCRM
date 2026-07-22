from __future__ import annotations

import json
from pathlib import Path

import fitz

from budget_extractor.config import AppConfig
from budget_extractor.extraction import ExtractionPipeline
from budget_extractor.glm_client import GlmCompletionResult
from budget_extractor.logging_utils import create_app_logger
from budget_extractor.ocr_client import OcrChunkResult, OcrClient


class FakeGlm:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.api_requests = 0
        self.api_retries = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.calls = 0

    def complete_json(self, messages, **kwargs):
        self.calls += 1
        self.api_requests += 1
        content = self.responses.pop(0) if self.responses else '{"projects":[],"chunk_validation_issues":[]}'
        self.prompt_tokens += 10
        self.completion_tokens += 20
        self.total_tokens += 30
        return GlmCompletionResult(
            content=content,
            request_id=f"req-{self.calls}",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            raw_response={"id": f"req-{self.calls}"},
            truncated=False,
        )


class FakeOcr(OcrClient):
    def __init__(self, *args, **kwargs):
        self.api_requests = 0
        self.api_retries = 0
        self.cost_tracker = kwargs.get("cost_tracker")

    def select_ocr_pages(self, pages, *, mode):
        return []

    def run_ocr(self, *, source_pdf, page_numbers, ocr_dir):
        return OcrChunkResult({}, [], [], [])


def _make_pdf(path: Path, pages: int = 3) -> None:
    doc = fitz.open()
    for i in range(1, pages + 1):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Capital Project: Bridge Deck Repair #{i}. Total project cost $1,250,000. Design phase.",
        )
    doc.save(path)
    doc.close()


def test_pipeline_with_mocked_glm(tmp_path: Path):
    pdf_path = tmp_path / "budget.pdf"
    _make_pdf(pdf_path, pages=3)

    response = {
        "chunk_metadata": {"chunk_id": "chunk_0001", "start_page": 1, "end_page": 3},
        "projects": [
            {
                "project_name": "Bridge Deck Repair",
                "project_id": "CIP-BR-1",
                "current_phase": "preliminary_design",
                "pre_rfp_status": "strong_pre_rfp",
                "source_pages": [1, 2],
                "evidence": [{"page": 1, "quote": "Bridge Deck Repair total project cost $1,250,000"}],
                "confidence_score": 0.93,
                "first_seen_chunk": "chunk_0001",
                "total_project_budget": 1250000,
                "department_or_agency": "Public Works",
            }
        ],
        "chunk_validation_issues": [],
    }

    config = AppConfig(
        api_key="test-key",
        chunk_pages=20,
        overlap_pages=2,
        ocr_mode="never",
        scout_mode="never",
        keep_intermediate=True,
        prompts_dir=Path(__file__).resolve().parents[1] / "prompts",
    )
    logger = create_app_logger("WARNING")
    pipeline = ExtractionPipeline(
        config,
        logger,
        glm_client=FakeGlm([json.dumps(response)]),
        ocr_client=FakeOcr(),
    )
    final, paths, exit_code = pipeline.run(str(pdf_path), tmp_path / "out")
    assert exit_code == 0
    assert final.summary.final_project_count == 1
    assert paths["json"].exists()
    assert paths["min_json"].exists()
    assert paths["xlsx"].exists()
    assert final.projects[0].source_pages


def test_failed_chunk_continues_and_nonzero_exit(tmp_path: Path):
    pdf_path = tmp_path / "budget.pdf"
    _make_pdf(pdf_path, pages=5)

    good = {
        "chunk_metadata": {"chunk_id": "chunk_0001", "start_page": 1, "end_page": 3},
        "projects": [
            {
                "project_name": "Signal Upgrade",
                "current_phase": "funding_approved",
                "pre_rfp_status": "possible_pre_rfp",
                "source_pages": [1],
                "evidence": [{"page": 1, "quote": "Signal Upgrade funded"}],
                "confidence_score": 0.8,
                "first_seen_chunk": "chunk_0001",
            }
        ],
        "chunk_validation_issues": [],
    }

    class FlakyGlm(FakeGlm):
        def complete_json(self, messages, **kwargs):
            self.calls += 1
            self.api_requests += 1
            # First chunk ok, later calls fail via invalid JSON that also fails repair.
            if self.calls == 1:
                content = json.dumps(good)
            else:
                content = "{not-json"
            return GlmCompletionResult(
                content=content,
                request_id=f"req-{self.calls}",
                finish_reason="stop",
                prompt_tokens=5,
                completion_tokens=5,
                total_tokens=10,
                raw_response={},
                truncated=False,
            )

    config = AppConfig(
        api_key="test-key",
        chunk_pages=3,
        overlap_pages=1,
        ocr_mode="never",
        scout_mode="never",
        prompts_dir=Path(__file__).resolve().parents[1] / "prompts",
        max_api_retries=1,
    )
    logger = create_app_logger("ERROR")
    pipeline = ExtractionPipeline(
        config,
        logger,
        glm_client=FlakyGlm([]),
        ocr_client=FakeOcr(),
    )
    final, paths, exit_code = pipeline.run(str(pdf_path), tmp_path / "out2")
    assert exit_code == 2
    assert final.summary.final_project_count >= 1
    assert paths["json"].exists()
