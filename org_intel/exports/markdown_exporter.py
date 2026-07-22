"""Markdown organization intelligence report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from org_intel.exports.account_profile import synthesize_account_profile
from org_intel.llm.router import LLMRouter
from org_intel.utils.io import atomic_write_text, ensure_dir


def export_markdown_report(
    output_dir: Path,
    artifacts: dict[str, Any],
    router: LLMRouter | None = None,
) -> Path:
    """Export an Account Intelligence Profile markdown report."""
    ensure_dir(output_dir)
    content = synthesize_account_profile(artifacts, router=router)
    path = output_dir / "organization_intelligence.md"
    atomic_write_text(path, content)
    return path