"""Money parsing helpers."""

from __future__ import annotations

import re

_MONEY_RE = re.compile(
    r"(?P<sign>-)?\$?\s*(?P<num>[\d,]+(?:\.\d+)?)\s*(?P<suffix>[kmb])?",
    re.I,
)


def parse_money(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"n/a", "na", "-", "—", "tbd", "none"}:
        return None
    cleaned = text.replace("(", "-").replace(")", "")
    match = _MONEY_RE.search(cleaned.replace(",", ""))
    if not match:
        # try plain number with commas already removed
        try:
            return float(cleaned.replace(",", "").replace("$", ""))
        except ValueError:
            return None
    num = float(match.group("num").replace(",", ""))
    suffix = (match.group("suffix") or "").lower()
    if suffix == "k":
        num *= 1_000
    elif suffix == "m":
        num *= 1_000_000
    elif suffix == "b":
        num *= 1_000_000_000
    if match.group("sign"):
        num = -num
    return num
