.PHONY: help install test test-quick test-unit test-integration test-coverage lint format clean docs build

# Default target
help:  ## Show this help message
	@echo "CloudBuccaneer Development Commands"
	@echo "=================================="
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install package and dependencies
	pip install -e .
	pip install pytest pytest-cov pytest-mock pytest-xdist pytest-html flake8 black isort

install-dev:  ## Install with all development dependencies
	pip install -e .[test]
	pip install flake8 black isort mypy safety bandit

test:  ## Run all tests
	python run_tests.py

test-quick:  ## Run quick tests (unit tests without coverage)
	python run_tests.py --quick

test-unit:  ## Run only unit tests
	python run_tests.py --unit-only

test-integration:  ## Run only integration tests
	python run_tests.py --integration-only

test-coverage:  ## Run tests with coverage report
	pytest --cov=cb --cov-report=html --cov-report=term-missing tests/

test-parallel:  ## Run tests in parallel
	pytest -n auto tests/

test-verbose:  ## Run tests with verbose output
	python run_tests.py --verbose

test-report:  ## Generate HTML test report
	python run_tests.py --report

smoke-test:  ## Run basic smoke tests
	python -c "from cb.cli import app; print('✅ CLI import successful')"
	python -m cb.cli --help

lint:  ## Run code linting
	flake8 src/cb --max-line-length=100 --ignore=E203,W503

format:  ## Format code with black and isort
	black src/cb tests/
	isort src/cb tests/

format-check:  ## Check code formatting
	black --check src/cb tests/
	isort --check-only src/cb tests/

type-check:  ## Run type checking
	mypy src/cb --ignore-missing-imports

security:  ## Run security checks
	safety check
	bandit -r src/cb

clean:  ## Clean build artifacts and cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf test_report.html
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docs:  ## Generate documentation
	@echo "Documentation generation not implemented yet"

build:  ## Build package
	python -m build

build-check:  ## Check built package
	python -m build
	twine check dist/*

# Testing specific modules
test-utils:  ## Test utils module
	pytest tests/test_utils.py -v

test-renamer:  ## Test renamer module
	pytest tests/test_renamer.py -v

test-cli:  ## Test CLI module
	pytest tests/test_cli.py -v

test-ytwrap:  ## Test ytwrap module
	pytest tests/test_ytwrap.py -v

test-spotwrap:  ## Test spotwrap module
	pytest tests/test_spotwrap.py -v

# Development workflow commands
dev-setup:  ## Set up development environment
	$(MAKE) install-dev
	pre-commit install

pre-commit:  ## Run pre-commit checks
	$(MAKE) format-check
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test-quick

ci-local:  ## Run CI checks locally
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) security
	$(MAKE) test
	$(MAKE) build-check

# File-specific tests for debugging
test-file:  ## Run tests for a specific file (usage: make test-file FILE=test_utils.py)
	pytest tests/$(FILE) -v

debug-test:  ## Run specific test with debugging (usage: make debug-test TEST=test_function)
	pytest -v -s --pdb -k $(TEST)

# Performance and stress testing
stress-test:  ## Run stress tests with large datasets
	pytest tests/test_integration.py::TestConcurrencyAndResourceManagement -v

performance-test:  ## Run performance-focused tests
	pytest tests/ -k "large" -v

# Validation commands
validate-install:  ## Validate package can be installed and basic commands work
	pip install dist/*.whl --force-reinstall
	cb --help
	cb fetch --help
	cb rename --help

validate-uninstall:  ## Test package uninstallation
	pip uninstall cloudbuccaneer -y

# Git workflow helpers
test-branch:  ## Test current branch thoroughly before merge
	$(MAKE) clean
	$(MAKE) ci-local
	@echo "✅ Branch validation complete"

pre-push:  ## Run checks before pushing
	$(MAKE) test
	$(MAKE) lint
	$(MAKE) security
	@echo "✅ Ready to push"
