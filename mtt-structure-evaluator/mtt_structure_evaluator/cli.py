from __future__ import annotations

import argparse
import sys

from .s_points import calculate_s_points, load_structure_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute S-Points for an MTT structure")
    parser.add_argument("--file", required=True, help="Path to structure file (.json or .csv)")
    parser.add_argument(
        "--starting-stack",
        type=int,
        default=None,
        help="Starting stack in chips (overrides file value)",
    )
    parser.add_argument(
        "--level-length",
        type=int,
        default=None,
        help="Level length in minutes (overrides file value)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        structure = load_structure_file(args.file)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    starting_stack = args.starting_stack
    if starting_stack is None:
        starting_stack = structure.starting_stack

    level_length = args.level_length
    if level_length is None:
        level_length = structure.level_length

    if starting_stack is None:
        print(
            "Error: starting_stack is required via --starting-stack or file field 'starting_stack'",
            file=sys.stderr,
        )
        return 1

    if level_length is None:
        print(
            "Error: level_length is required via --level-length or file field 'level_length_minutes'",
            file=sys.stderr,
        )
        return 1

    try:
        result = calculate_s_points(
            starting_stack=starting_stack,
            level_length=level_length,
            orbit_costs=structure.orbit_costs,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"affordable_levels_count: {result.affordable_levels_count}")
    print(f"starting_stack_minutes: {result.starting_stack_minutes}")
    print(f"orbit_cost_level_6: {result.orbit_costs_reference[6]}")
    print(f"orbit_cost_level_10: {result.orbit_costs_reference[10]}")
    print(f"orbit_cost_level_14: {result.orbit_costs_reference[14]}")
    print(f"orbit_cost_level_18: {result.orbit_costs_reference[18]}")
    print(
        "denominator: "
        + ("null" if result.denominator is None else f"{result.denominator:.6f}")
    )

    if result.s_points is None:
        print("s_points: null")
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    print(f"s_points: {result.s_points:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
