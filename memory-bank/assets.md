---
title: "Assets cache and versions"
description: "How the Shinylive web assets are chosen, downloaded, cached, installed from a local build, and removed: version inputs, versions.json, the once-a-day GitHub check, fallbacks, and the `shinylive assets` commands. Covers `_assets.py`, `_assets_version.py`, and `_version/`."
---

# Assets cache and versions

## Where assets live

`shinylive_cache_dir()` is `appdirs.user_cache_dir("shinylive")`. Each
version is a folder `shinylive-<version>/` holding:

- `shinylive/` - the runtime: `shinylive.js`, the service worker loader,
  `pyodide/` (Pyodide plus every package wheel and `pyodide-lock.json`),
  `pyright/`, `webr/` (R only), `examples.json`.
- `shinylive-sw.js` - the service worker.
- `export_template/` - `index.html` and `edit/index.html` mustache templates.
- `scripts/codeblock-to-json.js` - run by Quarto through Deno.

Also in the cache folder: `versions.json`, and temp entries prefixed
`extract-`, `old-`, or `versions-`.

`shinylive_assets_dir(version=None)` is `<cache>/shinylive-<version>`, using
`assets_version()` when `version` is `None`.

## Version inputs (`_assets_version.py`)

`parse_assets_version()` accepts:

- an exact version, `"0.10.16"` (`kind="exact"`);
- a series, `"0.10.*"` (`kind="pattern"`): the highest `0.10.x`;
- `"latest"`: the newest release, checked on GitHub every time.

`assets_version_input(version)` picks the input: a non-`None` argument, then
`SHINYLIVE_ASSETS_VERSION` (an empty value counts as unset), then
`SHINYLIVE_ASSETS_VERSION_DEFAULT`. A bad env var raises a `ValueError` that
names the env var; the CLI turns it into a usage error.

`_version/__init__.py` holds `SHINYLIVE_ASSETS_VERSION_DEFAULT` (the series,
`"0.10.*"`) and `SHINYLIVE_ASSETS_VERSION_FALLBACK` (a known-good exact
version, used when no match is known). The old name
`SHINYLIVE_ASSETS_VERSION` still works through a module `__getattr__` with a
`FutureWarning`.

## `versions.json`

Shared with r-shinylive, same format:

```json
{"checked_at": "2026-11-20T17:03:00Z", "latest": "0.11.0",
 "versions": ["0.11.0", "0.10.17"], "error": "<only when the last check failed>"}
```

- A check is due after 24 hours, or 1 hour after a failed check, or if the
  clock went backwards (`versions_check_due()`).
- `check_versions_info()` reads where `/releases/latest` redirects to (no rate
  limit), and fetches the full release list from the GitHub API only when the
  latest tag changed or the saved list is empty. `GITHUB_PAT` or `GITHUB_TOKEN` is used if set; a 401
  retries without it.
- A failed check keeps the old list and records `error`.
- `write_versions_json()` writes a temp file and renames it. A read-only cache
  is ignored (`save_versions_json()`).

## `resolve_assets_version(version, dir, *, download, check, warn)`

- Exact: returns it, downloading it first if `download=True`; warns once if it
  is outside the default series.
- Series or `"latest"`: reads `versions.json`, runs the check if `check=True`
  (always for `"latest"`), and picks the highest known or downloaded match, or
  the fallback version. With `download=True` it downloads the choice; if that
  fails it uses the highest downloaded match (or downloads the fallback) and
  warns. The new `versions.json` is saved only once the chosen version is
  downloaded, so later commands that only read it never pick a version they
  would have to download.
- Series and `"latest"` results are memoized per `(input, dir, download,
  check)` in `_memo`. Exact versions return before the memo.

`assets_version()` resolves once per process (`_session_version`).
`set_assets_version()` sets it and clears the `_deps.py` caches when it
changes. Tests reset all of this with `_reset()`.

## Downloading (`_assets.py`)

`download_shinylive(destdir, version, url, status)`:

1. Resolves `version` (no download) and builds the GitHub release URL, unless
   `url` is given (a mirror; `version` is then ignored).
2. `_urlretrieve()` streams to a temp file with a 60 second timeout per read.
   Progress goes to stderr once a second.
3. Extracts into `<cache>/extract-*` with `tar_safe_extractall()`, then moves
   each top-level entry into place with `_move_into_place()`. A folder another
   process just made is kept; a re-download moves the old folder aside to
   `old-*` first, then deletes it.

`ensure_shinylive_assets(destdir, version, url)` resolves the version
(downloading from GitHub unless `url` is set), downloads from `url` if the
folder is missing, and returns the folder. With `url` and a series, the
tarball may hold any matching version.

## Local builds

`shinylive assets install-from-local BUILD` (`copy_shinylive_local()`) and
`link-from-local BUILD` (`link_shinylive_local()`) put a local shinylive build
into the cache as `shinylive-<version>`. The version defaults to the one in the
`package.json` of `BUILD` or its parent (`local_build_version()`); a given
`--version` must be exact. To use it, set `SHINYLIVE_ASSETS_VERSION` to that
version. A local build is treated like any other installed version.

## Cleanup and info

- `cleanup_shinylive_assets(dir, keep)` keeps exact matches and the newest
  downloaded match of each series (default: the default series and
  `SHINYLIVE_ASSETS_VERSION`), removes the rest, and removes temp entries
  older than 10 minutes (`remove_stale_temp_files()`).
- `remove_shinylive_assets(dir, version)` removes given versions.
- `print_shinylive_local_info()` reports the version in use (from
  `versions.json`, no network), the last check, and installed versions.
- `local_assets_versions(dir)` lists `shinylive-<version>` folders whose name
  is a valid version, newest first. Other `shinylive-*` entries are ignored.

## Pitfalls

- **The cache is shared with r-shinylive.** Folder names, `versions.json`, and
  the temp prefixes must stay the same in both packages. Changes must be
  released in both at about the same time.
- **Check inputs before removing anything.** `copy_shinylive_local()` and
  `link_shinylive_local()` check that `BUILD` is a folder before they remove
  the old `shinylive-<version>`.
- **A server may send no size.** Mirrors may leave out `Content-Length`, so
  `_urlretrieve()` passes `-1` and the progress line shows only the MB so far.
- **Tests must not touch your real cache.** Monkeypatch
  `assets.shinylive_cache_dir` and call `_assets_version._reset()`; see the
  `offline` fixture in `tests/test_assets_version.py`.
