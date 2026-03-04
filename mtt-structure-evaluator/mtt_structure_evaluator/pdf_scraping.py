from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any

from .s_points import CalculationResult, calculate_s_points
from .scraping import write_json, write_structure_files

try:
    import pytesseract
    from pdf2image import convert_from_path
except Exception:  # noqa: BLE001
    pytesseract = None
    convert_from_path = None


PDF_LEVEL_HEADER_RE = re.compile(
    r"\bLEVEL\s+DAY\s+DURATION\s+SMALL\s+BLIND\s+BIG\s+BLIND\b", re.IGNORECASE
)
LEVEL_ROW_RE = re.compile(
    r"^LEVEL\s+(?P<level>\d+)\s+(?P<day>\d+)\s+(?P<duration>\d+)\s+MIN\s+"
    r"(?P<sb>[\d,]+)\s+(?P<bb>[\d,]+)"
    r"(?:\s+(?P<ante>[\d,]+))?$",
    re.IGNORECASE,
)
EVENT_RE = re.compile(r"\bEVENT\s*#\s*(?P<num>\d+)\b", re.IGNORECASE)
BUYIN_RE = re.compile(r"\bBUY-IN\s*\$?(?P<total>[\d,]+)", re.IGNORECASE)
STARTING_STACK_RE = re.compile(r"\bSTARTING\s+STACK\s+(?P<stack>[\d,]+)", re.IGNORECASE)
SCHEDULE_RE = re.compile(
    r"^(?P<label>DAY\s+\d+[A-Z]?|\bFINAL\b|\bDAY\s+\d+)\s+"
    r"(?P<date>\d{1,2}\s+[A-Z]{3}\s+\d{4})\s*"
    r"\((?P<time>[\d.]+[AP]M)\)$",
    re.IGNORECASE,
)


@dataclass
class ParsedLevel:
    level: int
    day: int
    duration_min: int
    sb: int
    bb: int
    bba: int


@dataclass
class ParsedEvent:
    event_number: int
    event_name: str
    buy_in_total: int | None
    starting_stack: int | None
    schedule: list[dict[str, str]]
    levels: list[ParsedLevel]
    source_pages: list[int]


def _require_pdfplumber() -> Any:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is required for Sydney Champs scraping. "
            "Install with: pip install -e '.[scraping]'"
        ) from exc
    return pdfplumber


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").strip()
    if cleaned == "":
        return None
    return int(cleaned)


def _normalize_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"\s{2,}", " ", line)
        lines.append(line)
    return lines


def _page_needs_ocr(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 200:
        return True
    if not PDF_LEVEL_HEADER_RE.search(stripped) and not EVENT_RE.search(stripped):
        return True
    return False


def _ocr_page(pdf_path: Path, page_index: int, dpi: int) -> str:
    if pytesseract is None or convert_from_path is None:
        raise RuntimeError(
            "OCR dependencies are missing. Install pytesseract + pdf2image and ensure "
            "tesseract/poppler are available."
        )

    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        first_page=page_index + 1,
        last_page=page_index + 1,
    )
    if not images:
        return ""
    return pytesseract.image_to_string(images[0])


