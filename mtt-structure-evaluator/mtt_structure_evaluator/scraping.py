from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse

from .s_points import CalculationResult, calculate_s_points

DEFAULT_LINK_SELECTORS = (
    "a.cw-title",
    "a[href*='/live/']",
    "a[href*='clockw']",
)
DEFAULT_LEVEL_TABLE_SELECTORS = (
    "table.cw-table-levels",
    "table[id*='cw'][class*='level']",
    "table[class*='level']",
)

_NON_NUMERIC_PATTERN = re.compile(r"[^0-9-]")
_FLIGHT_PATTERN = re.compile(
    r"(?:\b(?:flight|day)\s*\d+\s*[A-Z]\b|\bflight\s*[A-Z]\b)",
    re.IGNORECASE,
)
_EVENT_MERGE_PATTERN = re.compile(
    r"(?:"
    r"\b(?:flight|day)\s*\d+\s*[A-Z]\b"
    r"|\bflight\s*[A-Z]\b"
    r"|\s*-?\s*\bday\s*\d+\b"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SiteConfig:
    site_name: str
    listing_urls: tuple[str, ...]
    link_selectors: tuple[str, ...] = DEFAULT_LINK_SELECTORS
    level_table_selectors: tuple[str, ...] = DEFAULT_LEVEL_TABLE_SELECTORS
    table_row_selector: str = "tbody tr"


@dataclass(frozen=True)
class LevelEntry:
    level: int
    sb: int
    bb: int
    bba: int
    orbit_cost: int


@dataclass
class TournamentScrapeResult:
    source: str
    name: str
    url: str
    buyin: str | None
    starting_stack: int | None
    level_length_minutes: int | None
    levels: list[LevelEntry]
    s_points: float | None
    affordable_levels_count: int | None
    starting_stack_minutes: int | None
    denominator: float | None
    reference_orbit_costs: dict[int, int | None] | None
    calculation_error: str | None
    scrape_error: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.s_points is not None:
            payload["s_points"] = round(self.s_points, 2)
        return payload


def _require_selenium() -> tuple[Any, Any, Any, Any]:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError(
            "Selenium is required for scraping. Install it with: pip install '.[scraping]'"
        ) from exc
    return webdriver, Options, By, WebDriverWait


def _parse_int(text: str | None) -> int | None:
    if text is None:
        return None
    cleaned = _NON_NUMERIC_PATTERN.sub("", text)
    if cleaned in {"", "-"}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _parse_blind(text: str | None) -> int:
    value = _parse_int(text)
    if value is None:
        return 0
    return max(value, 0)


def _first_non_empty_text(driver: Any, selectors: list[tuple[str, str]]) -> str | None:
    for lookup, selector in selectors:
        elements = driver.find_elements(lookup, selector)
        for element in elements:
            text = (element.text or element.get_attribute("textContent") or "").strip()
            if text:
                return text
    return None


def _find_level_table(driver: Any, by: Any, selectors: tuple[str, ...]) -> Any | None:
    for selector in selectors:
        tables = driver.find_elements(by.CSS_SELECTOR, selector)
        if tables:
            return tables[0]
    return None


def _extract_levels(driver: Any, by: Any, config: SiteConfig) -> tuple[list[LevelEntry], int | None]:
    table = _find_level_table(driver, by, config.level_table_selectors)
    if table is None:
        return [], None

    rows = table.find_elements(by.CSS_SELECTOR, config.table_row_selector)
    if not rows:
        rows = table.find_elements(by.CSS_SELECTOR, "tr")

    levels: list[LevelEntry] = []
    level_length_minutes: int | None = None
    prev_raw_level = 0
    day_offset = 0

    for row in rows:
        cols = row.find_elements(by.CSS_SELECTOR, "td")
        if len(cols) < 4:
            continue

        raw_level = _parse_int(cols[0].text)
        if raw_level is None or raw_level < 1:
            continue

        if raw_level <= prev_raw_level:
            day_offset = prev_raw_level + day_offset

        effective_level = raw_level + day_offset
        prev_raw_level = raw_level

        sb = _parse_blind(cols[1].text)
        bb = _parse_blind(cols[2].text)
        bba = _parse_blind(cols[3].text)
        orbit_cost = sb + bb + bba

        if level_length_minutes is None and len(cols) >= 5:
            maybe_minutes = _parse_int(cols[4].text.replace("'", "").strip())
            if maybe_minutes is not None and maybe_minutes > 0:
                level_length_minutes = maybe_minutes

        levels.append(
            LevelEntry(
                level=effective_level,
                sb=sb,
                bb=bb,
                bba=bba,
                orbit_cost=orbit_cost,
            )
        )

    seen: dict[int, int] = {}
    deduped: list[LevelEntry] = []
    for entry in levels:
        if entry.level not in seen:
            seen[entry.level] = len(deduped)
            deduped.append(entry)
        else:
            deduped[seen[entry.level]] = entry

    return deduped, level_length_minutes


def _is_probable_tournament_url(config: SiteConfig, href: str) -> bool:
    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"}:
        return False

    listing_urls = {url.rstrip("/") for url in config.listing_urls}
    if href.rstrip("/") in listing_urls:
        return False

    listing_hosts = {urlparse(url).netloc for url in config.listing_urls if urlparse(url).netloc}
    if listing_hosts and parsed.netloc not in listing_hosts:
        return False

    lower_href = href.lower()
    lower_path = parsed.path.lower()
    if "/live/" in lower_path or "clock" in lower_href:
        return True
    if parsed.query and "id=" in parsed.query:
        return True
    return False


def _collect_tournament_links(
    driver: Any, wait: Any, by: Any, config: SiteConfig
) -> list[tuple[str, str]]:
    seen_by_url: dict[str, str] = {}

    for listing_url in config.listing_urls:
        driver.get(listing_url)
        wait.until(lambda d: d.find_elements(by.TAG_NAME, "body"))

        for selector in config.link_selectors:
            elements = driver.find_elements(by.CSS_SELECTOR, selector)
            for element in elements:
                href = (element.get_attribute("href") or "").strip()
                if (
                    not href
                    or href in seen_by_url
                    or not _is_probable_tournament_url(config, href)
                ):
                    continue

                name = (
                    element.text
                    or element.get_attribute("title")
                    or element.get_attribute("aria-label")
                    or ""
                ).strip()
                if not name:
                    name = Path(href.rstrip("/")).name.replace("-", " ").strip() or href

                seen_by_url[href] = name

        if seen_by_url:
            break

    deduped: dict[str, tuple[str, str]] = {}
    for url, name in seen_by_url.items():
        canonical = _FLIGHT_PATTERN.sub("", name).strip()
        canonical = re.sub(r"\s{2,}", " ", canonical)
        if canonical not in deduped:
            deduped[canonical] = (name, url)

    return list(deduped.values())


def _build_calc_payload(result: CalculationResult | None) -> tuple[
    float | None, int | None, int | None, float | None, dict[int, int | None] | None, str | None
]:
    if result is None:
        return None, None, None, None, None, None

    return (
        result.s_points,
        result.affordable_levels_count,
        result.starting_stack_minutes,
        result.denominator,
        result.orbit_costs_reference,
        result.error,
    )


def _scrape_tournament_page(
    driver: Any, wait: Any, by: Any, config: SiteConfig, name: str, url: str
) -> TournamentScrapeResult:
    driver.get(url)
    wait.until(lambda d: d.find_elements(by.TAG_NAME, "body"))

    starting_stack_text = _first_non_empty_text(
        driver,
        [
            (by.ID, "cw_clock_startchips"),
            (by.ID, "cw_clock_startingstack"),
            (by.CSS_SELECTOR, "[id*='start'][id*='chip']"),
        ],
    )
    starting_stack = _parse_int(starting_stack_text)

    buyin = _first_non_empty_text(
        driver,
        [
            (by.ID, "cw_clock_buyin"),
            (by.CSS_SELECTOR, "[id*='buyin']"),
        ],
    )

    level_length_text = _first_non_empty_text(
        driver,
        [
            (by.ID, "cw_clock_leveltime"),
            (by.ID, "cw_clock_levelduration"),
            (by.CSS_SELECTOR, "[id*='level'][id*='time']"),
        ],
    )
    level_length_minutes = _parse_int(level_length_text)

    levels, level_length_from_table = _extract_levels(driver, by, config)
    if level_length_minutes is None:
        level_length_minutes = level_length_from_table

    scrape_issues: list[str] = []
    if starting_stack is None:
        scrape_issues.append("starting_stack not found")
    if level_length_minutes is None:
        scrape_issues.append("level_length_minutes not found")
    if not levels:
        scrape_issues.append("No level rows parsed")

    calc_result: CalculationResult | None = None
    if starting_stack is not None and level_length_minutes is not None and levels:
        orbit_costs = {level.level: level.orbit_cost for level in levels}
        calc_result = calculate_s_points(
            starting_stack=starting_stack,
            level_length=level_length_minutes,
            orbit_costs=orbit_costs,
        )

    (
        s_points,
        affordable_levels_count,
        starting_stack_minutes,
        denominator,
        reference_orbit_costs,
        calculation_error,
    ) = _build_calc_payload(calc_result)

    if calc_result is None:
        calculation_error = (
            "Cannot calculate S-Points without starting_stack, level_length_minutes, and levels"
        )

    scrape_error = "; ".join(scrape_issues) if scrape_issues else None
    return TournamentScrapeResult(
        source=config.site_name,
        name=name,
        url=url,
        buyin=buyin,
        starting_stack=starting_stack,
        level_length_minutes=level_length_minutes,
        levels=levels,
        s_points=s_points,
        affordable_levels_count=affordable_levels_count,
        starting_stack_minutes=starting_stack_minutes,
        denominator=denominator,
        reference_orbit_costs=reference_orbit_costs,
        calculation_error=calculation_error,
        scrape_error=scrape_error,
    )


def _event_base_name(name: str) -> str:
    base = _EVENT_MERGE_PATTERN.sub("", name).strip()
    base = re.sub(r"\s{2,}", " ", base)
    base = base.rstrip(" -:")
    return base


def _merge_multi_day_tournaments(
    tournaments: list[TournamentScrapeResult],
) -> list[TournamentScrapeResult]:
    groups: dict[str, list[TournamentScrapeResult]] = {}
    group_order: list[str] = []
    for t in tournaments:
        base = _event_base_name(t.name)
        if base not in groups:
            groups[base] = []
            group_order.append(base)
        groups[base].append(t)

    merged: list[TournamentScrapeResult] = []
    for base in group_order:
        group = groups[base]
        if len(group) == 1:
            merged.append(group[0])
            continue

        group.sort(key=lambda t: t.levels[0].sb if t.levels else float("inf"))
        primary = group[0]

        combined_levels: list[LevelEntry] = list(primary.levels)
        for secondary in group[1:]:
            if not secondary.levels:
                continue
            offset = combined_levels[-1].level if combined_levels else 0
            for lv in secondary.levels:
                combined_levels.append(
                    LevelEntry(
                        level=lv.level + offset,
                        sb=lv.sb,
                        bb=lv.bb,
                        bba=lv.bba,
                        orbit_cost=lv.orbit_cost,
                    )
                )

        starting_stack = primary.starting_stack
        for t in group:
            if t.starting_stack is not None:
                starting_stack = t.starting_stack
                break

        level_length = primary.level_length_minutes
        buyin = primary.buyin

        scrape_issues: list[str] = []
        if starting_stack is None:
            scrape_issues.append("starting_stack not found")
        if level_length is None:
            scrape_issues.append("level_length_minutes not found")
        if not combined_levels:
            scrape_issues.append("No level rows parsed")

        calc_result: CalculationResult | None = None
        if starting_stack is not None and level_length is not None and combined_levels:
            orbit_costs = {lv.level: lv.orbit_cost for lv in combined_levels}
            calc_result = calculate_s_points(
                starting_stack=starting_stack,
                level_length=level_length,
                orbit_costs=orbit_costs,
            )

        (
            s_points,
            affordable_levels_count,
            starting_stack_minutes,
            denominator,
            reference_orbit_costs,
            calculation_error,
        ) = _build_calc_payload(calc_result)

        if calc_result is None:
            calculation_error = (
                "Cannot calculate S-Points without starting_stack, "
                "level_length_minutes, and levels"
            )

        scrape_error = "; ".join(scrape_issues) if scrape_issues else None
        merged.append(
            TournamentScrapeResult(
                source=primary.source,
                name=base,
                url=primary.url,
                buyin=buyin,
                starting_stack=starting_stack,
                level_length_minutes=level_length,
                levels=combined_levels,
                s_points=s_points,
                affordable_levels_count=affordable_levels_count,
                starting_stack_minutes=starting_stack_minutes,
                denominator=denominator,
                reference_orbit_costs=reference_orbit_costs,
                calculation_error=calculation_error,
                scrape_error=scrape_error,
            )
        )

    return merged


def scrape_site(
    config: SiteConfig,
    *,
    headless: bool = True,
    timeout_seconds: int = 12,
    limit: int | None = None,
) -> dict[str, Any]:
    webdriver, options_cls, by, wait_cls = _require_selenium()

    options = options_cls()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    wait = wait_cls(driver, timeout_seconds)

    tournaments: list[TournamentScrapeResult] = []
    fatal_error: str | None = None

    try:
        links = _collect_tournament_links(driver, wait, by, config)
        if limit is not None:
            links = links[:limit]

        if not links:
            fatal_error = (
                f"No tournament links found for {config.site_name} using selectors "
                f"{list(config.link_selectors)}"
            )

        for name, url in links:
            try:
                tournaments.append(_scrape_tournament_page(driver, wait, by, config, name, url))
            except Exception as exc:  # noqa: BLE001
                tournaments.append(
                    TournamentScrapeResult(
                        source=config.site_name,
                        name=name,
                        url=url,
                        buyin=None,
                        starting_stack=None,
                        level_length_minutes=None,
                        levels=[],
                        s_points=None,
                        affordable_levels_count=None,
                        starting_stack_minutes=None,
                        denominator=None,
                        reference_orbit_costs=None,
                        calculation_error="S-Points not calculated",
                        scrape_error=f"Unhandled scraping error: {exc}",
                    )
                )
    finally:
        driver.quit()

    tournaments = _merge_multi_day_tournaments(tournaments)

    with_s_points = sum(1 for item in tournaments if item.s_points is not None)
    payload: dict[str, Any] = {
        "source": config.site_name,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "listing_urls": list(config.listing_urls),
        "summary": {
            "tournaments_found": len(tournaments),
            "with_s_points": with_s_points,
            "without_s_points": len(tournaments) - with_s_points,
        },
        "tournaments": [item.to_dict() for item in tournaments],
    }
    if fatal_error is not None:
        payload["error"] = fatal_error
    return payload


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "tournament"


def write_structure_files(payload: dict[str, Any], output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    names_seen: dict[str, int] = {}
    written = 0

    for tournament in payload.get("tournaments", []):
        starting_stack = tournament.get("starting_stack")
        level_length_minutes = tournament.get("level_length_minutes")
        levels = tournament.get("levels") or []
        if starting_stack is None or level_length_minutes is None or not levels:
            continue

        base = _slugify(str(tournament.get("name") or "tournament"))
        names_seen[base] = names_seen.get(base, 0) + 1
        suffix = "" if names_seen[base] == 1 else f"-{names_seen[base]}"
        file_name = f"{base}{suffix}.json"

        structure_payload = {
            "starting_stack": starting_stack,
            "level_length_minutes": level_length_minutes,
            "levels": [
                {
                    "level": level["level"],
                    "sb": level["sb"],
                    "bb": level["bb"],
                    "bba": level["bba"],
                }
                for level in levels
            ],
        }
        file_path = output_dir / file_name
        file_path.write_text(json.dumps(structure_payload, indent=2), encoding="utf-8")
        tournament["structure_file"] = str(file_path.resolve())
        written += 1

    return written


def run_site_cli(config: SiteConfig, default_output: Path, default_structures_dir: Path) -> int:
    parser = argparse.ArgumentParser(description=f"Scrape {config.site_name} tournaments")
    parser.add_argument("--output", default=str(default_output), help="Output JSON path")
    parser.add_argument(
        "--structures-dir",
        default=str(default_structures_dir),
        help="Directory for per-tournament structure JSON files",
    )
    parser.add_argument("--timeout", type=int, default=12, help="WebDriver wait timeout seconds")
    parser.add_argument("--limit", type=int, default=None, help="Optional max tournaments to scrape")
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run Chrome with UI instead of headless mode",
    )

    args = parser.parse_args()
    try:
        payload = scrape_site(
            config=config,
            headless=not args.no_headless,
            timeout_seconds=args.timeout,
            limit=args.limit,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    structures_written = write_structure_files(payload, Path(args.structures_dir))
    write_json(payload, Path(args.output))

    print(f"source: {config.site_name}")
    print(f"output: {Path(args.output).resolve()}")
    print(f"structures_written: {structures_written}")
    print(f"tournaments_found: {payload['summary']['tournaments_found']}")
    print(f"with_s_points: {payload['summary']['with_s_points']}")

    if payload.get("error"):
        print(f"Error: {payload['error']}", file=sys.stderr)
        return 1
    return 0
