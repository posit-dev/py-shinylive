---
title: "shinylive.io URLs"
description: "How `ShinyliveApp`, `url_encode()`, `url_decode()`, and `shinylive url encode|decode` build and read shinylive.io links: the file bundle, lz-string compression, language and mode detection, and writing decoded files. Covers `_url.py`."
---

# shinylive.io URLs

A shinylive.io link holds the whole app in the URL hash:

```
https://shinylive.io/<py|r>/<editor|app>/#[h=0&]code=<lz-string of JSON>
```

The JSON is a list of `{"name", "content", "type"?}` dicts (`type` is only
`"binary"` for base64 content). `h=0` hides the header and is only used in
`app` mode. This works for R apps too; no assets are needed.

## `ShinyliveApp`

- `ShinyliveApp(bundle, language, mode="editor", header=True, host=...)`.
  With `language=None`, it is detected from the first file's content.
- `from_local(app, files, language)`: reads `app` and renames it `app.py` or
  `app.R` (unless it is `ui.R` or `server.R`). Other files are named relative
  to the app's folder (`_root_dir`).
- `from_text(app_text, files, language, root_dir)`: the app from a string.
  Without `root_dir`, added files keep only their base name.
- `from_url(url)`: decodes with `bundle_from_url()`, which checks each item.
  Language and mode come from the end of the URL path, `/<py|r>/<editor|app>/`,
  on any host (default: Python editor); header is off if the URL contains
  `h=0`.
- `to_url()`, `to_json()`, `to_chunk_contents()` (`## file:` sections),
  `to_chunk()` (a full Quarto `shinylive-<lang>` block), `view()`,
  `write_files(dest)`.
- `add_file()`, `add_files()` (files or folders), `add_dir()`,
  `add_file_contents()`, `remove_file()` (by bundle name or local path), `+`
  (file or dir), and `-`. `add_file(overwrite=True)` replaces a file with the
  same name; otherwise a duplicate name is a `ValueError`.

`read_file()` reads UTF-8 text or falls back to base64 binary, and names the
file relative to `root_dir` (or by base name) with `_relative_name()`, which
compares absolute paths and always uses `/`. A file outside `root_dir` is a
`ValueError`, unless `add_file()` is given a `name`.

`write_files(dest)` checks every name first (no absolute paths, no `..`),
then creates subfolders and writes text as UTF-8.

`detect_app_language()`: a string with a newline is code (`import shiny` /
`from shiny` means Python, `library(shiny)` means R); otherwise it is a path
and the suffix decides.

## CLI

- `shinylive url encode APP [FILES...]` (`APP` may be `-` for stdin), with
  `--mode`, `--language`, `--json`, `--no-header`, `--view`.
- `shinylive url decode [URL]` (or stdin) prints `## file:` sections, or
  `--json`, or writes files with `--dir`.

## Pitfalls

- **Decoded URLs are untrusted.** Their file names can be anything; keep the
  `write_files()` name check.
- **Folders in `files` are named differently by the two constructors.** With
  `from_local()`, names are relative to the app's folder (`www/s.css`); with
  `from_text()` and no `root_dir`, only the base name is kept (`s.css`).
  `add_dir()` names files `<folder name>/...` (or flattens them).
- **Bundle names always use `/`.** Build them with `as_posix()`, never
  `str(Path)` or `os.path.join()`, which use `\` on Windows.
- **`url_encode()` returns a `str`**, not a `ShinyliveApp`.
