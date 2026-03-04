#!/opt/homebrew/bin/python3.11
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mtt_structure_evaluator.scraping import SiteConfig, run_site_cli

CONFIG = SiteConfig(
    site_name="kingsroom",
    listing_urls=("https://kingsroom.com.au/live/",),
    link_selectors=(
        "a.cw-title",
        "a[href*='?id=']",
        "a[href*='kingsroom.com.au/live/']",
        "a[href*='clockw']",
    ),
)


if __name__ == "__main__":
    raise SystemExit(
        run_site_cli(
            config=CONFIG,
            default_output=PROJECT_ROOT / "structure-scrapes" / "kingsroom_tournaments.json",
            default_structures_dir=PROJECT_ROOT / "structure-scrapes" / "kingsroom",
        )
    )
