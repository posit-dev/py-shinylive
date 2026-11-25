---
title: "Pyodide package detection"
description: "How shinylive finds the Pyodide packages an app needs from its imports and requirements.txt, maps module names to pyodide-lock.json keys, follows dependencies, and which wheels are always included. Covers the package half of `_deps.py`."
---

# Pyodide package detection

Pyodide can only load packages that are in its `pyodide-lock.json` (or that
`micropip` installs at run time from PyPI). An export copies just the wheels
the app needs from `<assets>/shinylive/pyodide/` so the site stays small.

## `find_package_deps(app_contents)`

1. `_find_import_app_contents()`: for every file whose name ends in `.py`,
   `_find_imports()` parses it with `ast` (after `dedent()`) and collects the
   top-level module of every `import x.y` and `from x.y import z`. Relative
   imports (`from .x import y`) are skipped, as they name app modules. A file
   with a syntax error gives no imports. Module names are mapped to lock keys with
   `module_to_package_key()` (from each package's `imports` list, so `cv2`
   becomes `opencv-python`); unknown modules are dropped.
2. `_find_requirements_app_contents()`: for the top-level file named exactly
   `requirements.txt`, `_find_packages_in_requirements()` keeps the leading
   name of each line and turns `_` into `-`. It drops comments (also inline),
   blank lines, option lines starting with `-` (`-r`, `--index-url`, `-e`),
   local paths (`.`, `./my_pkg`, `/wheels/x.whl`, `C:\x.whl`), and lines
   starting with a URL (`https://`, `git+https://`). For
   `pkg @ https://...` it keeps `pkg`.
3. `_find_recursive_deps()` follows each package's `depends` list. Names not
   in the lock are dropped. With `--verbose`, a message is printed for each,
   except base names like `ssl`. It returns the names
   sorted, so the copy order is the same on every run.
4. `_dep_names_to_pyodide_pkg_infos()` turns names into lock entries
   (`dep_name_to_dep_key()` lowercases and maps the lock's `name` to its key).

## Base packages

`BASE_PYODIDE_PACKAGE_NAMES` (`distutils`, `micropip`, `ssl`, `pyodide-http`)
and their dependencies are always copied (`base_package_deps()`).
`BASE_PYODIDE_FILES` (`pyodide.asm.js`, `pyodide.asm.wasm`,
`python_stdlib.zip`, `pyodide-lock.json`) are the only files of
`shinylive/pyodide/` in `shinylive_common_files()`, which returns its list
sorted. The base names that are not in the lock (like `distutils` and `ssl`)
are dropped.

## Lock data and caches

`_pyodide_lock_data()`, `_dep_name_to_dep_key_mappings()`, and
`_module_to_package_key_mappings()` are `functools.lru_cache`d. They read the
lock of `assets_version()`. `set_assets_version()` clears them through
`clear_pyodide_caches()` when the version changes.

## Names versus keys versus modules

- **Key**: the dict key in `packages`, such as `jsonschema-specifications`.
- **Name**: the `name` field, such as `jsonschema_specifications`. `depends`
  lists use names.
- **Module**: an entry in `imports`, such as `cv2`.

`dep_name_to_dep_key()` maps names (case-insensitive) to keys;
`module_to_package_key()` maps modules (case-sensitive) to keys.

## Pitfalls

- **Local modules with a package's name.** A local `utils.py` imported as
  `import utils` is matched against Pyodide's modules too. There is no check
  against the app's own files.
- **Sets have no stable order.** Sort anything built from a `set` before it
  reaches output (copied files, Quarto resources, `app.json`).
- **Only the top-level `requirements.txt` is read**, and it is not followed
  through `-r` includes.
- **Package tests depend on the Pyodide version.** `tests/test_deps.py`
  asserts exact dependency lists, which change when the assets update Pyodide.
