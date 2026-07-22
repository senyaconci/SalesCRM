"""Z.AI GLM-OCR layout parsing client with caching and chunk limits."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from budget_extractor.checkpoint import CheckpointStore
from budget_extractor.config import AppConfig
from budget_extractor.pdf_processor import PageTextInfo, split_pdf_pages
from budget_extractor.utils import atomic_write_json, ensure_dir, read_json, sha256_file

LOGGER = logging.getLogger(__name__)

# Conservative OCR PDF size limit before further subdivision.
MAX_OCR_FILE_BYTES = 8 * 1024 * 1024


@dataclass
class OcrChunkResult:
    page_texts: dict[int, str]
    failed_pages: list[int]
    request_ids: list[str]
    raw_responses: list[dict[str, Any]]


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    message = str(exc).lower()
    return "rate limit" in message or "timeout" in message or "temporarily" in message


class OcrClient:
    """Calls Z.AI `/layout_parsing` for low-text or forced OCR pages."""

    def __init__(self, config: AppConfig, checkpoint: CheckpointStore | None = None):
        self.config = config
        self.checkpoint = checkpoint
        self._client: Any | None = None
        self.api_requests = 0
        self.api_retries = 0

    def _get_sdk_client(self) -> Any:
        if self._client is None:
            from zai import ZaiClient

            self._client = ZaiClient(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.request_timeout_seconds,
                max_retries=0,
            )
        return self._client

    def select_ocr_pages(
        self,
        pages: list[PageTextInfo],
        *,
        mode: str,
    ) -> list[int]:
        if mode == "never":
            return []
        if mode == "always":
            return [page.page_number for page in pages]
        return [page.page_number for page in pages if page.needs_ocr]

    def run_ocr(
        self,
        *,
        source_pdf: str | Path,
        page_numbers: list[int],
        ocr_dir: str | Path,
    ) -> OcrChunkResult:
        if not page_numbers:
            return OcrChunkResult({}, [], [], [])

        ocr_dir = ensure_dir(ocr_dir)
        page_texts: dict[int, str] = {}
        failed_pages: list[int] = []
        request_ids: list[str] = []
        raw_responses: list[dict[str, Any]] = []

        for chunk_pages in _batched(page_numbers, self.config.ocr_chunk_pages):
            for sub_pages in self._subdivide_for_limits(source_pdf, chunk_pages, ocr_dir):
                cache_key = f"{sha256_file(source_pdf)}:{sub_pages[0]}-{sub_pages[-1]}"
                cached_path = self.checkpoint.get_ocr_cache(cache_key) if self.checkpoint else None
                if cached_path and cached_path.exists():
                    payload = read_json(cached_path)
                    page_texts.update({int(k): v for k, v in payload.get("page_texts", {}).items()})
                    request_ids.extend(payload.get("request_ids", []))
                    continue

                try:
                    result = self._ocr_page_group(source_pdf, sub_pages, ocr_dir)
                    page_texts.update(result["page_texts"])
                    request_ids.extend(result.get("request_ids", []))
                    raw_responses.append(result.get("raw", {}))
                    cache_path = ocr_dir / f"ocr_{sub_pages[0]:04d}_{sub_pages[-1]:04d}.json"
                    atomic_write_json(cache_path, result)
                    if self.checkpoint:
                        self.checkpoint.set_ocr_cache(cache_key, cache_path)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning(
                        "OCR failed for pages %s-%s: %s",
                        sub_pages[0],
                        sub_pages[-1],
                        exc,
                    )
                    failed_pages.extend(sub_pages)

        return OcrChunkResult(
            page_texts=page_texts,
            failed_pages=sorted(set(failed_pages)),
            request_ids=request_ids,
            raw_responses=raw_responses,
        )

    def _subdivide_for_limits(
        self,
        source_pdf: str | Path,
        page_numbers: list[int],
        ocr_dir: Path,
    ) -> list[list[int]]:
        if not page_numbers:
            return []
        temp_path = ocr_dir / f"_probe_{page_numbers[0]}_{page_numbers[-1]}.pdf"
        split_pdf_pages(source_pdf, page_numbers, temp_path)
        size = temp_path.stat().st_size
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

        if len(page_numbers) == 1 or (
            len(page_numbers) <= self.config.ocr_chunk_pages and size <= MAX_OCR_FILE_BYTES
        ):
            return [page_numbers]

        mid = max(1, len(page_numbers) // 2)
        left = self._subdivide_for_limits(source_pdf, page_numbers[:mid], ocr_dir)
        right = self._subdivide_for_limits(source_pdf, page_numbers[mid:], ocr_dir)
        return left + right

    def _ocr_page_group(
        self,
        source_pdf: str | Path,
        page_numbers: list[int],
        ocr_dir: Path,
    ) -> dict[str, Any]:
        chunk_pdf = ocr_dir / f"chunk_{page_numbers[0]:04d}_{page_numbers[-1]:04d}.pdf"
        split_pdf_pages(source_pdf, page_numbers, chunk_pdf)
        file_b64 = base64.b64encode(chunk_pdf.read_bytes()).decode("ascii")
        file_payload = f"data:application/pdf;base64,{file_b64}"

        response = self._call_layout_parsing(file_payload)
        md_results = _extract_md_results(response)
        page_texts = _split_ocr_markdown_to_pages(md_results, page_numbers)
        raw = _to_plain_dict(response)
        request_id = raw.get("request_id") or raw.get("id")
        return {
            "page_texts": {str(k): v for k, v in page_texts.items()},
            "request_ids": [request_id] if request_id else [],
            "raw": raw,
            "original_pages": page_numbers,
        }

    def _call_layout_parsing(self, file_payload: str) -> Any:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self.config.max_api_retries),
            wait=wait_exponential_jitter(initial=2, max=60),
            retry=retry_if_exception(_is_retryable),
            before_sleep=lambda rs: setattr(self, "api_retries", self.api_retries + 1),
        )
        def _invoke() -> Any:
            self.api_requests += 1
            # Prefer official SDK when available.
            try:
                client = self._get_sdk_client()
                return client.layout_parsing.create(
                    model="glm-ocr",
                    file=file_payload,
                    return_crop_images=False,
                    need_layout_visualization=False,
                )
            except Exception as sdk_exc:  # noqa: BLE001
                LOGGER.debug("SDK layout_parsing failed, falling back to HTTP: %s", sdk_exc)
                return self._http_layout_parsing(file_payload)

        return _invoke()

    def _http_layout_parsing(self, file_payload: str) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/layout_parsing"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "glm-ocr",
            "file": file_payload,
            "return_crop_images": False,
            "need_layout_visualization": False,
        }
        with httpx.Client(timeout=self.config.request_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code in {401, 403}:
                raise PermissionError("OCR authentication failed; check ZAI_API_KEY")
            response.raise_for_status()
            return response.json()


def _batched(items: list[int], size: int) -> list[list[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _extract_md_results(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("md_results") or "")
    return str(getattr(response, "md_results", "") or "")


def _to_plain_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    return {"repr": repr(response)}


def _split_ocr_markdown_to_pages(md_results: str, page_numbers: list[int]) -> dict[int, str]:
    """Map OCR markdown back onto original PDF page numbers.

    GLM-OCR may return a single markdown blob or page-delimited content.
    When explicit page breaks are absent, assign the full text to each page
    group proportionally by splitting on form-feed / horizontal rules.
    """
    text = (md_results or "").strip()
    if not text:
        return {page: "" for page in page_numbers}

    # Common separators used by layout parsers.
    parts = re_split_pages(text)
    if len(parts) == len(page_numbers):
        return {page: part.strip() for page, part in zip(page_numbers, parts)}

    if len(parts) == 1:
        # Best-effort: attach full OCR text to the first page and leave notes
        # on remaining pages so provenance is not completely lost.
        mapping = {page_numbers[0]: parts[0].strip()}
        for page in page_numbers[1:]:
            mapping[page] = (
                f"[OCR text shared with page {page_numbers[0]} in this OCR chunk]\n"
                f"{parts[0].strip()}"
            )
        return mapping

    mapping: dict[int, str] = {}
    for idx, page in enumerate(page_numbers):
        mapping[page] = parts[idx].strip() if idx < len(parts) else ""
    # Append leftovers to the last page.
    if len(parts) > len(page_numbers):
        mapping[page_numbers[-1]] = (
            mapping[page_numbers[-1]] + "\n\n" + "\n\n".join(parts[len(page_numbers) :])
        ).strip()
    return mapping


def re_split_pages(text: str) -> list[str]:
    import re

    # Prefer explicit markers if present.
    if "<<<PDF_PAGE_" in text:
        chunks = re.split(r"<<<PDF_PAGE_\d+>>>", text)
        return [chunk for chunk in chunks if chunk.strip()]

    parts = re.split(r"\n\s*(?:---|\f|<!--\s*page\s*break\s*-->)\s*\n", text, flags=re.IGNORECASE)
    parts = [part for part in parts if part.strip()]
    return parts or [text]
