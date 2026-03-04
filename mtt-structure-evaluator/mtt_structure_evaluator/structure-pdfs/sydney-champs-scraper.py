#!/opt/homebrew/bin/python3.11
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mtt_structure_evaluator.pdf_scraping import run_pdf_cli


if __name__ == "__main__":
    raise SystemExit(
        run_pdf_cli(
            default_pdf=Path(__file__).resolve().parent / "sydney-champs-structures.pdf",
            default_output=PROJECT_ROOT / "structure-scrapes" / "sydney_champs_tournaments.json",
            default_structures_dir=PROJECT_ROOT / "structure-scrapes" / "sydney_champs",
        )
    )
