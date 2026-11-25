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
   top-level module of every `import x.y` and `from x.y import z`. A file with
   a syntax error gives no imports. Module names are mapped to lock keys with
   `module_to_package_key()` (from each package's `imports` list, so `cv2`
   becomes `opencv-python`); unknown modules are dropped.
2. `_find_requirements_app_contents()`: for the top-level file named exactly
   `requirements.txt`, `_find_packages_in_requirements()` keeps the leading
   name of each line, drops comments, blank lines, and `http(s)://` lines, and
   turns `_` into `-`.
3. `_find_recursive_deps()` follows each package's `depends` list. Names not
   in the lock are dropped (with a verbose message), except the base names.
4. `_dep_names_to_pyodide_pkg_infos()` turns names into lock entries
   (`dep_name_to_dep_key()` lowercases and maps the lock's `name` to its key).

## Base packages

`BASE_PYODIDE_PACKAGE_NAMES` (`distutils`, `micropip`, `ssl`, `pyodide-http`)
and their dependencies are always copied (`base_package_deps()`).
`BASE_PYODIDE_FILES` (`pyodide.asm.js`, `pyodide.asm.wasm`,
`python_stdlib.zip`, `pyodide-lock.json`) are the only files of
`shinylive/pyodide/` in `shinylive_common_files()`.

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

- **Relative imports count.** `from .numpy import x` (a local module) is read
  as the `numpy` package, because `node.level` is ignored.
- **Local modules with a package's name.** A local `utils.py` imported as
  `import utils` is matched against Pyodide's modules too. There is no check
  against the app's own files.
- **`requirements.txt` lines are read loosely.** `-r other.txt` gives `-r`,
  `git+https://...` gives `git`, and option lines like `--index-url` are kept
  as names. They do no harm unless a lock entry has that name.
- **Order is not stable.** `_find_recursive_deps()` adds dependencies from a
  `set`, and `shinylive_common_files()` lists `BASE_PYODIDE_FILES` from a
  `set`, so the order of copied files and of Quarto resources changes between
  runs.
- **Package tests depend on the Pyodide version.** `tests/test_deps.py`
  asserts exact dependency lists, which change when the assets update Pyodide.
