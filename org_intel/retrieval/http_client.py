"""HTTP client with retries, caching, and robots awareness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from org_intel.retrieval.cache import ContentCache
from org_intel.retrieval.robots_policy import RobotsPolicy
from org_intel.utils.logging import get_logger
from org_intel.utils.urls import normalize_url

logger = get_logger(__name__)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content: bytes
    text: str
    content_type: str | None
    from_cache: bool
    sha256: str | None = None
    local_path: str | None = None
    headers: dict[str, str] | None = None


class HttpClient:
    def __init__(
        self,
        cache: ContentCache,
        user_agent: str,
        timeout: float = 45.0,
        robots: RobotsPolicy | None = None,
    ) -> None:
        self.cache = cache
        self.user_agent = user_agent
        self.timeout = timeout
        self.robots = robots or RobotsPolicy(user_agent, enabled=True)
        self._search_count = 0

    @property
    def search_count(self) -> int:
        return self._search_count

    def fetch(
        self,
        url: str,
        *,
        use_cache: bool = True,
        force: bool = False,
        as_binary: bool = False,
    ) -> FetchResult:
        norm = normalize_url(url)
        if not self.robots.allowed(norm):
            raise PermissionError(f"Blocked by robots.txt: {norm}")

        if use_cache and not force:
            cached = self.cache.get(norm)
            if cached:
                path = cached.local_path
                content = open(path, "rb").read()
                text = "" if as_binary else _safe_decode(content)
                return FetchResult(
                    url=norm,
                    final_url=norm,
                    status_code=200,
                    content=content,
                    text=text,
                    content_type=cached.content_type,
                    from_cache=True,
                    sha256=cached.sha256,
                    local_path=cached.local_path,
                )

        response = self._get(norm)
        content = response.content
        content_type = response.headers.get("content-type")
        row = self.cache.put(
            norm,
            content,
            content_type=content_type,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
        text = "" if as_binary else _safe_decode(content)
        return FetchResult(
            url=norm,
            final_url=str(response.url),
            status_code=response.status_code,
            content=content,
            text=text,
            content_type=content_type,
            from_cache=False,
            sha256=row.sha256,
            local_path=row.local_path,
            headers=dict(response.headers),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _get(self, url: str) -> httpx.Response:
        headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response


def _safe_decode(content: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


class MockHttpClient(HttpClient):
    """Fixture-backed HTTP client for tests."""

    def __init__(self, fixtures: dict[str, dict[str, Any]], cache: ContentCache, user_agent: str):
        super().__init__(cache=cache, user_agent=user_agent, robots=RobotsPolicy(user_agent, enabled=False))
        self.fixtures = {normalize_url(k): v for k, v in fixtures.items()}

    def fetch(
        self,
        url: str,
        *,
        use_cache: bool = True,
        force: bool = False,
        as_binary: bool = False,
    ) -> FetchResult:
        norm = normalize_url(url)
        if use_cache and not force:
            cached = self.cache.get(norm)
            if cached:
                content = open(cached.local_path, "rb").read()
                return FetchResult(
                    url=norm,
                    final_url=norm,
                    status_code=200,
                    content=content,
                    text="" if as_binary else _safe_decode(content),
                    content_type=cached.content_type,
                    from_cache=True,
                    sha256=cached.sha256,
                    local_path=cached.local_path,
                )
        if norm not in self.fixtures:
            # try without normalize differences
            for key, value in self.fixtures.items():
                if key.rstrip("/") == norm.rstrip("/"):
                    norm = key
                    break
            else:
                raise httpx.HTTPStatusError(
                    f"No fixture for {norm}",
                    request=httpx.Request("GET", norm),
                    response=httpx.Response(404, request=httpx.Request("GET", norm)),
                )
        fixture = self.fixtures[norm]
        content = fixture.get("content")
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content or b""
        content_type = fixture.get("content_type", "text/html")
        row = self.cache.put(norm, content_bytes, content_type=content_type)
        return FetchResult(
            url=norm,
            final_url=fixture.get("final_url", norm),
            status_code=int(fixture.get("status_code", 200)),
            content=content_bytes,
            text="" if as_binary else _safe_decode(content_bytes),
            content_type=content_type,
            from_cache=False,
            sha256=row.sha256,
            local_path=row.local_path,
        )
