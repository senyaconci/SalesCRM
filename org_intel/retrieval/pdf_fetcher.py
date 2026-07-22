"""PDF download helper."""

from __future__ import annotations

from org_intel.retrieval.http_client import FetchResult, HttpClient


class PdfFetcher:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def fetch(self, url: str, *, force: bool = False) -> FetchResult:
        return self.http.fetch(url, force=force, as_binary=True)
