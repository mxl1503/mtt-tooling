from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_bucket_sizes(path: str | Path) -> pd.DataFrame:
    """Load and validate bucket size metadata."""
    bucket_sizes = pd.read_csv(path)
    required_columns = {"bucket", "max_players"}
    missing_columns = required_columns.difference(bucket_sizes.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"bucket_sizes.csv is missing required column(s): {missing}")

    bucket_sizes = bucket_sizes.copy()
    bucket_sizes["max_players"] = pd.to_numeric(
        bucket_sizes["max_players"], errors="raise"
    ).astype(int)
    bucket_sizes = bucket_sizes.sort_values("max_players").reset_index(drop=True)
    return bucket_sizes


def select_bucket(num_players: int, bucket_sizes: pd.DataFrame) -> str:
    """Pick the bucket whose max_players is closest to num_players."""
    if num_players <= 0:
        raise ValueError("num_players must be > 0")
    if bucket_sizes.empty:
        raise ValueError("bucket_sizes cannot be empty")

    distances = (bucket_sizes["max_players"] - num_players).abs()
    closest_idx = distances.idxmin()
    return str(bucket_sizes.loc[closest_idx, "bucket"])

