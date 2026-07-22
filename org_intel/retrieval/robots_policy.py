"""Robots.txt policy helper."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from org_intel.utils.logging import get_logger

logger = get_logger(__name__)


class RobotsPolicy:
    def __init__(self, user_agent: str, enabled: bool = True) -> None:
        self.user_agent = user_agent
        self.enabled = enabled
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True
        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._get_parser(base)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _get_parser(self, base: str) -> RobotFileParser | None:
        if base in self._parsers:
            return self._parsers[base]
        robots_url = f"{base}/robots.txt"
        parser = RobotFileParser()
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(robots_url)
                if resp.status_code >= 400:
                    self._parsers[base] = None
                    return None
                parser.parse(resp.text.splitlines())
                self._parsers[base] = parser
                return parser
        except Exception as exc:
            logger.debug("robots_fetch_failed", url=robots_url, error=str(exc))
            self._parsers[base] = None
            return None
