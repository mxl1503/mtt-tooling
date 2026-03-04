# MTT Tooling

Collection of poker MTT utilities:

- `mtt-bankroll-modeller`: Streamlit app for EV and bankroll-growth modelling.
- `mtt-structure-evaluator`: Python CLI for evaluating tournament structures with S-Points.

## Repository Layout

```text
mtt-tooling/
  mtt-bankroll-modeller/
  mtt-structure-evaluator/
```

## Prerequisites

- Python 3.11+ (recommended for both projects)
- `pip`

## Quick Start

### 1) MTT Bankroll Modeller (Streamlit)

```bash
cd mtt-bankroll-modeller
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### 2) MTT Structure Evaluator (CLI)

```bash
cd mtt-structure-evaluator
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m mtt_structure_evaluator.cli --file examples/example_structure.json --starting-stack 15000 --level-length 30
```

If you want scraper support:

```bash
pip install -e ".[scraping]"
```

Run scraper scripts from `mtt-structure-evaluator/`:

```bash
python structure-scrapers/kingsroom_scraper.py
python structure-scrapers/kingslive_scraper.py
python structure-scrapers/sydney_champs_scraper.py
```

Sydney Champs reads the bundled PDF at
`mtt_structure_evaluator/structure-pdfs/sydney-champs-structures.pdf`
and writes outputs under `structure-scrapes/sydney_champs*`.

## Notes

- Each subproject has its own implementation details and README.
- Run commands from each subproject directory unless noted otherwise.
