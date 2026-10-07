# flybrain-connectome — developer entry points.
#
# Every target here maps to something a new contributor will actually run.
# `make help` prints this table.

PYTHON ?= python
VENV   ?= .venv
PIP    := $(PYTHON) -m pip
PY     := $(VENV)/bin/python
PYL    := $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_/-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Create a Python 3.12+ venv and install dev deps
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"

.PHONY: install
install: ## Install the package (non-editable, with provenance)
	$(PIP) install ".[prov]"

.PHONY: install-editable
install-editable: ## Editable install pointing at this checkout
	$(PIP) install -e ".[prov,dev]"

.PHONY: lint
lint: ## Run ruff (lint) and black --check (formatting)
	$(PIP) show ruff  >/dev/null 2>&1 || $(PIP) install ruff black
	ruff check .
	black --check --diff .

.PHONY: format
format: ## Apply ruff --fix and black
	$(PIP) show ruff >/dev/null 2>&1 || $(PIP) install ruff black
	ruff check --fix .
	black .

.PHONY: typecheck
typecheck: ## Run mypy on the shipped code paths
	$(PIP) show mypy >/dev/null 2>&1 || $(PIP) install mypy
	mypy flybrain_cli.py flybrain-connectome-mcp scripts

.PHONY: test
test: ## Run pytest with coverage
	$(PIP) show pytest >/dev/null 2>&1 || $(PIP) install pytest pytest-cov
	pytest --cov --cov-report=term-missing

.PHONY: gates
gates: ## Run every repo gate (offline, CI-equivalent)
	$(PYTHON) scripts/run_gates.py

.PHONY: gates-data
gates-data: ## Run every gate + the data-backed smoke test (needs FLYBRAIN_DATA_DIR)
	$(PYTHON) scripts/run_gates.py --with-data

.PHONY: smoke
smoke: ## Generate a smoke organism into ./_smoke_out/
	$(PYTHON) flybrain_cli.py generate \
		--motif-source local \
		--blueprint predictive_coding_v2 \
		--modules 3 --agents-per-module 4 \
		--name smoke --out _smoke_out --no-html

.PHONY: mcp
mcp: ## Launch the MCP stdio server (used by MCP-capable clients)
	$(PYTHON) -m flybrain-connectome-mcp.mcp_connectome.server

.PHONY: api
api: ## Launch the HTTP API on :8799
	$(PYTHON) flybrain-connectome-mcp/run_api.py

.PHONY: build
build: ## Build the sdist + wheel into dist/
	$(PIP) show build >/dev/null 2>&1 || $(PIP) install build
	rm -rf dist/ build/ *.egg-info
	python -m build

.PHONY: publish
publish: ## Publish to PyPI (or --dry-run via TWINE_REPOSITORY_URL)
	$(PIP) show twine >/dev/null 2>&1 || $(PIP) install twine
	twine check dist/*
	twine upload dist/*

.PHONY: clean
clean: ## Remove build artifacts and caches (does not touch archive/)
	rm -rf build/ dist/ *.egg-info _smoke_out/
	find . -type d -name __pycache__ -not -path "./archive/*" -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -not -path "./archive/*" -prune -exec rm -rf {} +

.PHONY: verify-commit
verify-commit: ## Verify current commit's gates offline (for CI dry-runs)
	$(PYTHON) scripts/run_gates.py
