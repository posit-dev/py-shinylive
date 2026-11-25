---
title: "CI, release, and tooling"
description: "GitHub Actions workflows (build and test, PyPI release, the reusable deploy-app workflow and its actions/v1 tag), the Makefile, packaging in pyproject.toml, linting and typing config, and the CHANGELOG."
---

# CI, release, and tooling

## Workflows (`.github/workflows/`)

- `build.yml` - on push to `main`/`rc-*`, pull requests, releases, and manual
  runs. Tests Python 3.10 to 3.14 with uv: `uv sync`, `make install` (builds
  a wheel and installs it over the editable copy), `make install-deps` (`uv sync`), `make test`, `make check`.
  The job sets `UV_NO_SYNC=1` so `uv run` does not put the editable copy back.
  On a published release, the `deploy` job builds with `make dist` and
  publishes to PyPI: to TestPyPI if the release name starts with `TEST`, to
  PyPI if it starts with `shinylive`.
- `deploy-app.yaml` - a reusable (`workflow_call`) workflow for users. It runs
  `uvx --from <shinylive-version> shinylive export <app-dir> site` and, only on
  `refs/heads/main`, uploads and deploys to GitHub Pages. Inputs:
  `python-version`, `shinylive-version`, `app-dir`.
- `test-deploy-app.yaml` - on pull requests, runs `deploy-app.yaml` from this
  branch on `tests/app` with `shinylive-version: "."`. It never deploys,
  because the ref is not `main`.

## `examples/` and the `actions/v1` tag

`examples/deploy-app.yaml` is the file users copy. It calls
`posit-dev/py-shinylive/.github/workflows/deploy-app.yaml@actions/v1`. The
README tells users to `curl` it from the `actions/v1` tag. After changing
`deploy-app.yaml` or `examples/`, move the tag:

```bash
git tag -f actions/v1
git push --force origin refs/tags/actions/v1
```

## Makefile

`make install-deps` (`uv sync`), `make test`, `make check` (`pyright`, `lint`,
`ruff format --check`), `make lint` (`ruff check`), `make format` (`ruff check
--fix` and `ruff format`), `make dist` (`uv build`), `make install`,
`make coverage`, `make clean`.

## Packaging (`pyproject.toml`)

- The build backend is hatchling.
- Version comes from `SHINYLIVE_PACKAGE_VERSION` in
  `shinylive/_version/__init__.py` (read by a regex in `[tool.hatch.version]`).
- The wheel holds only the `shinylive` package, including `py.typed`. The
  sdist adds `tests/`, `CHANGELOG.md`, `README.md`, and `LICENSE`, so
  `memory-bank/`, `.agents/`, and `AGENTS.md` are in neither.
- The `shinylive` console script is `shinylive._main:main`.
- Dev tools are in the `dev` dependency group (`[dependency-groups]`), not in
  extras, so they are not part of the published package metadata.
- ruff settings are in `pyproject.toml`: rules `E`, `F`, `I` (imports), and
  `B` (bugbear, carried over from flake8-bugbear), with `E501` (line length)
  off because `ruff format` already wraps code. pyright settings are in `pyrightconfig.json` (strict).

## CHANGELOG

Add a bullet under `## [UNRELEASED]` in `CHANGELOG.md` for any user-facing
change. A release renames it to the version and date.

## Pitfalls

- **Move the `actions/v1` tag for changes in `examples/` too.** Users `curl`
  `examples/deploy-app.yaml` from the tag.
- **The "On push events" comment in `deploy-app.yaml` is out of date** (it
  deploys on `main` for any event). It is left as is so the tag need not move
  for a comment.
- **Every Makefile tool runs through `uv run`,** which installs the `dev`
  dependency group into `.venv` first. No activated environment is needed.
- **`uv.lock` is not committed** (see `.gitignore`), so CI tests against the
  newest versions of dependencies, as users get them.
- **Asset tests only run in CI on a release** (see `testing.md`), so a broken
  asset test shows up at release time.
