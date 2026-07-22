"""JSON repair helpers for LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def loads_json(text: str, default: Any = None) -> Any:
    try:
        return json.loads(extract_json_object(text))
    except json.JSONDecodeError:
        repaired = _simple_repair(text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return default


def _simple_repair(text: str) -> str:
    candidate = extract_json_object(text)
    candidate = candidate.replace("\r", "")
    candidate = re.sub(r",\s*}", "}", candidate)
    candidate = re.sub(r",\s*]", "]", candidate)
    candidate = re.sub(r"\bNone\b", "null", candidate)
    candidate = re.sub(r"\bTrue\b", "true", candidate)
    candidate = re.sub(r"\bFalse\b", "false", candidate)
    return candidate
