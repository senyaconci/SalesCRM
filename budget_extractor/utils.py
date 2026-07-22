"""Shared utility helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CURRENCY_PATTERN = re.compile(
    r"(?P<sign>[-+])?\s*"
    r"(?:\$|USD\s*)?\s*"
    r"(?P<number>\(?-?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\)?)"
    r"\s*(?P<suffix>[kKmMbB])?",
    re.IGNORECASE,
)


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: str | Path, data: Any, *, compact: bool = False) -> None:
    if compact:
        content = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        content += "\n"
    atomic_write_text(path, content)


def read_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_stem(path: str | Path) -> str:
    return Path(path).stem


def parse_currency(value: str | float | int | None) -> float | None:
    """Parse currency-like values into floats.

    Supports $, commas, parentheses for negatives, and k/m/b suffixes.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"n/a", "na", "none", "-", "—", "tbd"}:
        return None

    compact = text.replace(" ", "")
    accounting_negative = compact.startswith("(") and compact.endswith(")")
    if accounting_negative:
        compact = compact[1:-1]

    match = CURRENCY_PATTERN.search(compact)
    if not match:
        # Fallback: strip non-numeric noise.
        cleaned = re.sub(r"[^\d.\-]", "", compact)
        if not cleaned:
            return None
        try:
            amount = float(cleaned)
        except ValueError:
            return None
        return -abs(amount) if accounting_negative or cleaned.startswith("-") else amount

    number = match.group("number").strip("()")
    number = number.replace(",", "")
    try:
        amount = float(number)
    except ValueError:
        return None

    suffix = (match.group("suffix") or "").lower()
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    amount *= multipliers.get(suffix, 1)
    if accounting_negative or match.group("sign") == "-" or number.startswith("-"):
        amount = -abs(amount)
    return amount


def normalize_budget_string(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def flatten_list(values: list[Any] | None, sep: str = "; ") -> str:
    if not values:
        return ""
    parts = [str(v).strip() for v in values if v is not None and str(v).strip()]
    return sep.join(parts)


def pages_to_range_label(start: int, end: int) -> str:
    return f"{start}-{end}"


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", name.strip())
    return cleaned[:180] or "document"


def chunk_id_for_index(index: int) -> str:
    return f"chunk_{index:04d}"


def redact_secrets(text: str, api_key: str | None = None) -> str:
    if not text:
        return text
    redacted = text
    if api_key:
        redacted = redacted.replace(api_key, "***REDACTED***")
    redacted = re.sub(
        r"(Authorization:\s*Bearer\s+)(\S+)",
        r"\1***REDACTED***",
        redacted,
        flags=re.IGNORECASE,
    )
    return redacted
