"""JSON export helpers with atomic writes."""

from __future__ import annotations

from pathlib import Path

from budget_extractor.schemas import FinalExtractionOutput
from budget_extractor.utils import atomic_write_json, document_stem, ensure_dir


def export_json_outputs(
    output: FinalExtractionOutput,
    output_dir: str | Path,
    *,
    source_filename: str,
) -> dict[str, Path]:
    output_dir = ensure_dir(output_dir)
    stem = document_stem(source_filename)
    pretty_path = output_dir / f"{stem}_capital_projects.json"
    compact_path = output_dir / f"{stem}_capital_projects.min.json"

    payload = output.model_dump(mode="json")
    atomic_write_json(pretty_path, payload, compact=False)
    atomic_write_json(compact_path, payload, compact=True)
    return {"json": pretty_path, "min_json": compact_path}
