.PHONY: help setup test test-coverage lint format clean install-dev install docs serve-docs

# Default target
help:
	@echo "Available targets:"
	@echo "  setup         - Create virtual environment and install all dependencies"
	@echo "  install       - Install ebk package in current environment"
	@echo "  install-dev   - Install ebk with development dependencies"
	@echo "  test          - Run all tests"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  lint          - Run linting checks"
	@echo "  format        - Format code with black"
	@echo "  clean         - Remove build artifacts and virtual environment"
	@echo "  docs          - Build documentation"
	@echo "  serve-docs    - Serve documentation locally"

# Python interpreter
PYTHON := python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

# Create virtual environment
$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip setuptools wheel

# Setup development environment
setup: $(VENV)/bin/activate
	$(VENV_PIP) install -e ".[dev,all]"
	@echo "✅ Development environment ready! Activate with: source $(VENV)/bin/activate"

# Install package
install: $(VENV)/bin/activate
	$(VENV_PIP) install -e .

# Install with development dependencies
install-dev: $(VENV)/bin/activate
	$(VENV_PIP) install -e ".[dev]"

# Run tests
test: $(VENV)/bin/activate
	$(VENV_PYTHON) -m pytest tests/ -v

# Run tests with coverage
test-coverage: $(VENV)/bin/activate
	$(VENV_PYTHON) -m pytest tests/ -v --cov=ebk --cov-report=html --cov-report=term
	@echo "📊 Coverage report generated in htmlcov/index.html"

# Run specific test file
test-file: $(VENV)/bin/activate
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make test-file FILE=tests/test_library_api.py"; \
	else \
		$(VENV_PYTHON) -m pytest $(FILE) -v; \
	fi

# Run linting
lint: $(VENV)/bin/activate
	$(VENV_PYTHON) -m flake8 ebk/ tests/ --max-line-length=100 --exclude=$(VENV)
	$(VENV_PYTHON) -m mypy ebk/ --ignore-missing-imports
	$(VENV_PYTHON) -m pylint ebk/ --disable=C0114,C0115,C0116,R0903,R0913

# Format code
format: $(VENV)/bin/activate
	$(VENV_PYTHON) -m black ebk/ tests/
	$(VENV_PYTHON) -m isort ebk/ tests/

# Check formatting without applying
format-check: $(VENV)/bin/activate
	$(VENV_PYTHON) -m black --check ebk/ tests/
	$(VENV_PYTHON) -m isort --check-only ebk/ tests/

# Clean build artifacts
clean:
	rm -rf $(VENV)
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build documentation
docs: $(VENV)/bin/activate
	$(VENV_PYTHON) -m mkdocs build

# Serve documentation locally
serve-docs: $(VENV)/bin/activate
	$(VENV_PYTHON) -m mkdocs serve

# Build package
build: $(VENV)/bin/activate clean
	$(VENV_PYTHON) -m build

# Upload to PyPI
upload: build
	$(VENV_PYTHON) -m twine upload dist/*

# Upload to Test PyPI
upload-test: build
	$(VENV_PYTHON) -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Run the CLI
run: $(VENV)/bin/activate
	$(VENV_PYTHON) -m ebk $(ARGS)

# Run specific CLI command
ebk: $(VENV)/bin/activate
	@$(VENV_PYTHON) -m ebk $(filter-out $@,$(MAKECMDGOALS))

# Catch-all target to allow passing arguments to ebk
%:
	@:

# Development shortcuts
.PHONY: dev
dev: setup
	@echo "🚀 Starting development environment..."
	@echo "Run 'source $(VENV)/bin/activate' to activate the virtual environment"

# Quick test for CI
.PHONY: ci
ci: setup lint format-check test-coverage

# Install pre-commit hooks
.PHONY: pre-commit
pre-commit: $(VENV)/bin/activate
	$(VENV_PIP) install pre-commit
	$(VENV_PYTHON) -m pre_commit install