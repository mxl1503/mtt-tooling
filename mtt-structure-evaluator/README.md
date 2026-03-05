# MTT Structure Evaluator

Small Python 3.11 CLI tool to compute **S-Points** for a tournament blind structure.

## Project layout

```text
mtt-structure-evaluator/
  README.md
  pyproject.toml
  mtt_structure_evaluator/
    __init__.py
    s_points.py
    cli.py
    scraping.py
    pdf_scraping.py
    structure-pdfs/
      sydney-champs-structures.pdf
  examples/
    example_structure.json
  structure-scrapers/
    kingsroom_scraper.py
    kingslive_scraper.py
    sydney_champs_scraper.py
  structure-scrapes/
```

## S-Points definition

- Orbit Cost (per level) = `Small Blind + Big Blind + Big Blind Ante`
- Starting Stack Minutes:
  - Count affordable levels from level 1 upward.
  - A level is affordable when `OrbitCost(level) <= starting_stack`.
  - Stop at the first non-affordable level.
  - `StartingStackMinutes = affordable_levels_count * level_length_minutes`
- S-Points:

```text
S-Points = StartingStackMinutes / (
    Level10OrbitCost / Level6OrbitCost
  + Level14OrbitCost / Level10OrbitCost
  + Level18OrbitCost / Level14OrbitCost
)
```

If required levels `6, 10, 14, 18` are missing, or a denominator divisor level cost is zero (`L6`, `L10`, `L14`), the tool returns `null` for S-Points and exits non-zero with an error.

## Input format

The CLI accepts `.json` or `.csv` structure files.

### JSON example shape

```json
{
  "starting_stack": 15000,
  "level_length_minutes": 30,
  "levels": [
    {"level": 1, "sb": 25, "bb": 50, "bba": 50},
    {"level": 2, "sb": 50, "bb": 100, "bba": 100}
  ]
}
```

Each level may provide either:
- `sb`, `bb`, `bba` (preferred, used when all are present), or
- `orbit_cost`

## CLI usage

From the `mtt-structure-evaluator/` directory:

```bash
make install
make run-example
```

Or with custom args:

```bash
make run ARGS="--file examples/example_structure.json --starting-stack 15000 --level-length 30"
```

You can omit `--starting-stack` and `--level-length` if those values are present in the file.

Requires [uv](https://docs.astral.sh/uv/).

## Scrapers (no manual CSV)

Manual CSV conversion is no longer needed. The scraper flow writes:
- A run summary JSON (all tournaments + computed S-Points where possible)
- Per-tournament structure JSON files in calculator-ready format (`starting_stack`, `level_length_minutes`, `levels`)

### Install scraping dependency

```bash
make install-scraping
```

### Run kingsroom scraper

```bash
make scrape-kingsroom
```

Default outputs:
- `structure-scrapes/kingsroom_tournaments.json`
- `structure-scrapes/kingsroom/*.json` (one structure file per tournament)

### Run kingslive scraper

```bash
make scrape-kingslive
```

Default outputs:
- `structure-scrapes/kingslive_tournaments.json`
- `structure-scrapes/kingslive/*.json`

### Run Sydney Champs PDF scraper

```bash
make scrape-sydney
```

Default outputs:
- `structure-scrapes/sydney_champs_tournaments.json`
- `structure-scrapes/sydney_champs/*.json`

Optional OCR fallback support (for low-text pages):

```bash
uv add pytesseract pdf2image pillow
```

System tools may also be required:
- macOS: `brew install tesseract poppler`
- Linux: install equivalent `tesseract-ocr` and `poppler-utils` packages

### Evaluate a scraped tournament file

```bash
make run ARGS="--file structure-scrapes/<source>/<tournament-slug>.json"
```

Selenium scrapers support `--help`, `--output`, `--structures-dir`, `--timeout`, and `--limit`.
The Sydney Champs PDF scraper supports `--help`, `--pdf`, `--output`, `--structures-dir`, `--no-ocr`, and `--ocr-dpi`.

## One-time walkthrough with included example

### 1) Orbit Cost example (Level 6)

In `examples/example_structure.json`, level 6 has:
- `SB=150`
- `BB=300`
- `BBA=300`

So:

```text
OrbitCost(level 6) = 150 + 300 + 300 = 750
```

### 2) Starting Stack Minutes example

Using:
- `starting_stack = 15000`
- `level_length_minutes = 30`

From the example structure:
- `OrbitCost(level 16) = 11000` (affordable)
- `OrbitCost(level 17) = 19000` (not affordable)

So affordable levels are 1 through 16:

```text
affordable_levels_count = 16
StartingStackMinutes = 16 * 30 = 480
```

### 3) S-Points calculation with actual example numbers

Reference orbit costs from the file:
- `Level 6 = 750`
- `Level 10 = 2500`
- `Level 14 = 6000`
- `Level 18 = 25000`

Denominator:

```text
(2500/750) + (6000/2500) + (25000/6000)
= 3.333333 + 2.400000 + 4.166667
= 9.900000
```

Final S-Points:

```text
S-Points = 480 / 9.9 = 48.48
```

## Expected output fields

The CLI prints:
- `affordable_levels_count`
- `starting_stack_minutes`
- `orbit_cost_level_6`
- `orbit_cost_level_10`
- `orbit_cost_level_14`
- `orbit_cost_level_18`
- `denominator`
- `s_points` (rounded to 2 decimals when available)
