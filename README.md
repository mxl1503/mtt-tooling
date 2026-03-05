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

- [uv](https://docs.astral.sh/uv/) (Python 3.11+ is managed by uv)

## Quick Start

### 1) MTT Bankroll Modeller (Streamlit)

```bash
cd mtt-bankroll-modeller
make install
make run
```

### 2) MTT Structure Evaluator (CLI)

```bash
cd mtt-structure-evaluator
make install
make run-example
```

Or with custom args:

```bash
make run ARGS="--file examples/example_structure.json --starting-stack 15000 --level-length 30"
```

For scraper support:

```bash
make install-scraping
make scrape-kingsroom   # or scrape-kingslive, scrape-sydney
```

Sydney Champs reads the bundled PDF at
`mtt_structure_evaluator/structure-pdfs/sydney-champs-structures.pdf`
and writes outputs under `structure-scrapes/sydney_champs*`.

## Notes

- Each subproject has its own implementation details and README.
- Run commands from each subproject directory unless noted otherwise.
