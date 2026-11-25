from __future__ import annotations

import base64
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Literal, TypedDict

from . import _utils


# This is the same as the FileContentJson type in TypeScript.
class FileContentJson(TypedDict):
    name: str
    content: str
    type: Literal["text", "binary"]


class AppInfo(TypedDict):
    appdir: str
    subdir: str
    files: list[FileContentJson]


# =============================================================================
def read_app_files(appdir: Path, destdir: Path) -> list[FileContentJson]:
    """
    Load files for a Shiny application.

    Parameters
    ----------
    appdir : str
       Directory containing the application.

    destdir : str
       Destination directory. This is used only to avoid adding shinylive assets when
       they are in a subdir of the application.
    """
    app_files: list[FileContentJson] = []
    # Recursively iterate over files in app directory, and collect the files into
    # app_files data structure.
    exclude_names = {"__pycache__", "venv", ".venv"}
    # Compare resolved paths, so a relative destdir and an absolute appdir (or the
    # other way around) still match
    destdir_cmp = _utils.comparable_path(destdir)
    for root, dirs, files in os.walk(appdir, topdown=True):
        root = Path(root)

        if _utils.comparable_path(root).is_relative_to(destdir_cmp):
            # In case destdir is inside of the appdir, don't copy those files.
            dirs[:] = []
            continue

        # Sort, so the files in app.json are in the same order on every run
        dirs[:] = sorted(
            d for d in dirs if not d.startswith(".") and d not in exclude_names
        )
        rel_dir = root.relative_to(appdir)
        files = [f for f in files if not f.startswith(".")]
        files = [f for f in files if f not in exclude_names]
        files.sort()

        # Move app.py to first in list.
        if "app.py" in files:
            app_py_idx = files.index("app.py")
            files.insert(0, files.pop(app_py_idx))

        # Add the file to the app_files list.
        for filename in files:
            # For the top folder, `rel_dir` is `Path(".")`, which this drops.
            output_filename = (rel_dir / filename).as_posix()

            if filename == "shinylive.js":
                print(
                    f"Warning: Found shinylive.js in source directory '{appdir}/{rel_dir}'. Are you including a shinylive distribution in your app?",
                    file=sys.stderr,
                )

            type: Literal["text", "binary"] = "text"
            try:
                with open(root / filename, "r", encoding="utf-8") as f:
                    file_content = f.read()
                    type = "text"
            except UnicodeDecodeError:
                # If text failed, try binary.
                with open(root / filename, "rb") as f:
                    file_content_bin = f.read()
                    file_content = base64.b64encode(file_content_bin).decode("utf-8")
                    type = "binary"

            app_files.append(
                {
                    "name": output_filename,
                    "content": file_content,
                    "type": type,
                }
            )

    return app_files


def write_app_json(
    app_info: AppInfo,
    destdir: Path,
    html_source_dir: Path,
    template_params: dict[str, object] | None = None,
) -> None:
    """
    Write index.html, edit/index.html, and app.json for an application in the destdir.
    """
    app_destdir = destdir / app_info["subdir"]

    # For a subdir like a/b/c, this will be ../../../
    subdir_inverse = "/".join([".."] * _utils.path_length(app_info["subdir"]))
    if subdir_inverse != "":
        subdir_inverse += "/"

    app_destdir.mkdir(parents=True, exist_ok=True)

    replacements = {
        # Default values
        "title": "Shiny App",
        # User values
        **(template_params or {}),
        # Forced values
        "REL_PATH": subdir_inverse,
        "APP_ENGINE": "python",
    }

    template_files = list(html_source_dir.glob("**/*"))
    template_files = [f for f in template_files if f.is_file()]

    for template_file in template_files:
        dest_file = app_destdir / template_file.relative_to(html_source_dir)
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if template_file.suffix == ".html":
            _utils.copy_file_and_substitute(
                src=template_file,
                dest=dest_file,
                data=replacements,
            )
        else:
            shutil.copyfile(template_file, dest_file)

    app_json_output_file = app_destdir / "app.json"

    with open(app_json_output_file, "w", encoding="utf-8") as f:
        json.dump(app_info["files"], f)
    size = app_json_output_file.stat().st_size
    print(f"Writing {app_json_output_file}: {size} bytes", file=sys.stderr)
