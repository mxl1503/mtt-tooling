from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json
from typing import Any

REQUIRED_REFERENCE_LEVELS = (6, 10, 14, 18)


@dataclass(frozen=True)
class StructureInput:
    orbit_costs: dict[int, int]
    starting_stack: int | None
    level_length: int | None


@dataclass(frozen=True)
class CalculationResult:
    s_points: float | None
    affordable_levels_count: int
    starting_stack_minutes: int
    orbit_costs_reference: dict[int, int | None]
    denominator: float | None
    error: str | None


def _parse_int(value: Any, field_name: str) -> int:
    if value is None:
        raise ValueError(f"{field_name} is required")
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    try:
        text = str(value).strip()
        if text == "":
            raise ValueError
        return int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return _parse_int(value, field_name)


def _level_from_row(row: dict[str, Any], index: int) -> int:
    level_raw = row.get("level")
    level = _parse_int(level_raw, f"level (row {index})")
    if level < 1:
        raise ValueError(f"level must be >= 1 (row {index})")
    return level


def _compute_orbit_cost(row: dict[str, Any], level: int) -> int:
    sb = _optional_int(row.get("sb"), f"sb (level {level})")
    bb = _optional_int(row.get("bb"), f"bb (level {level})")
    bba = _optional_int(row.get("bba"), f"bba (level {level})")

    if sb is not None and bb is not None and bba is not None:
        orbit_cost = sb + bb + bba
    else:
        orbit_cost = _optional_int(row.get("orbit_cost"), f"orbit_cost (level {level})")
        if orbit_cost is None:
            raise ValueError(
                f"level {level} requires sb/bb/bba or orbit_cost to compute orbit cost"
            )

    if orbit_cost < 0:
        raise ValueError(f"orbit cost must be >= 0 (level {level})")
    return orbit_cost


def _normalize_levels(level_rows: list[dict[str, Any]]) -> dict[int, int]:
    orbit_costs: dict[int, int] = {}
    for idx, row in enumerate(level_rows, start=1):
        level = _level_from_row(row, idx)
        orbit_cost = _compute_orbit_cost(row, level)
        orbit_costs[level] = orbit_cost
    if not orbit_costs:
        raise ValueError("No levels found in structure file")
    return dict(sorted(orbit_costs.items(), key=lambda item: item[0]))


def _read_json(file_path: Path) -> StructureInput:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON structure file must be an object")

    levels_raw = payload.get("levels")
    if not isinstance(levels_raw, list):
        raise ValueError("JSON must include a 'levels' array")
    if any(not isinstance(level, dict) for level in levels_raw):
        raise ValueError("Each entry in 'levels' must be an object")

    orbit_costs = _normalize_levels(levels_raw)
    starting_stack = _optional_int(payload.get("starting_stack"), "starting_stack")
    level_length = _optional_int(
        payload.get("level_length_minutes"), "level_length_minutes"
    )

    return StructureInput(
        orbit_costs=orbit_costs,
        starting_stack=starting_stack,
        level_length=level_length,
    )


def _read_csv(file_path: Path) -> StructureInput:
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("CSV structure file has no rows")

    orbit_costs = _normalize_levels(rows)

    starting_stack = _optional_int(rows[0].get("starting_stack"), "starting_stack")
    level_length = _optional_int(rows[0].get("level_length_minutes"), "level_length_minutes")

    return StructureInput(
        orbit_costs=orbit_costs,
        starting_stack=starting_stack,
        level_length=level_length,
    )


def load_structure_file(file_path: str | Path) -> StructureInput:
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"Structure file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        return _read_json(path)
    if suffix == ".csv":
        return _read_csv(path)

    raise ValueError("Unsupported file format. Use .json or .csv")


def calculate_s_points(
    starting_stack: int, level_length: int, orbit_costs: dict[int, int]
) -> CalculationResult:
    if starting_stack < 0:
        raise ValueError("starting_stack must be >= 0")
    if level_length <= 0:
        raise ValueError("level_length must be > 0")
    if not orbit_costs:
        raise ValueError("orbit_costs cannot be empty")

    affordable_levels_count = 0
    for _, cost in sorted(orbit_costs.items(), key=lambda item: item[0]):
        if cost <= starting_stack:
            affordable_levels_count += 1
        else:
            break

    starting_stack_minutes = affordable_levels_count * level_length
    reference_costs = {level: orbit_costs.get(level) for level in REQUIRED_REFERENCE_LEVELS}

    missing = [level for level, cost in reference_costs.items() if cost is None]
    if missing:
        return CalculationResult(
            s_points=None,
            affordable_levels_count=affordable_levels_count,
            starting_stack_minutes=starting_stack_minutes,
            orbit_costs_reference=reference_costs,
            denominator=None,
            error=f"Missing required reference levels: {missing}",
        )

    level6 = reference_costs[6]
    level10 = reference_costs[10]
    level14 = reference_costs[14]
    level18 = reference_costs[18]

    # Type checkers do not infer from missing check above.
    assert level6 is not None
    assert level10 is not None
    assert level14 is not None
    assert level18 is not None

    if level6 == 0 or level10 == 0 or level14 == 0:
        return CalculationResult(
            s_points=None,
            affordable_levels_count=affordable_levels_count,
            starting_stack_minutes=starting_stack_minutes,
            orbit_costs_reference=reference_costs,
            denominator=None,
            error=(
                "Cannot compute denominator because one of Level 6/10/14 orbit costs is zero "
                f"(level6={level6}, level10={level10}, level14={level14})"
            ),
        )

    denominator = (level10 / level6) + (level14 / level10) + (level18 / level14)
    if denominator == 0:
        return CalculationResult(
            s_points=None,
            affordable_levels_count=affordable_levels_count,
            starting_stack_minutes=starting_stack_minutes,
            orbit_costs_reference=reference_costs,
            denominator=denominator,
            error="Cannot compute S-Points because denominator is zero",
        )

    s_points = starting_stack_minutes / denominator
    return CalculationResult(
        s_points=s_points,
        affordable_levels_count=affordable_levels_count,
        starting_stack_minutes=starting_stack_minutes,
        orbit_costs_reference=reference_costs,
        denominator=denominator,
        error=None,
    )
