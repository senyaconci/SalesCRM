"""Text helpers."""

from __future__ import annotations

import re
import unicodedata


_WS_RE = re.compile(r"\s+")


def clean_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def excerpt(text: str | None, max_len: int = 280) -> str:
    cleaned = clean_whitespace(text)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def slugify(text: str) -> str:
    value = unicodedata.normalize("NFKD", text)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "item"
