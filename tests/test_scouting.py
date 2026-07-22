from __future__ import annotations

import json
from pathlib import Path

from budget_extractor.checkpoint import CheckpointStore
from budget_extractor.config import AppConfig
from budget_extractor.costing import CostTracker
from budget_extractor.glm_client import GlmCompletionResult
from budget_extractor.logging_utils import create_app_logger
from budget_extractor.pdf_processor import analyze_page_text
from budget_extractor.scouting import (
    ProjectScout,
    build_selected_extraction_chunks,
    detect_signal_pages,
    expand_candidate_pages,
)


class FakeScoutClient:
    def __init__(self, responses: list[dict] | None = None, error: Exception | None = None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = 0
        self.api_requests = 0
        self.api_retries = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def complete_json(self, messages, **kwargs):
        self.calls += 1
        self.api_requests += 1
        if self.error is not None:
            raise self.error
        payload = self.responses.pop(0)
        self.prompt_tokens += 100
        self.completion_tokens += 20
        self.total_tokens += 120
        return GlmCompletionResult(
            content=json.dumps(payload),
            request_id=f"scout-{self.calls}",
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            raw_response={},
        )


def _pages(count: int, text: str = "Administrative overview and staffing.") -> list:
    return [analyze_page_text(index, text) for index in range(1, count + 1)]


def _config(tmp_path: Path, **overrides) -> AppConfig:
    values = {
        "api_key": "test-key",
        "scout_mode": "auto",
        "scout_model": "glm-4.7-flash",
        "scout_chunk_pages": 4,
        "scout_overlap_pages": 1,
        "scout_context_pages": 1,
        "prompts_dir": Path(__file__).resolve().parents[1] / "prompts",
    }
    values.update(overrides)
    return AppConfig(**values)


def test_deterministic_signal_pages_are_conservative():
    pages = [
        analyze_page_text(1, "Personnel salaries and employee benefits."),
        analyze_page_text(
            2,
            "Project Details\nProject Description: Replace the roof.\n"
            "Project Funding Information\nActual Budget: $400,000",
        ),
    ]
    assert detect_signal_pages(pages) == {2}


def test_expand_candidate_pages_adds_context_only_when_available():
    assert expand_candidate_pages(
        {5},
        available_pages=[3, 4, 5, 6, 7],
        context_pages=2,
    ) == [3, 4, 5, 6, 7]


def test_selected_extraction_chunks_do_not_bridge_filtered_gaps():
    pages = _pages(10)
    chunks = build_selected_extraction_chunks(
        pages,
        selected_pages=[1, 2, 8, 9],
        chunk_size=20,
        overlap=2,
    )
    assert len(chunks) == 2
    assert chunks[0].page_numbers == [1, 2]
    assert chunks[1].page_numbers == [8, 9]
    assert chunks[0].chunk_id == "chunk_0001"
    assert chunks[1].chunk_id == "chunk_0002"


def test_second_pass_audits_negative_window_and_cache_resumes(tmp_path: Path):
    config = _config(tmp_path, resume=False)
    store = CheckpointStore(tmp_path / "out")
    store.load_or_create(
        document_hash="doc",
        configuration_hash=config.configuration_hash(),
        resume=False,
        force=False,
    )
    client = FakeScoutClient(
        [
            {
                "chunk_id": "scout_primary_0001",
                "candidate_pages": [],
                "uncertain_pages": [],
                "continuation_pages": [],
                "candidates": [],
            },
            {
                "chunk_id": "scout_audit_0001",
                "candidate_pages": [4],
                "uncertain_pages": [],
                "continuation_pages": [],
                "candidates": [
                    {
                        "project_name": "Server Replacement",
                        "pages": [4],
                        "signals": ["equipment"],
                        "confidence": 0.8,
                    }
                ],
            },
        ]
    )
    scout = ProjectScout(
        config,
        store,
        create_app_logger("ERROR"),
        cost_tracker=CostTracker(),
        client=client,  # type: ignore[arg-type]
    )
    result = scout.run(_pages(4), document_hash="doc")
    assert result.primary_windows == 1
    assert result.audit_windows == 1
    assert result.candidate_pages == [4]
    assert result.selected_pages == [3, 4]
    assert result.filtered_pages == [1, 2]
    assert client.calls == 2

    config.resume = True
    cached_scout = ProjectScout(
        config,
        store,
        create_app_logger("ERROR"),
        cost_tracker=CostTracker(),
        client=client,  # type: ignore[arg-type]
    )
    cached = cached_scout.run(_pages(4), document_hash="doc")
    assert cached.cache_used is True
    assert client.calls == 2


def test_scout_failure_routes_all_window_pages_fail_open(tmp_path: Path):
    config = _config(tmp_path)
    store = CheckpointStore(tmp_path / "out")
    store.load_or_create(
        document_hash="doc",
        configuration_hash=config.configuration_hash(),
        resume=False,
        force=False,
    )
    client = FakeScoutClient(error=RuntimeError("model unavailable"))
    scout = ProjectScout(
        config,
        store,
        create_app_logger("ERROR"),
        cost_tracker=CostTracker(),
        client=client,  # type: ignore[arg-type]
    )
    result = scout.run(_pages(4), document_hash="doc")
    assert result.fail_open is True
    assert result.selected_pages == [1, 2, 3, 4]
    assert result.filtered_pages == []
