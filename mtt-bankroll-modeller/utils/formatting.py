from __future__ import annotations

import numpy as np
import pandas as pd


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_percent(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


def format_log_component(value: float) -> str:
    if np.isposinf(value):
        return "inf"
    if np.isneginf(value):
        return "-inf"
    if pd.isna(value):
        return "n/a"
    return f"{value:.8f}"


def format_outcome_table(table: pd.DataFrame) -> pd.DataFrame:
    display = table.copy()
    display["Payout %"] = display["Payout %"].map(format_percent)
    display["Payout $"] = display["Payout $"].map(format_currency)
    display["Profit"] = display["Profit"].map(format_currency)
    display["Probability"] = display["Probability"].map(format_percent)
    display["p * log(delta bankroll)"] = display["p * log(delta bankroll)"].map(
        format_log_component
    )
    return display

