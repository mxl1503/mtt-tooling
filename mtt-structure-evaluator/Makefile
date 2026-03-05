.PHONY: install install-scraping run run-example scrape-kingsroom scrape-kingslive scrape-sydney clean help

help:
	@echo "mtt-structure-evaluator:"
	@echo "  install, install-scraping, run, run-example"
	@echo "  scrape-kingsroom, scrape-kingslive, scrape-sydney"
	@echo "  clean"

install:
	uv sync

install-scraping:
	uv sync --extra scraping

run:
	uv run python -m mtt_structure_evaluator.cli $(ARGS)

run-example:
	uv run python -m mtt_structure_evaluator.cli --file examples/example_structure.json --starting-stack 15000 --level-length 30

scrape-kingsroom: install-scraping
	uv run python structure-scrapers/kingsroom_scraper.py

scrape-kingslive: install-scraping
	uv run python structure-scrapers/kingslive_scraper.py

scrape-sydney: install-scraping
	uv run python structure-scrapers/sydney_champs_scraper.py

clean:
	rm -rf .venv uv.lock build dist *.egg-info
