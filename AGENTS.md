# AGENTS.md

This file gives guidance to coding agents working in this repository.

## Project overview

`shinylive` is a Python package that exports Shiny for Python apps to static
sites that run entirely in the browser through
[Pyodide](https://pyodide.org/). It has a `shinylive` command line with these
parts:

- **Export** (`shinylive export`): copy the Shinylive web assets, the app files
  (as `app.json`), and the Pyodide packages the app imports into a folder that
  any static web server can host.
- **Assets** (`shinylive assets ...`): download, cache, and manage versions of
  the Shinylive web assets from
  [posit-dev/shinylive](https://github.com/posit-dev/shinylive) releases.
- **Quarto** (`shinylive extension ...`): commands called by the
  [quarto-ext/shinylive](https://github.com/quarto-ext/shinylive) extension.
  They print JSON to stdout, so nothing else may be printed to stdout.
- **URL** (`shinylive url ...`): create and decode shinylive.io URLs.

## Development commands

```sh
pip install -e ".[dev,test]"
make test     # pytest
make check    # pyright, flake8, black --check, isort --check
black . && isort .
```

Some tests need the assets (a large download) and are skipped in CI unless the
run is for a release.

## Conventions

- **CHANGELOG:** add a bullet to `CHANGELOG.md` under `[UNRELEASED]` for any
  user-facing change.
- **Messages:** print progress messages to stderr, never to stdout, because
  the Quarto extension reads stdout as JSON.

## Keep r-shinylive in sync

[posit-dev/r-shinylive](https://github.com/posit-dev/r-shinylive) is the R
version of this package. The two packages share:

- the `extension` commands and the JSON they print, used by
  quarto-ext/shinylive for both `shinylive-python` and `shinylive-r` blocks;
- the assets cache folder, its `shinylive-<version>` folders, and its
  `versions.json` file;
- how the assets version is chosen: the `SHINYLIVE_ASSETS_VERSION`
  environment variable, and exact versions, series (`0.10.*`), and `latest`.

When you add a feature or fix a bug, check whether r-shinylive needs the same
change. Skip this for changes that only apply to Python, such as finding the
Pyodide packages an app imports. If r-shinylive needs it:

- Open an issue in posit-dev/r-shinylive that links to your PR and says what
  to change. Or open the r-shinylive PR yourself.
- Link that issue or PR in your PR's description.

Changes to the shared items above must be released in both packages at about
the same time. Otherwise, a Quarto document with both `shinylive-python` and
`shinylive-r` blocks can fail to render.
