"""Command-line interface for budget capital-project extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from budget_extractor.config import AppConfig, LogLevel, OcrMode, load_config
from budget_extractor.extraction import ExtractionPipeline
from budget_extractor.logging_utils import create_app_logger
from budget_extractor.utils import is_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_extractor",
        description=(
            "Extract capital/infrastructure projects from public-sector budget PDFs "
            "using the Z.AI GLM API."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Local PDF path or HTTP/HTTPS PDF URL",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for outputs, checkpoints, and intermediate files",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="GLM model name (default from GLM_MODEL / glm-5.2)",
    )
    parser.add_argument(
        "--chunk-pages",
        type=int,
        default=None,
        help="Pages per extraction chunk (default 20)",
    )
    parser.add_argument(
        "--overlap-pages",
        type=int,
        default=None,
        help="Overlap pages between chunks (default 2)",
    )
    parser.add_argument(
        "--ocr",
        choices=["auto", "always", "never"],
        default="auto",
        help="OCR mode for low-text pages",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing checkpoints when compatible",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess completed chunks and ignore prior resume state",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=None,
        help="Optional first PDF page (1-based)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=None,
        help="Optional last PDF page (1-based)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="API concurrency (default 1)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity",
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Preserve extracted text and raw model responses",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = create_app_logger(args.log_level)

    try:
        config = load_config(
            model=args.model,
            chunk_pages=args.chunk_pages,
            overlap_pages=args.overlap_pages,
            ocr_mode=args.ocr,  # type: ignore[arg-type]
            resume=args.resume,
            force=args.force,
            start_page=args.start_page,
            end_page=args.end_page,
            max_workers=args.max_workers,
            log_level=args.log_level,  # type: ignore[arg-type]
            keep_intermediate=args.keep_intermediate,
        )
        # Keep intermediates whenever explicitly requested; also keep raw responses
        # in checkpoints by default via CheckpointStore.
        if args.keep_intermediate:
            config.keep_intermediate = True
        config.validate()
    except Exception as exc:  # noqa: BLE001
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    input_value = args.input
    if not is_url(input_value):
        path = Path(input_value).expanduser()
        if not path.exists():
            print(f"Input PDF not found: {path}", file=sys.stderr)
            return 1

    logger.event(
        "INFO",
        f"Configured model={config.model} ocr={config.ocr_mode} workers={config.max_workers}",
        stage="startup",
    )
    # Never print the full API key.
    logger.logger.debug("Using API key %s", config.masked_api_key())

    try:
        pipeline = ExtractionPipeline(config, logger)
        _final, paths, exit_code = pipeline.run(input_value, args.output_dir)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.event("ERROR", f"Fatal error: {exc}", stage="fatal", status="failed")
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1

    print("Output files:")
    for label, path in paths.items():
        print(f"  - {label}: {path}")
    if exit_code != 0:
        print(
            "Completed with failed chunks; partial outputs were written.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
