from __future__ import annotations

import base64
import json
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
        A tuple of file paths to include in the application. On shinylive, these files
        will be given stored relative to the main `app` file.
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
    root_dir = Path(app).parent
    file_bundle = [read_file(app, root_dir)]

    if files is not None:
        file_bundle = file_bundle + [read_file(file, root_dir) for file in files]

    if language is None:
        language = file_bundle[0]["name"].split(".")[-1].lower()
    else:
        language = "py" if language.lower() in ["py", "python"] else "r"

    # if first file is not named either `ui.R` or `server.R`, then make it app.{language}
    if file_bundle[0]["name"] not in ["ui.R", "server.R"]:
        file_bundle[0]["name"] = f"app.{'py' if language == 'py' else 'R'}"

    file_lz = lzstring_file_bundle(file_bundle)

    base = "https://shinylive.io"

    return f"{base}/{language}/{mode}/#{'h=0&' if not header else ''}code={file_lz}"


def decode_shinylive_url(url: str) -> FileContentJson:
    from lzstring import LZString  # type: ignore[reportMissingTypeStubs]

    bundle_json = cast(
        str,
        LZString.decompressFromEncodedURIComponent(  # type: ignore
            url.split("code=")[1]
        ),
    )
    return cast(FileContentJson, json.loads(bundle_json))


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
