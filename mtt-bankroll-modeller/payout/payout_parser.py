from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


def parse_percentage(value: object) -> float:
    """Parse values like '27.0%' into decimal fractions like 0.27."""
    if pd.isna(value):
        return np.nan

    text = str(value).strip()
    if not text:
        return np.nan
    if text.endswith("%"):
        text = text[:-1].strip()
    if not text:
        return np.nan

    return float(text) / 100.0


def expand_place_token(place_token: str) -> list[int]:
    """Expand '11-20' into [11, ..., 20], or '1' into [1]."""
    token = place_token.strip()
    if token == "ITM%":
        return []

    if "-" in token:
        start_str, end_str = token.split("-", 1)
        start = int(start_str)
        end = int(end_str)
        if end < start:
            raise ValueError(f"Invalid place range: {place_token}")
        return list(range(start, end + 1))

    return [int(token)]


def load_payout_structure(path: str | Path) -> pd.DataFrame:
    """Load payout structure CSV and set Place as index."""
    payout_structure = pd.read_csv(path)
    if "Place" not in payout_structure.columns:
        raise ValueError("payout_structure.csv must include a 'Place' column")

    payout_structure = payout_structure.copy()
    payout_structure["Place"] = payout_structure["Place"].astype(str).str.strip()
    payout_structure = payout_structure.set_index("Place")
    return payout_structure


def build_paid_placements(
    payout_structure: pd.DataFrame,
    bucket: str,
    num_players: int,
) -> tuple[pd.DataFrame, float, int]:
    """
    Build expanded paid placements up to number_paid.

    Returns:
      - DataFrame with columns: Place, Payout %
      - ITM rate as decimal fraction
      - number_paid
    """
    if bucket not in payout_structure.columns:
        raise ValueError(f"Bucket '{bucket}' was not found in payout structure columns")
    if "ITM%" not in payout_structure.index:
        raise ValueError("payout_structure.csv must include an 'ITM%' row")

    itm_rate = parse_percentage(payout_structure.at["ITM%", bucket])
    if np.isnan(itm_rate):
        raise ValueError(f"Could not parse ITM% for bucket '{bucket}'")
    itm_rate = min(max(float(itm_rate), 0.0), 1.0)

    number_paid = math.floor(num_players * itm_rate)
    if number_paid <= 0:
        empty = pd.DataFrame(columns=["Place", "Payout %"])
        return empty, itm_rate, 0

    rows: list[dict[str, float | int]] = []
    for place_token, raw_pct in payout_structure[bucket].items():
        if place_token == "ITM%":
            continue

        payout_pct = parse_percentage(raw_pct)
        if np.isnan(payout_pct):
            continue

        for place in expand_place_token(str(place_token)):
            if place <= number_paid:
                rows.append({"Place": place, "Payout %": float(payout_pct)})

    paid_placements = pd.DataFrame(rows)
    if paid_placements.empty:
        paid_placements = pd.DataFrame(columns=["Place", "Payout %"])
    else:
        paid_placements = (
            paid_placements.drop_duplicates(subset=["Place"], keep="first")
            .sort_values("Place")
            .reset_index(drop=True)
        )

    return paid_placements, itm_rate, number_paid

