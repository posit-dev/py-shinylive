---
title: "CI, release, and tooling"
description: "GitHub Actions workflows (build and test, PyPI release, the reusable deploy-app workflow and its actions/v1 tag), the Makefile, packaging in setup.cfg, linting and typing config, and the CHANGELOG."
---

# CI, release, and tooling

## Workflows (`.github/workflows/`)

- `build.yml` - on push to `main`/`rc-*`, pull requests, releases, and manual
  runs. Tests Python 3.10 to 3.14: `pip install -e ".[dev,test]"`,
  `make install` (builds a wheel and installs it), `make test`, `make check`.
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

`make test`, `make check` (`pyright`, `lint`, `black --check`,
`isort --check-only`), `make lint` (flake8 on `shinylive` and `tests`),
`make dist` (`setup.py sdist` and `bdist_wheel`), `make install`,
`make clean`.

## Packaging (`setup.cfg`)

- Version comes from `shinylive._version.SHINYLIVE_PACKAGE_VERSION`.
- Only `shinylive` and `shinylive.*` are packaged, plus `py.typed`. There is
  no `MANIFEST.in`, so `memory-bank/`, `.agents/`, and `AGENTS.md` are not in
  the sdist or wheel.
- The `shinylive` console script is `shinylive._main:main`.
- flake8 and isort settings are here; pyright settings are in
  `pyrightconfig.json` (strict).

## CHANGELOG

Add a bullet under `## [UNRELEASED]` in `CHANGELOG.md` for any user-facing
change. A release renames it to the version and date.

## Pitfalls

- **`examples/README.md` says the tag does not need to move for changes in
  `examples/`.** It does: users `curl` `examples/deploy-app.yaml` from the
  tag.
- **`make test-all` and `make coverage` don't work as is.** There is no tox
  config, and `coverage` is not a dev dependency.
- **`setup.cfg` has deprecated keys**: `license_file`, `tests_require`,
  `test_suite`, and `setup_requires`.
- **Asset tests only run in CI on a release** (see `testing.md`), so a broken
  asset test shows up at release time.
