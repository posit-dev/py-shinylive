---
title: "Quarto extension interface"
description: "The `shinylive extension` commands that quarto-ext/shinylive runs for shinylive-python blocks: what each prints as JSON, how one render uses one assets version, and how HTML dependencies are built. Covers `_main.py` extension commands and the HTML dependency half of `_deps.py`."
---

# Quarto extension interface

quarto-ext/shinylive calls the `shinylive` command for each document with
`shinylive-python` blocks. Every command prints one JSON value to stdout with
`print_as_json()`; anything else on stdout breaks the render.

## Commands

| Command | Prints |
|---|---|
| `extension info` | `{"version", "assets_version", "scripts": {"codeblock-to-json": path}}` |
| `extension base-htmldeps --sw-dir DIR` | Two HTML dependencies: `shinylive-serviceworker` and `shinylive` |
| `extension language-resources` | Python support files plus the base package wheels, as `{name, path}` items |
| `extension app-resources [--json-file F]` | The wheels for one app's packages, as `{name, path}` items. Reads the app's `FileContentJson` list from `--json-file` or stdin |

`name` is the path inside the site (such as
`shinylive/pyodide/pandas-....whl`) and `path` is the absolute path in the
assets cache. Quarto copies `path` to `name`.

## One version per render

- `extension` (the group) checks `SHINYLIVE_ASSETS_VERSION` first.
- `info` runs `resolve_assets_version()` with the GitHub check and download,
  so `codeblock-to-json.js` exists, and saves `versions.json`.
- The other commands call `use_quarto_assets_version()`: resolve with
  `check=False` (read `versions.json` only) and `set_assets_version()`. So a
  render uses the version `info` chose, even across processes, and the R
  package, which reads the same file, chooses the same one.

## HTML dependencies (`_deps.py`)

- `_serviceworker_dep(sw_dir)`: copies `shinylive-sw.js` to the site root
  (`/shinylive-sw.js`) and, with `sw_dir`, adds a
  `shinylive:serviceworker_dir` meta tag.
- `_shinylive_common_dep_htmldep(asset_type)`: every file from
  `shinylive_common_files()`. `load-shinylive-sw.js` (first) and
  `run-python-blocks.js` (last) are module scripts, `shinylive.css` is a
  stylesheet, and every file except the stylesheet is also a resource.
- `shinylive_common_files(asset_type)` walks the assets folder. It skips
  `scripts/`, `export_template/`, `shinylive/examples.json`, dotfiles, and
  `pyodide/fonts/`. `asset_type` picks the parts: `"base"` (top-level files
  and `shinylive/*`), `"python"` (`pyodide/` with only `BASE_PYODIDE_FILES`,
  and `pyright/`), `"r"` (`webr/`). It calls `ensure_shinylive_assets()`
  first.
- `shinylive_r_resources()` exists for symmetry and is not used.

## Defunct commands

`base-deps`, `package-deps`, and `codeblock-to-json` at the top level are
hidden and exit with a message to update the Quarto extension.

## Pitfalls

- **Keep the JSON shape in sync with r-shinylive.** The extension reads both
  packages' output the same way.
- **Never print to stdout in code these commands reach.** Download and
  resolve messages go to stderr; keep it that way.
- **Resource order changes between runs** because `BASE_PYODIDE_FILES` is a
  `set` (see `pyodidePackages.md`).
- **Only `info` may use the network.** Adding a GitHub check or a download to
  another command can make one render use two versions.
