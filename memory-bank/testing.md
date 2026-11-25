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
| `tests/test_deps.py` | `requirements.txt` parsing; module/name/key mapping and dependency lists | Yes, except `test_requirements_txt` |
| `tests/test_url.py` | Encoding and decoding shinylive.io links | No |
| `tests/test_assets.py` | `_check_assets_url()` for the fallback version | Network |

`tests/app/` is a fixture app for the deploy-app workflow test; pytest and
pyright ignore it.

## Tests that need assets

`tests/test_deps.py` and `tests/test_assets.py` define
`skip_if_not_release`: they are skipped when `CI=true` and the GitHub event is
not `release`. Locally they always run, so they use your real cache and
download the assets on first run (hundreds of MB). In CI they run only for a
release.

## Offline testing of versions and downloads

`tests/test_assets_version.py` has an autouse `offline` fixture that:

- points `assets.shinylive_cache_dir` at `tmp_path`;
- calls `_assets_version._reset()` (memo, warnings, session version);
- replaces `fetch_latest_assets_version`, `fetch_assets_versions`, and
  `download_shinylive` with fakes that record calls (`Calls`).

Helpers: `fake_github()` sets the latest tag and list; `write_info()` writes a
`versions.json`; the `real_download` fixture runs the real
`download_shinylive()` against a local tarball (`make_bundle()`) by patching
`_urlretrieve`. Extension commands are run with `click.testing.CliRunner`.

Use these for any new test that touches the assets cache, so it never uses the
network or your real cache.

## Pitfalls

- **Export, `_app_json.py`, and `_utils.py` have no tests.** Write tests for
  them with a fake assets folder (or the offline fixture plus a small
  `shinylive-<version>` tree) rather than the real assets.
- **`SHINYLIVE_ASSETS_VERSION` in your shell** changes which assets the
  asset tests use. Unset it, or set it on purpose.
- **Asset tests can break on new assets.** `test_find_recursive_deps` asserts
  exact Pyodide dependency lists.
- **`click` output in tests.** `CliRunner` mixes stderr into `result.output`
  unless you read `result.stdout`; Quarto commands must keep stdout to JSON.