def _parse_event_from_page(lines: list[str], page_number: int) -> ParsedEvent | None:
    joined = "\n".join(lines)
    event_match = EVENT_RE.search(joined)
    if event_match is None:
        return None

    event_number = int(event_match.group("num"))
    event_name = f"EVENT #{event_number}"

    for i, line in enumerate(lines):
        if EVENT_RE.search(line) is None:
            continue

        title_parts: list[str] = []
        for j in range(i, min(i + 4, len(lines))):
            candidate = lines[j]
            upper = candidate.upper()
            if LEVEL_ROW_RE.match(candidate):
                break
            if PDF_LEVEL_HEADER_RE.search(candidate):
                continue
            if upper.startswith("BUY-IN") or upper.startswith("STARTING STACK"):
                continue
            if "GAMBLEAWARE" in upper:
                continue
            title_parts.append(candidate)

        joined_title = " ".join(title_parts).strip()
        if joined_title:
            event_name = joined_title
        break

    buy_in_total: int | None = None
    buyin_match = BUYIN_RE.search(joined)
    if buyin_match is not None:
        buy_in_total = _to_int(buyin_match.group("total"))

    starting_stack: int | None = None
    stack_match = STARTING_STACK_RE.search(joined)
    if stack_match is not None:
        starting_stack = _to_int(stack_match.group("stack"))

    schedule: list[dict[str, str]] = []
    for line in lines:
        schedule_match = SCHEDULE_RE.match(line)
        if schedule_match is None:
            continue
        schedule.append(
            {
                "label": schedule_match.group("label").upper(),
                "date": schedule_match.group("date").upper(),
                "time": schedule_match.group("time").upper(),
            }
        )

    levels: list[ParsedLevel] = []
    for line in lines:
        level_match = LEVEL_ROW_RE.match(line)
        if level_match is None:
            continue
        levels.append(
            ParsedLevel(
                level=int(level_match.group("level")),
                day=int(level_match.group("day")),
                duration_min=int(level_match.group("duration")),
                sb=_to_int(level_match.group("sb")) or 0,
                bb=_to_int(level_match.group("bb")) or 0,
                bba=_to_int(level_match.group("ante")) or 0,
            )
        )

    return ParsedEvent(
        event_number=event_number,
        event_name=event_name,
        buy_in_total=buy_in_total,
        starting_stack=starting_stack,
        schedule=schedule,
        levels=levels,
        source_pages=[page_number],
    )


def _merge_events(events: list[ParsedEvent]) -> list[ParsedEvent]:
    merged: list[ParsedEvent] = []
    by_event: dict[int, ParsedEvent] = {}

    for event in events:
        existing = by_event.get(event.event_number)
        if existing is None:
            by_event[event.event_number] = event
            merged.append(event)
            continue

        existing.source_pages.extend(event.source_pages)

        for item in event.schedule:
            if item not in existing.schedule:
                existing.schedule.append(item)

        existing_levels = {(level.level, level.day) for level in existing.levels}
        for level in event.levels:
            level_key = (level.level, level.day)
            if level_key not in existing_levels:
                existing.levels.append(level)

        if existing.buy_in_total is None:
            existing.buy_in_total = event.buy_in_total
        if existing.starting_stack is None:
            existing.starting_stack = event.starting_stack
        if len(existing.event_name) < len(event.event_name):
            existing.event_name = event.event_name

    for event in merged:
        event.source_pages = sorted(set(event.source_pages))
        event.levels.sort(key=lambda level: (level.day, level.level))

    return merged


def _extract_level_length_minutes(levels: list[ParsedLevel]) -> tuple[int | None, str | None]:
    durations = {level.duration_min for level in levels if level.duration_min > 0}
    if not durations:
        return None, "level_length_minutes not found"
    if len(durations) == 1:
        return next(iter(durations)), None

    day1_durations = [
        level.duration_min for level in levels if level.day == 1 and level.duration_min > 0
    ]
    if day1_durations:
        most_common = Counter(day1_durations).most_common(1)[0][0]
        return most_common, None

    all_durations = [level.duration_min for level in levels if level.duration_min > 0]
    most_common = Counter(all_durations).most_common(1)[0][0]
    return most_common, None


