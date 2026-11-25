---
title: "Export pipeline"
description: "How `shinylive export` turns an app folder into a static site: argument checks, copying assets, reading app files into app.json, copying Pyodide packages, and rendering the export template. Covers `_export.py`, `_app_json.py`, and `_utils.py`."
---

# Export pipeline

`shinylive export APPDIR DESTDIR` (`_main.export`) parses
`--template-params` and calls `_export.export()`.

## `_main.export`

- `--template-params` is a JSON string or a path to a JSON file. If
  `Path(value).exists()`, the file is read; otherwise the value is parsed as
  JSON.
- When `--assets-version` is not given, `check_env_assets_version()` turns a
  bad `SHINYLIVE_ASSETS_VERSION` into a usage error.

## `_export.export()`

In order:

1. `appdir/app.py` must exist, or `ValueError`.
2. `subdir` (default `""`) must not be absolute. Nothing else is checked.
3. `set_assets_version(resolve_assets_version(assets_version_input(assets_version)))`.
   This may use the network and downloads the chosen version if needed. It is
   done after the argument checks so a bad call fails fast.
4. `template_dir` defaults to `<assets>/export_template`; a given one must
   exist.
5. `destdir` is created with `mkdir()` (no `parents=True`).
6. Base files are copied with `create_copy_fn(overwrite=False)`: every file
   from `shinylive_common_files(asset_type=("base", "python"))`.
7. `read_app_files(appdir, destdir)` builds the `AppInfo`.
8. Pyodide wheels are copied into `destdir/shinylive/pyodide/`: either the
   packages from `base_package_deps() + find_package_deps(files)`, or, with
   `full_shinylive=True`, every file in the assets' `shinylive/pyodide/`
   (minus base files). See `pyodidePackages.md`.
9. `write_app_json()` renders the template and writes `app.json`.

Progress messages go to stderr, except `write_app_json()`'s
"Writing .../app.json: N bytes" and `read_app_files()`'s `shinylive.js`
warning, which go to stdout.

## `read_app_files(appdir, destdir)` (`_app_json.py`)

Walks `appdir` with `os.walk()` and returns a list of
`{"name", "content", "type"}` dicts:

- Skips any folder or file whose name starts with `.`, and folders named
  `__pycache__`, `venv`, or `.venv` (files with those names too).
- Skips every walked folder for which `is_relative_to(root, destdir)` is true,
  so an export inside the app folder is not read back in. The comparison is on
  the paths as given, not resolved.
- Sorts file names within a folder and moves `app.py` first.
- Reads each file as UTF-8 text; on `UnicodeDecodeError` it reads bytes and
  stores base64 with `"type": "binary"`. Text is read with universal newlines,
  so `\r\n` becomes `\n`.
- Names use `/` (`as_posix()`), relative to `appdir`.
- Warns (stdout) when it finds `shinylive.js`, which suggests an old export is
  inside the app.

## `write_app_json(app_info, destdir, html_source_dir, template_params)`

- `app_destdir = destdir / subdir`, created with `mkdir()` (no parents).
- `REL_PATH` is `"../"` once per part of `subdir` (`path_length()`), so the
  pages can find `shinylive/` at the top of `destdir`.
- Template data: `{"title": "Shiny App", **template_params, "REL_PATH": ...,
  "APP_ENGINE": "python"}`. `REL_PATH` and `APP_ENGINE` can't be overridden.
- Every file in the template folder (recursively) is copied to
  `app_destdir`. `.html` files go through `copy_file_and_substitute()`
  (`chevron` mustache); others use `shutil.copyfile()` and are overwritten on
  each export.
- `app.json` is written with `json.dump()`.

## Helpers (`_utils.py`)

- `create_copy_fn(overwrite, verbose_print)` returns a `copy_fn(src, dst)`.
  When `dst` exists it prints "Source and destination copies differ" (stderr)
  if the contents differ, then skips (or, with `overwrite=True`, replaces).
- `copy_file_and_substitute()` reads UTF-8 and writes with the platform
  default encoding.
- `path_length()` counts parts of a relative path after `os.path.normpath()`.
- `tar_safe_extractall()` uses `filter="data"` on Python 3.12+ and a manual
  path check before that.
- `is_relative_to()` is a wrapper kept from when Python 3.8 was supported.

## Pitfalls

- **Keep the app and the export apart.** `export(".", ".")`, or a `destdir`
  that holds the app (`export("myapp", ".")`, `export("site/app", "site")`),
  writes an `app.json` with no files and no error, because every folder is
  inside `destdir`.
- **Mixed relative and absolute paths defeat the `destdir` check.**
  `export("/abs/app", "site")` run from inside the app reads the previous
  export (all of `shinylive/`) into `app.json`.
- **`subdir` is barely checked.** `"../x"` writes outside `destdir`, and a
  nested `subdir` (`"a/b"`) or `destdir` (`"out/site"`) whose parent does not
  exist fails with `FileNotFoundError`.
- **File order in `app.json` is not stable.** `read_app_files()` sets
  `dirs[:]` to a `set`, so sibling folders are walked in hash order, which
  changes between runs.
- **`path_length()` on Windows.** It calls `path.replace("\\", "/")` but drops
  the result, so a Windows `subdir` with more than one part gets too short a
  `REL_PATH`.
- **Platform encodings.** `copy_file_and_substitute()` writes without
  `encoding="utf-8"`, so non-ASCII template params can fail on Windows.
- **Re-export keeps old asset files.** Only a message is printed when they
  differ. Remove `destdir` to pick up new assets.
