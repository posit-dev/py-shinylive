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
  Language is `"r"` if the URL contains `shinylive.io/r/`; mode is `"app"` if
  it contains `<lang>/app/`; header is off if it contains `h=0`.
- `to_url()`, `to_json()`, `to_chunk_contents()` (`## file:` sections),
  `to_chunk()` (a full Quarto `shinylive-<lang>` block), `view()`,
  `write_files(dest)`.
- `add_file()`, `add_files()`, `add_dir()`, `add_file_contents()`,
  `remove_file()`, `+` (file or dir), and `-`.

`read_file()` reads UTF-8 text or falls back to base64 binary, and names the
file relative to `root_dir` (or by base name).

`detect_app_language()`: a string with a newline is code (`import shiny` /
`from shiny` means Python, `library(shiny)` means R); otherwise it is a path
and the suffix decides.

## CLI

- `shinylive url encode APP [FILES...]` (`APP` may be `-` for stdin), with
  `--mode`, `--language`, `--json`, `--no-header`, `--view`.
- `shinylive url decode [URL]` (or stdin) prints `## file:` sections, or
  `--json`, or writes files with `--dir`.

## Pitfalls

- **Directories in `files` fail.** `add_files()` calls `add_file()`, which
  can't read a folder, so `from_local(app, ["www"])` and
  `shinylive url encode app.py www` raise `IsADirectoryError`, though the help
  says folders work. `app + "www"` works.
- **`add_file(overwrite=True)` adds a second copy** of the file instead of
  replacing it.
- **`remove_file()` and `-` never remove anything.** They find the index but
  do not delete. With a `_root_dir`, a bundle name like `"x.txt"` is resolved
  against the working folder and raises `ValueError`.
- **Paths must be on the same footing.** `read_file()` uses
  `file.relative_to(root_dir)`, so a relative app path with absolute `files`,
  or a file outside the app folder (even in `add_dir()` with a `name`), raises
  `ValueError`.
- **`write_files()`** fails for names in subfolders (`www/app.js`), because
  it does not create folders, and writes outside `dest` for names like
  `../x` from a decoded URL. Text is written with the platform encoding.
- **Language detection by host.** A URL for an R app on another host
  (`http://localhost:8080/r/...`) decodes as Python.
- **Windows names.** `read_file()` and `add_dir()` build names with
  `str(Path)` / `os.path.join`, so names use `\` on Windows.
- **`url_encode()` returns a `str`**, though its docstring says it returns a
  `ShinyliveApp`.
