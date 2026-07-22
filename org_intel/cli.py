"""Command-line interface for Organization Capital Intelligence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from org_intel.config import RunConfig, Settings
from org_intel.pipeline.orchestrator import PipelineOrchestrator
from org_intel.utils.logging import configure_logging, get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="org_intel",
        description="Organization Capital Intelligence — evidence-backed capital project mapping",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an organization intelligence pipeline")
    run.add_argument("--org-url", required=True, help="Official organization URL")
    run.add_argument("--org-name", default=None, help="Optional canonical name hint")
    run.add_argument("--org-type", default=None, help="Optional organization type hint")
    run.add_argument("--output-dir", required=True, help="Output directory")
    run.add_argument(
        "--mode",
        choices=["discover", "project-map", "full", "refresh", "deep-enrich"],
        default="full",
    )
    run.add_argument("--resume", action="store_true", help="Resume from checkpoints")
    run.add_argument("--force", action="store_true", help="Force recompute all phases")
    run.add_argument("--max-cost-usd", type=float, default=None)
    run.add_argument("--max-documents", type=int, default=None)
    run.add_argument("--max-pages", type=int, default=None)
    run.add_argument("--max-searches", type=int, default=None)
    run.add_argument("--max-workers", type=int, default=None)
    run.add_argument("--official-sources-only", action=argparse.BooleanOptionalAction, default=None)
    run.add_argument(
        "--include-third-party-sources",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run.add_argument("--project-id", action="append", default=[])
    run.add_argument("--project-category", action="append", default=[])
    run.add_argument("--min-project-value", type=float, default=None)
    run.add_argument("--include-completed", action="store_true")
    run.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None)
    run.add_argument("--keep-intermediate", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help()
        return 2

    settings = Settings()
    run = RunConfig(
        org_url=args.org_url,
        org_name=args.org_name,
        org_type=args.org_type,
        output_dir=Path(args.output_dir),
        mode=args.mode,
        resume=args.resume,
        force=args.force,
        max_cost_usd=args.max_cost_usd,
        max_documents=args.max_documents,
        max_pages=args.max_pages,
        max_searches=args.max_searches,
        max_workers=args.max_workers,
        official_sources_only=args.official_sources_only,
        include_third_party_sources=args.include_third_party_sources,
        project_id=args.project_id or [],
        project_category=args.project_category or [],
        min_project_value=args.min_project_value,
        include_completed=args.include_completed,
        log_level=args.log_level,
        keep_intermediate=args.keep_intermediate,
    )
    configure_logging(run.log_level or settings.log_level)
    log = get_logger("cli")
    log.info("starting", mode=run.mode, org_url=run.org_url, output_dir=str(run.output_dir))

    orchestrator = PipelineOrchestrator(settings, run)
    try:
        artifacts = orchestrator.run_pipeline()
    except Exception as exc:
        log.error("run_failed", error=str(exc))
        return 1

    log.info(
        "run_finished",
        output_dir=str(run.output_dir),
        projects=len(artifacts.get("projects_full") or []),
        opportunities=len(artifacts.get("opportunities") or []),
        partial=orchestrator.partial,
    )
    print(f"Outputs written to {run.output_dir}")
    print(f"  - organization_intelligence.md")
    print(f"  - capital_projects.xlsx")
    print(f"  - *.json artifacts")
    if orchestrator.partial:
        print(f"Partial run: {orchestrator.stop_reason}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