def _build_calc_payload(result: CalculationResult | None) -> tuple[
    float | None,
    int | None,
    int | None,
    float | None,
    dict[int, int | None] | None,
    str | None,
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


def _event_to_tournament_payload(
    event: ParsedEvent, pdf_path: Path, source_name: str
) -> dict[str, Any]:
    scrape_issues: list[str] = []

    if event.starting_stack is None:
        scrape_issues.append("starting_stack not found")
    if not event.levels:
        scrape_issues.append("No level rows parsed")

    level_length_minutes, duration_issue = _extract_level_length_minutes(event.levels)
    if duration_issue is not None:
        scrape_issues.append(duration_issue)

    orbit_costs: dict[int, int] = {}
    levels_payload: list[dict[str, Any]] = []
    for level in event.levels:
        orbit_cost = level.sb + level.bb + level.bba
        if level.level not in orbit_costs:
            orbit_costs[level.level] = orbit_cost
        levels_payload.append(
            {
                "level": level.level,
                "day": level.day,
                "duration_min": level.duration_min,
                "sb": level.sb,
                "bb": level.bb,
                "bba": level.bba,
                "orbit_cost": orbit_cost,
            }
        )

    calc_result: CalculationResult | None = None
    if event.starting_stack is not None and level_length_minutes is not None and orbit_costs:
        calc_result = calculate_s_points(
            starting_stack=event.starting_stack,
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
    first_page = event.source_pages[0] if event.source_pages else 1
    buyin_display = (
        None if event.buy_in_total is None else f"${event.buy_in_total:,}"
    )

    return {
        "source": source_name,
        "name": event.event_name,
        "url": f"{pdf_path.resolve()}#page={first_page}",
        "event_number": event.event_number,
        "buyin": buyin_display,
        "buy_in_total": event.buy_in_total,
        "starting_stack": event.starting_stack,
        "level_length_minutes": level_length_minutes,
        "schedule": event.schedule,
        "source_pages": event.source_pages,
        "levels": levels_payload,
        "s_points": None if s_points is None else round(s_points, 2),
        "affordable_levels_count": affordable_levels_count,
        "starting_stack_minutes": starting_stack_minutes,
        "denominator": denominator,
        "reference_orbit_costs": reference_orbit_costs,
        "calculation_error": calculation_error,
        "scrape_error": scrape_error,
    }


def scrape_pdf(
    pdf_path: Path,
    *,
    source_name: str = "sydney_champs_pdf",
    use_ocr: bool = True,
    ocr_dpi: int = 300,
) -> dict[str, Any]:
    pdfplumber = _require_pdfplumber()

    if not pdf_path.exists():
        raise RuntimeError(f"PDF not found: {pdf_path}")

    parsed_events: list[ParsedEvent] = []
    ocr_unavailable = False

    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            if use_ocr and _page_needs_ocr(text):
                try:
                    text = _ocr_page(pdf_path, index, ocr_dpi)
                except RuntimeError:
                    ocr_unavailable = True
                except Exception:  # noqa: BLE001
                    pass

            lines = _normalize_lines(text)
            maybe_event = _parse_event_from_page(lines, index + 1)
            if maybe_event is not None:
                parsed_events.append(maybe_event)

    events = _merge_events(parsed_events)
    tournaments = [
        _event_to_tournament_payload(event, pdf_path, source_name) for event in events
    ]
    with_s_points = sum(1 for item in tournaments if item.get("s_points") is not None)

    payload: dict[str, Any] = {
        "source": source_name,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "pdf_path": str(pdf_path.resolve()),
        "summary": {
            "tournaments_found": len(tournaments),
            "with_s_points": with_s_points,
            "without_s_points": len(tournaments) - with_s_points,
        },
        "tournaments": tournaments,
    }

    errors: list[str] = []
    if not tournaments:
        errors.append("No events parsed from PDF")
    if use_ocr and ocr_unavailable:
        errors.append(
            "OCR requested but dependencies were unavailable on at least one page; "
            "continuing with text extraction only"
        )

    if errors:
        payload["error"] = "; ".join(errors)

    return payload


def run_pdf_cli(default_pdf: Path, default_output: Path, default_structures_dir: Path) -> int:
    parser = argparse.ArgumentParser(description="Scrape Sydney Champs structure PDF")
    parser.add_argument("--pdf", default=str(default_pdf), help="Input tournament structure PDF")
    parser.add_argument("--output", default=str(default_output), help="Output JSON path")
    parser.add_argument(
        "--structures-dir",
        default=str(default_structures_dir),
        help="Directory for per-tournament structure JSON files",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR fallback for pages with poor text extraction",
    )
    parser.add_argument("--ocr-dpi", type=int, default=300, help="OCR DPI when fallback is used")

    args = parser.parse_args()

    try:
        payload = scrape_pdf(
            Path(args.pdf),
            use_ocr=not args.no_ocr,
            ocr_dpi=args.ocr_dpi,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    structures_written = write_structure_files(payload, Path(args.structures_dir))
    write_json(payload, Path(args.output))

    print("source: sydney_champs_pdf")
    print(f"pdf: {Path(args.pdf).resolve()}")
    print(f"output: {Path(args.output).resolve()}")
    print(f"structures_written: {structures_written}")
    print(f"tournaments_found: {payload['summary']['tournaments_found']}")
    print(f"with_s_points: {payload['summary']['with_s_points']}")

    if payload.get("error"):
        print(f"Error: {payload['error']}", file=sys.stderr)
        return 1
    return 0
