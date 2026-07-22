"""Playwright fetcher for JavaScript-rendered public pages.

Playwright is optional at runtime; callers should fall back to static HTML
when Playwright is unavailable or unnecessary.
"""

from __future__ import annotations

from dataclasses import dataclass

from org_intel.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PlaywrightResult:
    url: str
    final_url: str
    html: str
    status_code: int = 200


class PlaywrightFetcher:
    def __init__(self, user_agent: str, timeout_ms: int = 45000) -> None:
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401

            self._available = True
        except Exception:
            self._available = False
        return self._available

    def fetch(self, url: str) -> PlaywrightResult:
        if not self.is_available():
            raise RuntimeError("Playwright is not installed or unavailable.")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
            html = page.content()
            final_url = page.url
            status = response.status if response else 200
            browser.close()
            return PlaywrightResult(
                url=url,
                final_url=final_url,
                html=html,
                status_code=status,
            )
