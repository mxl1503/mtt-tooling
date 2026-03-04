from __future__ import annotations

from pathlib import Path

import numpy as np
import streamlit as st

from model.ev import build_outcome_table, compute_ev_metrics
from model.log_growth import compute_log_growth
from model.probabilities import paid_and_bust_probabilities
from payout.bucket_selector import load_bucket_sizes, select_bucket
from payout.payout_parser import build_paid_placements, load_payout_structure
from utils.formatting import format_currency, format_outcome_table, format_percent


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"


@st.cache_data
def load_inputs() -> tuple:
    payout_structure = load_payout_structure(DATA_DIR / "payout_structure.csv")
    bucket_sizes = load_bucket_sizes(DATA_DIR / "bucket_sizes.csv")
    return payout_structure, bucket_sizes


def render() -> None:
    st.set_page_config(page_title="MTT EV + Bankroll Growth", layout="wide")
    st.title("Poker MTT EV + Bankroll Growth Calculator")
    st.write(
        "ABI is treated as total tournament entry cost (buy-in + rake). "
        "Calculations use the payout table + ITM% with a uniform paid-place probability model."
    )

    payout_structure, bucket_sizes = load_inputs()

    input_col1, input_col2, input_col3 = st.columns(3)
    with input_col1:
        bankroll = st.number_input(
            "Bankroll ($)", min_value=0.01, value=5000.0, step=100.0
        )
        abi = st.number_input("ABI ($)", min_value=0.01, value=100.0, step=1.0)
    with input_col2:
        rake_pct = st.number_input("Rake (%)", min_value=0.0, max_value=50.0, value=10.0)
        num_players = st.number_input(
            "Number of Players", min_value=1, max_value=1999, value=100, step=1
        )
    with input_col3:
        estimated_roi_pct = st.number_input(
            "Estimated ROI (%)", min_value=-100.0, max_value=1000.0, value=15.0, step=1.0
        )
        n_tournaments = st.number_input(
            "N Tournaments", min_value=1, max_value=100000, value=100, step=1
        )

    rake_rate = rake_pct / 100.0
    estimated_roi = estimated_roi_pct / 100.0

    selected_bucket = select_bucket(int(num_players), bucket_sizes)
    paid_placements, itm_rate, number_paid = build_paid_placements(
        payout_structure, selected_bucket, int(num_players)
    )
    each_paid_probability, bust_probability, floored_to_zero = paid_and_bust_probabilities(
        itm_rate, number_paid
    )

    outcomes = build_outcome_table(
        paid_placements,
        abi=float(abi),
        rake_rate=float(rake_rate),
        num_players=int(num_players),
        each_paid_probability=each_paid_probability,
        bust_probability=bust_probability,
    )

    outcomes, log_metrics = compute_log_growth(
        outcomes, bankroll=float(bankroll), n_tournaments=int(n_tournaments)
    )
    ev_metrics = compute_ev_metrics(outcomes, abi=float(abi))

    prize_pool = num_players * abi * (1.0 - rake_rate)
    sum_probabilities = float(outcomes["Probability"].sum())
    bankroll_buy_ins = bankroll / abi

    if floored_to_zero:
        st.warning(
            "floor(num_players * ITM%) = 0 for this setup. "
            "No paid placements are modeled; all probability is assigned to Bust."
        )
    if len(paid_placements) < number_paid:
        st.warning(
            f"Payout table only defines {len(paid_placements)} paid placements "
            f"up to place {number_paid} for this bucket."
        )
    if log_metrics["ruin_possible"]:
        st.error(
            "Ruin is possible: at least one nonzero-probability outcome has "
            "bankroll + profit <= 0. Log growth is -inf."
        )

    st.caption(
        f"Selected bucket: `{selected_bucket}` | ITM: {format_percent(itm_rate)} | "
        f"Paid places: {number_paid} | Prize pool: {format_currency(prize_pool)}"
    )

    st.subheader("Summary Metrics")
    row1 = st.columns(4)
    row1[0].metric("EV ($)", format_currency(ev_metrics["ev_dollars"]))
    row1[1].metric("EV (%)", format_percent(ev_metrics["ev_pct"]))
    row1[2].metric("True ROI (%)", format_percent(ev_metrics["true_roi_pct"]))
    row1[3].metric("# Buy-ins in Bankroll", f"{bankroll_buy_ins:,.2f}")

    row2 = st.columns(3)
    expected_log_growth = log_metrics["expected_log_growth"]
    if np.isneginf(expected_log_growth):
        expected_log_text = "-inf"
    else:
        expected_log_text = f"{expected_log_growth:.8f}"
    row2[0].metric("Expected Log Bankroll Growth", expected_log_text)
    row2[1].metric(
        "Bankroll Growth / Tournament", format_percent(log_metrics["growth_per_tournament"])
    )
    row2[2].metric(
        f"Bankroll Growth After {int(n_tournaments)} Tournaments",
        format_percent(log_metrics["growth_after_n"]),
    )

    st.subheader("Input ROI Reference")
    roi_cols = st.columns(2)
    roi_cols[0].metric("Estimated ROI Input (%)", f"{estimated_roi_pct:.2f}%")
    roi_cols[1].metric("Estimated EV from Input ($)", format_currency(abi * estimated_roi))

    st.subheader("Outcome Table")
    outcome_columns = [
        "Place",
        "Payout %",
        "Payout $",
        "Profit",
        "Probability",
        "p * log(delta bankroll)",
    ]
    display_table = format_outcome_table(outcomes[outcome_columns])
    st.dataframe(display_table, use_container_width=True, hide_index=True)
    st.caption(f"Sum of probabilities = {sum_probabilities * 100:.2f}%")


if __name__ == "__main__":
    render()

