.PHONY: clean clean-test clean-pyc clean-build docs help
.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

BROWSER := python3 -c "$$BROWSER_PYSCRIPT"

help:
	@python3 -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -rf typings/

install-deps: ## install the package and dev tools into .venv
	uv sync

pyright: ## type check with pyright
	uv run pyright

check: pyright lint ## check code quality with pyright, flake8, black and isort
	echo "Checking code with black."
	uv run black --check .
	echo "Sorting imports with isort."
	uv run isort --check-only --diff .

lint: ## check style with flake8
	uv run flake8 --show-source --max-line-length=127 shinylive tests

test: ## run tests quickly with the default Python
	uv run pytest

coverage: ## check code coverage quickly with the default Python
	uv run coverage run --source shinylive -m pytest
	uv run coverage report -m
	uv run coverage html
	$(BROWSER) htmlcov/index.html

release: dist ## package and upload a release
	uv publish

dist: clean ## builds source and wheel package
	uv build
	ls -l dist

## install the built wheel into .venv, replacing the editable install.
## Run later commands with UV_NO_SYNC=1, or `uv run` reinstalls the editable copy.
install: dist
	uv pip install --reinstall dist/shinylive*.whl
