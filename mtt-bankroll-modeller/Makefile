.PHONY: install run clean help

help:
	@echo "mtt-bankroll-modeller: make install, make run, make clean"

install:
	uv sync

run:
	uv run streamlit run app.py

clean:
	rm -rf .venv uv.lock
