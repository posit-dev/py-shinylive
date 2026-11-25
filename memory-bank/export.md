---
title: "Export pipeline"
description: "How `shinylive export` turns an app folder into a static site: argument checks, copying assets, reading app files into app.json, copying Pyodide packages, and rendering the export template. Covers `_export.py`, `_app_json.py`, and `_utils.py`."
---

# Export pipeline

`shinylive export APPDIR DESTDIR` (`_main.export`) parses
`--template-params` and calls `_export.export()`.

## `_main.export`

- `--template-params` is a JSON string or a path to a JSON file. If
  `Path(value).is_file()`, the file is read; otherwise the value is parsed as
  JSON. An `OSError` from `is_file()` (a JSON string longer than a file name
  can be, on Python < 3.14) means "not a file".
- When `--assets-version` is not given, `check_env_assets_version()` turns a
  bad `SHINYLIVE_ASSETS_VERSION` into a usage error.

## `_export.export()`

In order:

1. `appdir/app.py` must exist, or `ValueError`.
2. `destdir` must not be `appdir` or hold it, compared with
   `comparable_path()`, or `ValueError`. Otherwise every app folder would be
   skipped as part of the export.
3. `check_subdir()`: `None` and `"."` mean no subdir; an absolute path or one
   with a `..` part is a `ValueError`.
4. `set_assets_version(resolve_assets_version(assets_version_input(assets_version)))`.
   This may use the network and downloads the chosen version if needed. It is
   done after the argument checks so a bad call fails fast.
5. `template_dir` defaults to `<assets>/export_template`; a given one must
   exist.
6. `destdir` is created with `mkdir(parents=True)`.
7. Base files are copied with `create_copy_fn(overwrite=False)`: every file
   from `shinylive_common_files(asset_type=("base", "python"))`.
8. `read_app_files(appdir, destdir)` builds the `AppInfo`.
9. Pyodide wheels are copied into `destdir/shinylive/pyodide/`: either the
   packages from `base_package_deps() + find_package_deps(files)`, or, with
   `full_shinylive=True`, every file in the assets' `shinylive/pyodide/`
   (minus base files). See `pyodidePackages.md`.
10. `write_app_json()` renders the template and writes `app.json`.

All messages go to stderr.

## `read_app_files(appdir, destdir)` (`_app_json.py`)

Walks `appdir` with `os.walk()` and returns a list of
`{"name", "content", "type"}` dicts:

- Skips any folder or file whose name starts with `.`, and folders named
  `__pycache__`, `venv`, or `.venv` (files with those names too).
- Skips (and does not walk into) every folder inside `destdir`, so an export
  inside the app folder is not read back in. Paths are compared with
  `comparable_path()`, so relative and absolute paths can be mixed.
- Sorts folder and file names, and moves `app.py` first, so `app.json` is in
  the same order on every run.
- Reads each file as UTF-8 text; on `UnicodeDecodeError` it reads bytes and
  stores base64 with `"type": "binary"`. Text is read with universal newlines,
  so `\r\n` becomes `\n`.
- Names use `/` (`as_posix()`), relative to `appdir`.
- Warns when it finds `shinylive.js`, which suggests an old export is
  inside the app.

## `write_app_json(app_info, destdir, html_source_dir, template_params)`

- `app_destdir = destdir / subdir`, created with `mkdir(parents=True)`.
- `REL_PATH` is `"../"` once per part of `subdir` (`path_length()`), so the
  pages can find `shinylive/` at the top of `destdir`.
- Template data: `{"title": "Shiny App", **template_params, "REL_PATH": ...,
  "APP_ENGINE": "python"}`. `REL_PATH` and `APP_ENGINE` can't be overridden.
- Every file in the template folder (recursively) is copied to
  `app_destdir`. `.html` files go through `copy_file_and_substitute()`
  (`chevron` mustache); others use `shutil.copyfile()` and are overwritten on
  each export.
- `app.json` is written as UTF-8 with `json.dump()`.

## Helpers (`_utils.py`)

- `create_copy_fn(overwrite, verbose_print)` returns a `copy_fn(src, dst)`.
  When `dst` exists it prints "Source and destination copies differ" (stderr)
  if the contents differ, then skips (or, with `overwrite=True`, replaces).
- `copy_file_and_substitute()` reads and writes UTF-8.
- `path_length()` counts parts of a relative path after `os.path.normpath()`
  (with `\` turned into `/` on Windows).
- `comparable_path()` makes a path absolute, resolves symlinks, and applies
  `os.path.normcase()` (lower case on Windows). Use it only to compare paths,
  never to name files.
- `tar_safe_extractall()` uses `filter="data"` on Python 3.12+ and a manual
  path check before that.

## Pitfalls

- **Keep the app and the export apart.** `destdir` equal to `appdir` or
  holding it is an error. A `destdir` inside `appdir` works (it is left out of
  the app) but is not recommended.
- **Compare paths with `comparable_path()`.** Comparing paths as given breaks
  when one is relative and the other absolute.
- **Always pass `encoding="utf-8"`** when reading or writing text. The default
  encoding on Windows is not UTF-8.
- **Print messages to stderr.** Keep stdout free for output that other tools
  read, like the JSON of the `extension` commands.
- **Text files are read with universal newlines,** so `\r\n` is stored as
  `\n` in `app.json`.
- **Re-export keeps old asset files.** Only a message is printed when they
  differ. Remove `destdir` to pick up new assets.
