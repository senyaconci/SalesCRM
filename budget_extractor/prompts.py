"""Prompt loading and message construction."""

from __future__ import annotations

from pathlib import Path

from budget_extractor.pdf_processor import TextChunk


def load_prompt(prompts_dir: str | Path, name: str) -> str:
    path = Path(prompts_dir) / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def build_extraction_messages(
    *,
    prompts_dir: str | Path,
    chunk: TextChunk,
    document_title: str,
    organization_hint: str | None = None,
    total_pages: int,
) -> list[dict[str, str]]:
    system_prompt = load_prompt(prompts_dir, "project_extraction.md")
    user_prompt = f"""
Extract every capital / infrastructure / facility / technology / equipment project from this budget document chunk.

Document title: {document_title}
Organization hint: {organization_hint or "unknown"}
Total document pages: {total_pages}
Chunk ID: {chunk.chunk_id}
Chunk page range: {chunk.start_page}-{chunk.end_page}

Page markers look like <<<PDF_PAGE_N>>> and use original PDF page numbers.

Return one JSON object with keys chunk_metadata, projects, chunk_validation_issues.
For each project set first_seen_chunk to "{chunk.chunk_id}".
Do not wrap the JSON in markdown fences.

CHUNK TEXT START
{chunk.text}
CHUNK TEXT END
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_repair_messages(
    *,
    prompts_dir: str | Path,
    invalid_json: str,
    validation_errors: str,
    schema_summary: str,
) -> list[dict[str, str]]:
    system_prompt = load_prompt(prompts_dir, "repair_json.md")
    user_prompt = f"""
Invalid JSON:
{invalid_json}

Validation errors:
{validation_errors}

Required schema summary:
{schema_summary}

Return corrected JSON only.
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_duplicate_resolution_messages(
    *,
    prompts_dir: str | Path,
    candidates_json: str,
) -> list[dict[str, str]]:
    system_prompt = load_prompt(prompts_dir, "duplicate_resolution.md")
    user_prompt = f"""
Candidate project records:
{candidates_json}

Return one JSON object with decision, reason, confidence, and merged_record.
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


SCHEMA_SUMMARY = """
Root object:
{
  "chunk_metadata": {"chunk_id": str, "start_page": int, "end_page": int, "notes": str},
  "projects": [ProjectRecord...],
  "chunk_validation_issues": [Issue...]
}

ProjectRecord required fields:
- project_name (non-empty string)
- current_phase (enum)
- pre_rfp_status (enum)
- source_pages (non-empty int array)
- evidence (non-empty array of {page, quote, evidence_type?})
- confidence_score (0..1)
- first_seen_chunk (string)
""".strip()
