"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from org_intel.config import RunConfig, Settings
from org_intel.database import Database
from org_intel.llm.glm_provider import MockLLMProvider
from org_intel.llm.router import CostTracker, LLMRouter
from org_intel.retrieval.cache import ContentCache
from org_intel.retrieval.http_client import MockHttpClient
from org_intel.retrieval.robots_policy import RobotsPolicy

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    return Database(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_provider="mock",
        cache_dir=tmp_path / "cache",
        database_url=f"sqlite:///{tmp_path / 'settings.db'}",
        max_cost_usd=5.0,
        respect_robots=False,
        official_sources_only=True,
    )


@pytest.fixture
def mock_router(settings: Settings, tmp_db: Database) -> LLMRouter:
    provider = MockLLMProvider(
        responses={
            "default": "{}",
            "cheap_classifier": '{"organization_type":"city","confidence":0.9,"rationale":"City of"}',
        }
    )
    tracker = CostTracker(tmp_db, "RUN-TEST", settings.max_cost_usd)
    return LLMRouter(settings, tmp_db, tracker, provider=provider)


def load_fixture_site(name: str) -> dict[str, dict]:
    root = FIXTURES / name
    fixtures: dict[str, dict] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".csv", ".pdf", ".txt"}:
            rel = path.relative_to(root).as_posix()
            # Map to https://example test hosts declared in meta
            continue
    # Prefer explicit mapping file
    mapping = root / "urls.json"
    if mapping.exists():
        import json

        data = json.loads(mapping.read_text())
        for url, meta in data.items():
            file_path = root / meta["file"]
            content = file_path.read_bytes()
            fixtures[url] = {
                "content": content,
                "content_type": meta.get("content_type", "text/html"),
                "status_code": 200,
            }
    return fixtures


@pytest.fixture
def municipality_http(tmp_db: Database, settings: Settings) -> MockHttpClient:
    fixtures = load_fixture_site("municipality")
    cache = ContentCache(tmp_db, settings.cache_dir)
    return MockHttpClient(fixtures, cache, settings.user_agent)


@pytest.fixture
def water_http(tmp_db: Database, settings: Settings) -> MockHttpClient:
    fixtures = load_fixture_site("water_district")
    cache = ContentCache(tmp_db, settings.cache_dir)
    return MockHttpClient(fixtures, cache, settings.user_agent)


@pytest.fixture
def university_http(tmp_db: Database, settings: Settings) -> MockHttpClient:
    fixtures = load_fixture_site("university")
    cache = ContentCache(tmp_db, settings.cache_dir)
    return MockHttpClient(fixtures, cache, settings.user_agent)


@pytest.fixture
def airport_http(tmp_db: Database, settings: Settings) -> MockHttpClient:
    fixtures = load_fixture_site("airport")
    cache = ContentCache(tmp_db, settings.cache_dir)
    return MockHttpClient(fixtures, cache, settings.user_agent)
