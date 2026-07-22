"""Allow `python -m budget_extractor`."""

from __future__ import annotations

from budget_extractor.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
