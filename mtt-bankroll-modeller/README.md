# MTT EV + Bankroll Growth Calculator

Small Streamlit app for modeling tournament EV and bankroll growth for poker MTTs.

## What this app models

Inputs:
- bankroll ($)
- ABI (average buy-in, total tournament entry cost)
- rake (%)
- number of players
- estimated ROI (%) input reference
- number of tournaments `N` (default 100)

Outputs:
- EV ($)
- EV (%)
- true ROI (%)
- bankroll buy-ins
- expected log bankroll growth
- bankroll growth per tournament
- bankroll growth after `N` tournaments
- outcome table including paid placements + `Bust`

## Core definitions

### ABI
ABI is the **total** cost to enter (buy-in + rake).

Example:
- ABI = `$100`
- Rake = `10%`
- `$90` contributes to prize pool
- `$10` is rake

### Rake and prize pool
`prize_pool = num_players * ABI * (1 - rake)`

### ROI definition
ROI is on total ABI cost:

`ROI = EV / ABI`

In this project, `EV (%)` and `true ROI (%)` are both shown from this definition.

## Data and bucket selection

Files:
- `data/payout_structure.csv`
- `data/bucket_sizes.csv`

Bucket rule:
- choose the bucket whose `max_players` is closest to `num_players`

Payout parsing:
- parse percentage strings like `27.0%` to decimals
- expand ranges (example: `11-20` -> places 11 through 20)

## ITM calculation

`ITM%` is read from the `ITM%` row of the selected bucket.

`number_paid = floor(num_players * ITM%)`

Only places `1..number_paid` are used in the outcome model.

## Probability model (simple)

- all paid placements are equally likely
- bust probability is `1 - ITM%`

If `floor(num_players * ITM%) == 0`, the app warns and uses Bust-only probability so probabilities still sum to 100%.

## EV model

For each paid place:
- `payout_$ = payout_pct * total_prize_pool`
- `profit = payout_$ - ABI`

Bust:
- `profit = -ABI`

Then:
- `EV = sum(probability * profit)`
- `true ROI = EV / ABI`

## Log bankroll growth model

For each outcome:

`log_delta = log((bankroll + profit) / bankroll)`

Expected log growth:

`E_log = sum(probability * log_delta)`

Derived metrics:
- growth per tournament: `exp(E_log) - 1`
- growth after `N` tournaments: `exp(N * E_log) - 1`

If any nonzero-probability outcome has `bankroll + profit <= 0`, ruin is possible and the app warns.

## Run

```bash
make install
make run
```

Requires [uv](https://docs.astral.sh/uv/).

## Project structure

```text
app.py
data/
  payout_structure.csv
  bucket_sizes.csv
model/
  probabilities.py
  ev.py
  log_growth.py
payout/
  payout_parser.py
  bucket_selector.py
utils/
  formatting.py
```

