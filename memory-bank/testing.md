---
title: "Testing"
description: "How the pytest suite is laid out, which tests need the downloaded assets or the network and when they run, and how to test asset version logic offline with monkeypatching."
---

# Testing

Run `make test` (or `pytest`). `make check` runs pyright (strict), flake8,
black, and isort.

## Layout

| File | Covers | Needs assets |
|---|---|---|
| `tests/test_assets_version.py` | Version inputs, `versions.json`, resolving, downloads, cleanup, extension commands | No; fully offline |
| `tests/test_deps.py` | `requirements.txt` parsing; module/name/key mapping and dependency lists | Only the `skip_if_not_release` tests |
| `tests/test_url.py` | Encoding and decoding shinylive.io links; `ShinyliveApp` files | No |
| `tests/test_export.py` | `export()`, `read_app_files()`, `path_length()` | Uses `fake_assets` |
| `tests/test_cli.py` | `shinylive` CLI options and help | Uses `fake_assets` |
| `tests/test_assets.py` | The release's assets URL (one release-only test uses the network); local builds; download progress | Mostly no |

`tests/app/` is a fixture app for the deploy-app workflow test; pytest and
pyright ignore it.

## Tests that need assets

`tests/test_deps.py` and `tests/test_assets.py` define
`skip_if_not_release` for the tests that use the real assets or network: they are skipped when `CI=true` and the GitHub event is
not `release`. Locally they always run, so they use your real cache and
download the assets on first run (hundreds of MB). In CI they run only for a
release.

## The `fake_assets` fixture

`tests/conftest.py` has a `fake_assets` fixture: a tiny
`shinylive-<fallback>` folder in a temp cache, with the folders that
`shinylive_common_files()` expects, an `export_template/`, and a
`pyodide-lock.json` with three packages (`micropip`, which depends on
`packaging`, and `numpy`). It sets `SHINYLIVE_ASSETS_VERSION`, points
`shinylive_cache_dir` at the temp cache, and resets the version and Pyodide
caches. Use it to test export and package code with no network.
`make_app()` and `app_json_names()` help build and check apps.

## Offline testing of versions and downloads

`tests/test_assets_version.py` has an autouse `offline` fixture that:

- points `assets.shinylive_cache_dir` at `tmp_path`;
- calls `_assets_version._reset()` (memo, warnings, session version);
- replaces `fetch_latest_assets_version` and `fetch_assets_versions` with
  fakes that raise `AssertionError("network used")`; call `fake_github()` to
  give them data;
- replaces `download_shinylive` with a fake that records each version in
  `calls.downloads` (`Calls`).

Helpers: `fake_github()` sets the latest tag and list; `write_info()` writes a
`versions.json`; the `real_download` fixture runs the real
`download_shinylive()` against a local tarball (`make_bundle()`) by patching
`_urlretrieve`. Extension commands are run with `click.testing.CliRunner`.

Use these for any new test that touches the assets cache, so it never uses the
network or your real cache.

## Pitfalls

- **Prefer `fake_assets` to the real assets.** Tests on the real assets only
  run in CI on a release.
- **Hash order.** Run new tests that check order with a few
  `PYTHONHASHSEED` values; `set` order changes between runs.
- **`SHINYLIVE_ASSETS_VERSION` in your shell** changes which assets the
  asset tests use. Unset it, or set it on purpose.
- **Asset tests can break on new assets.** `test_find_recursive_deps` asserts
  exact Pyodide dependency lists.
- **`click` output in tests.** `CliRunner` mixes stderr into `result.output`
  unless you read `result.stdout`; Quarto commands must keep stdout to JSON.
