.DEFAULT_GOAL := help

.PHONY: help
help: ## show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## install the package, dev tools, and pre-commit hooks
	@echo "📦 Installing the package and dev tools into .venv"
	uv sync --upgrade
	@echo "🪝 Installing pre-commit hooks"
	uv run pre-commit install

.PHONY: check
check: pyrefly lint ## check types, style, and formatting
	@echo "📐 Checking format with ruff"
	uv run ruff format --check .

.PHONY: pyrefly
pyrefly: ## check types with pyrefly
	@echo "📝 Checking types with pyrefly"
	uv run pyrefly check

.PHONY: lint
lint: ## check style and import order with ruff
	@echo "🔍 Checking style with ruff"
	uv run ruff check .

.PHONY: format
format: ## format code and sort imports with ruff
	@echo "🎨 Formatting code with ruff"
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: test
test: ## run tests with the default Python
	@echo "🧪 Running tests with pytest"
	uv run pytest

.PHONY: test-all
test-all: ## run tests on the built wheel with Python 3.10 to 3.14 (tox)
	@echo "🔄 Running tests with tox on Python 3.10 to 3.14"
	uv run tox run-parallel

.PHONY: coverage
coverage: ## measure test coverage and open the report
	@echo "📊 Measuring test coverage"
	uv run coverage run --source shinylive -m pytest
	uv run coverage report -m
	uv run coverage html
	uv run python -m webbrowser "file://$(CURDIR)/htmlcov/index.html"

.PHONY: dist
dist: clean ## build the sdist and wheel
	@echo "🧳 Building the package"
	uv build
	ls -l dist

.PHONY: install
install: dist ## install the built wheel into .venv (the next `uv run` restores the editable install)
	@echo "📥 Installing the built wheel"
	uv pip install --reinstall dist/shinylive*.whl

.PHONY: release
release: dist ## build and upload a release to PyPI
	@echo "🚢 Publishing to PyPI"
	uv publish

.PHONY: clean
clean: clean-build clean-pyc clean-test ## remove build, test, coverage, and Python artifacts

.PHONY: clean-build
clean-build:
	@echo "🧹 Removing build artifacts"
	rm -fr build/ dist/ .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc:
	@echo "🧹 Removing Python artifacts"
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test:
	@echo "🧹 Removing test and coverage artifacts"
	rm -fr .tox/ .coverage htmlcov/ .pytest_cache typings/
