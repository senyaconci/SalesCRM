"""JSON artifact exporters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from org_intel.utils.io import atomic_write_json, ensure_dir


def export_json_bundle(output_dir: Path, artifacts: dict[str, Any]) -> dict[str, Path]:
    ensure_dir(output_dir)
    written: dict[str, Path] = {}
    mapping = {
        "organization_profile": "organization_profile.json",
        "source_registry": "source_registry.json",
        "document_inventory": "document_inventory.json",
        "financial_capital_profile": "financial_capital_profile.json",
        "organization_relationships": "organization_relationships.json",
        "project_index": "project_index.json",
        "project_source_map": "project_source_map.json",
        "projects_full": "projects_full.json",
        "opportunities": "opportunities.json",
        "incumbent_vendor_analysis": "incumbent_vendor_analysis.json",
        "contacts": "contacts.json",
        "validation_plan": "validation_plan.json",
        "research_gaps": "research_gaps.json",
        "change_history": "change_history.json",
        "cost_ledger": "cost_ledger.json",
        "run_manifest": "run_manifest.json",
        "anchor_selection": "anchor_selection.json",
    }
    for key, filename in mapping.items():
        if key not in artifacts:
            continue
        path = output_dir / filename
        atomic_write_json(path, _serialize(artifacts[key]))
        written[key] = path
    return written


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value
