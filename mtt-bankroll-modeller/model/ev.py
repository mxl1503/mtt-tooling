from __future__ import annotations

import pandas as pd


def build_outcome_table(
    paid_placements: pd.DataFrame,
    *,
    abi: float,
    rake_rate: float,
    num_players: int,
    each_paid_probability: float,
    bust_probability: float,
) -> pd.DataFrame:
    """Build outcome table for all paid places plus a Bust row."""
    prize_pool = num_players * abi * (1.0 - rake_rate)

    outcomes = paid_placements.copy()
    outcomes["Probability"] = float(each_paid_probability)
    outcomes["Payout $"] = outcomes["Payout %"] * prize_pool
    outcomes["Profit"] = outcomes["Payout $"] - abi
    outcomes["Place"] = outcomes["Place"].astype(str)

    bust = pd.DataFrame(
        [
            {
                "Place": "Bust",
                "Payout %": 0.0,
                "Payout $": 0.0,
                "Profit": -abi,
                "Probability": float(bust_probability),
            }
        ]
    )

    return pd.concat([outcomes, bust], ignore_index=True)


def compute_ev_metrics(outcomes: pd.DataFrame, abi: float) -> dict[str, float]:
    """Compute EV dollars and ROI metrics."""
    ev_dollars = float((outcomes["Probability"] * outcomes["Profit"]).sum())
    ev_pct = ev_dollars / abi if abi > 0 else float("nan")

    return {
        "ev_dollars": ev_dollars,
        "ev_pct": ev_pct,
        "true_roi_pct": ev_pct,
    }

