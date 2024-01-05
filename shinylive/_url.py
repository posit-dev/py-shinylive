from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import List, Literal, Optional, TypedDict, cast


class FileContentJson(TypedDict):
    name: str
    content: str
    type: Literal["text", "binary"]


def encode_shinylive_url(
    app: str | Path,
    files: Optional[tuple[str | Path, ...]] = None,
    mode: str = "editor",
    language: Optional[str] = None,
    header: bool = True,
) -> str:
    """
    Generate a URL for a [ShinyLive application](https://shinylive.io).

    Parameters
    ----------
    app
        The main app file of the ShinyLive application. This file should be a Python
        `app.py` or an R `app.R`, `ui.R`, or `server.R` file. This file will be renamed
         `app.py` or `app.R` for shinylive, unless it's named `ui.R` or `server.R`.
    files
        A tuple of file or directory paths to include in the application. On shinylive,
        these files will be stored relative to the main `app` file. If an entry in files
        is a directory, then all files in that directory will be included, recursively.
    mode
        The mode of the application. Defaults to "editor".
    language
        The language of the application. Defaults to None.
    header
        Whether to include a header. Defaults to True.

    Returns
    -------
        The generated URL for the ShinyLive application.
    """

    # if app has a newline, then it's app content, not a path
    if isinstance(app, str) and "\n" in app:
        # now language is required
        if language is None:
            raise ValueError("If `app` is a string, then `language` must be specified.")

        app_path = ""
        root_dir = Path(".")
        file_bundle = [
            {
                "name": f"app.{'py' if language == 'py' else 'R'}",
                "content": app,
                "type": "text",
            }
        ]
    else:
        app_path = Path(app)
        root_dir = app_path.parent
        file_bundle = [read_file(app, root_dir)]

    if files is not None:
        file_list: list[str | Path] = []

        for file in files:
            if Path(file).is_dir():
                file_list.extend(listdir_recursive(file))
            else:
                file_list.append(file)

        file_bundle = file_bundle + [
            read_file(file, root_dir) for file in file_list if Path(file) != app_path
        ]

    if language is None:
        language = file_bundle[0]["name"].split(".")[-1].lower()
    else:
        language = "py" if language.lower() in ["py", "python"] else "r"

    # if first file is not named either `ui.R` or `server.R`, then make it app.{language}
    if file_bundle[0]["name"] not in ["ui.R", "server.R"]:
        file_bundle[0]["name"] = f"app.{'py' if language == 'py' else 'R'}"

    file_lz = lzstring_file_bundle(cast(List[FileContentJson], file_bundle))

    base = "https://shinylive.io"

    return f"{base}/{language}/{mode}/#{'h=0&' if not header else ''}code={file_lz}"


def listdir_recursive(dir: str | Path) -> list[str]:
    dir = Path(dir)
    all_files: list[str] = []

    for root, dirs, files in os.walk(dir):
        for file in files:
            all_files.append(os.path.join(root, file))
        for dir in dirs:
            all_files.extend(listdir_recursive(dir))

    return all_files


def decode_shinylive_url(url: str) -> List[FileContentJson]:
    from lzstring import LZString  # type: ignore[reportMissingTypeStubs]

    url = url.strip()

    try:
        bundle_json = cast(
            str,
            LZString.decompressFromEncodedURIComponent(  # type: ignore
                url.split("code=")[1]
            ),
        )
        bundle = json.loads(bundle_json)
    except Exception:
        raise ValueError("Could not parse and decode the shinylive URL code payload.")

    # bundle should be an array of FileContentJson objects, otherwise raise an error
    if not isinstance(bundle, list):
        raise ValueError(
            "The shinylive URL was not formatted correctly: `code` did not decode to a list."
        )

    for file in bundle:  # type: ignore
        if not isinstance(file, dict):
            raise ValueError(
                "Invalid shinylive URL: `code` did not decode to a list of dictionaries."
            )
        if not all(key in file for key in ["name", "content"]):
            raise ValueError(
                "Invalid shinylive URL: `code` included an object that was missing required fields `name` or `content`."
            )
        if "type" in file and file["type"] not in ["text", "binary"]:
            raise ValueError(
                f"Invalid shinylive URL: unexpected file type '{file['type']}' in '{file['name']}'."
            )
        elif "type" not in file:
            file["type"] = "text"
        if not all(isinstance(value, str) for value in file.values()):  # type: ignore
            raise ValueError(
                f"Invalid shinylive URL: not all items in '{file['name']}' were strings."
            )

    return cast(List[FileContentJson], bundle)


# Copied from https://github.com/posit-dev/py-shiny/blob/main/docs/_renderer.py#L231
def read_file(file: str | Path, root_dir: str | Path | None = None) -> FileContentJson:
    file = Path(file)
    if root_dir is None:
        root_dir = Path("/")
    root_dir = Path(root_dir)

    type: Literal["text", "binary"] = "text"

    try:
        with open(file, "r") as f:
            file_content = f.read()
            type = "text"
    except UnicodeDecodeError:
        # If text failed, try binary.
        with open(file, "rb") as f:
            file_content_bin = f.read()
            file_content = base64.b64encode(file_content_bin).decode("utf-8")
            type = "binary"

    return {
        "name": str(file.relative_to(root_dir)),
        "content": file_content,
        "type": type,
    }


def lzstring_file_bundle(file_bundle: List[FileContentJson]) -> str:
    from lzstring import LZString  # type: ignore[reportMissingTypeStubs]

    file_json = json.dumps(file_bundle)
    file_lz = LZString.compressToEncodedURIComponent(file_json)  # type: ignore[reportUnknownMemberType]
    return cast(str, file_lz)
