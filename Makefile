.PHONY: install bankroll structure help

help:
	@echo "MTT Tooling - available targets:"
	@echo ""
	@echo "  make install      - Install both projects (uv sync in each)"
	@echo "  make bankroll    - Run mtt-bankroll-modeller (Streamlit)"
	@echo "  make structure   - Run mtt-structure-evaluator CLI (use: make structure ARGS='--file path/to.json')"
	@echo ""
	@echo "Or cd into mtt-bankroll-modeller/ or mtt-structure-evaluator/ and run 'make help' for project-specific targets."

install:
	cd mtt-bankroll-modeller && uv sync
	cd mtt-structure-evaluator && uv sync

bankroll:
	cd mtt-bankroll-modeller && make run

structure:
	cd mtt-structure-evaluator && make run ARGS="$(ARGS)"
