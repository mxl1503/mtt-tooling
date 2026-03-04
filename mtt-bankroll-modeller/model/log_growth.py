from __future__ import annotations

import numpy as np
import pandas as pd


def compute_log_growth(
    outcomes: pd.DataFrame,
    *,
    bankroll: float,
    n_tournaments: int,
) -> tuple[pd.DataFrame, dict[str, float | bool]]:
    """
    Compute expected log growth and append p*log(delta bankroll) per outcome.

    If bankroll + profit <= 0 for any outcome with nonzero probability, ruin is possible.
    """
    if bankroll <= 0:
        raise ValueError("bankroll must be > 0")
    if n_tournaments <= 0:
        raise ValueError("n_tournaments must be > 0")

    table = outcomes.copy()
    ruin_mask = (table["Probability"] > 0) & ((bankroll + table["Profit"]) <= 0)

    if ruin_mask.any():
        safe_mask = ~ruin_mask
        table["p * log(delta bankroll)"] = np.nan
        safe_ratio = (bankroll + table.loc[safe_mask, "Profit"]) / bankroll
        table.loc[safe_mask, "p * log(delta bankroll)"] = (
            table.loc[safe_mask, "Probability"] * np.log(safe_ratio)
        )
        table.loc[ruin_mask, "p * log(delta bankroll)"] = -np.inf

        expected_log_growth = -np.inf
        growth_per_tournament = -1.0
        growth_after_n = -1.0
    else:
        ratio = (bankroll + table["Profit"]) / bankroll
        table["p * log(delta bankroll)"] = table["Probability"] * np.log(ratio)
        expected_log_growth = float(table["p * log(delta bankroll)"].sum())
        growth_per_tournament = float(np.exp(expected_log_growth) - 1.0)
        growth_after_n = float(np.exp(n_tournaments * expected_log_growth) - 1.0)

    metrics: dict[str, float | bool] = {
        "expected_log_growth": expected_log_growth,
        "growth_per_tournament": growth_per_tournament,
        "growth_after_n": growth_after_n,
        "ruin_possible": bool(ruin_mask.any()),
    }
    return table, metrics

