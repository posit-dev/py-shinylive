from __future__ import annotations

import base64
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal, Optional, Sequence, cast
from urllib.parse import urlparse

# Even though TypedDict is available in Python 3.8, because it's used with NotRequired,
# they should both come from the same typing module.
# https://peps.python.org/pep-0655/#usage-in-python-3-11
if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict


class FileContentJson(TypedDict):
    name: str
    content: str
    type: NotRequired[Literal["text", "binary"]]


SHINYLIVE_CODE_TEMPLATE = """
```{{shinylive-{language}}}
#| standalone: true
#| components: [{components}]
#| layout: {layout}
#| viewerHeight: {viewer_height}

{contents}
```
"""


class ShinyliveApp:
    """
    Create an instance of a Shiny App for use with shinylive.io.

    Parameters
    ----------
    bundle
        The file bundle of the Shinylive application. This should be a list of files
        as a dictionary of "name", "content" and optionally `"type": "binary"` for
        binary file types. (`"type": "text"` is the default and can be omitted.)
    language
        The language of the application, or None to autodetect the language. Defaults
        to None.
    mode
        The mode of the application, used when creating a shinylive.io URL. Accepted
        values are either "editor" or "app"; defaults to "editor".
    header
        Whether to include a header bar in the UI when creating a shinylive.io URL. This
        is used only if ``mode`` is "app". Defaults to True.
    host
        The host URL of the Shinylive application. Defaults to "https://shinylive.io".
    """

    def __init__(
        self,
        bundle: list[FileContentJson],
        language: Optional[Literal["py", "r"]],
        mode: Literal["editor", "app"] = "editor",
        header: bool = True,
        host: str = "https://shinylive.io",
    ):
        self._bundle = bundle
        if language is None:
            lang = detect_app_language(bundle[0]["content"])
        else:
            if language not in ["py", "r"]:
                raise ValueError(
                    f"Invalid language '{language}', must be either 'py' or 'r'."
                )
            lang = language

        if mode not in ["editor", "app"]:
            raise ValueError(
                f"Invalid mode '{mode}', must be either 'editor' or 'app'."
            )

        if not isinstance(header, bool):
            raise ValueError(
                f"Invalid header '{header}', must be either True or False."
            )

        self.mode: Literal["editor", "app"] = mode
        self.header: bool = header
        self.host: str = host
        self._language: Literal["py", "r"] = lang
        self._app_path: Optional[Path] = None
        self._root_dir: Optional[Path] = None

    @classmethod
    def from_local(
        cls,
        app: str | Path,
        files: Optional[str | Path | Sequence[str | Path]] = None,
        language: Optional[Literal["py", "r"]] = None,
        **kwargs: Any,
    ) -> ShinyliveApp:
        """
        Create an instance of a Shiny App from local files for use with shinylive.io.

        Parameters
        ----------
        app
            The main app file of the Shinylive application. This file should be a Python
            `app.py` or an R `app.R`, `ui.R`, or `server.R` file. This file will be
            renamed `app.py` or `app.R` for shinylive, unless it's named `ui.R` or
            `server.R`.
        files
            File(s) or directory path(s) to include in the application. On shinylive,
            these files will be stored relative to the main `app` file.
        language
            The language of the application, or None to autodetect the language. Defaults
            to None.
        """
        if language is None:
            language = detect_app_language(app)
        elif language not in ["py", "r"]:
            raise ValueError(
                f"Language '{language}' is not supported. Please specify one of 'py' or 'r'."
            )

        self = cls([], language=language, **kwargs)

        self._app_path = Path(app)
        self._root_dir = self._app_path.parent
        app_fc = read_file(app, self._root_dir)

        # if the app is not named either `ui.R` or `server.R`, then make it app.py or app.R
        if app_fc["name"] not in ["ui.R", "server.R"]:
            app_fc["name"] = f"app.{'py' if self._language == 'py' else 'R'}"

        self._bundle.append(app_fc)
        self.add_files(files)
        return self

    @classmethod
    def from_text(
        cls,
        app_text: str,
        files: Optional[str | Path | Sequence[str | Path]] = None,
        language: Optional[Literal["py", "r"]] = None,
        root_dir: Optional[str | Path] = None,
        **kwargs: Any,
    ) -> ShinyliveApp:
        """
        Create an instance of a Shiny App from a string containing the `app.py` or `app.R`
        file contents for use with shinylive.io.

        Parameters
        ----------
        app_code
            The text contents of the main app file for the Shinylive application. This file
            will be renamed `app.py` or `app.R` for shinylive.
        files
            File(s) or directory path(s) to include in the application. On shinylive,
            these files will be stored relative to the main `app` file.
        language
            The language of the application, or None to autodetect the language. Defaults
            to None.
        root_dir
            The root directory of the application,used to determine the relative
            path of supporting files to the main ``app`` file. Defaults to ``None``, meaning
            that additional files are added in a flattened structure.
        """
        if language is None:
            language = detect_app_language(app_text)
        elif language not in ["py", "r"]:
            raise ValueError(
                f"Language '{language}' is not supported. Please specify one of 'py' or 'r'."
            )

        default_app_file = f"app.{'py' if language == 'py' else 'R'}"
        app_fc = {default_app_file: app_text}

        self = cls([], language=language, **kwargs)
        self._root_dir = Path(root_dir) if root_dir is not None else None

        return self.add_file_contents(app_fc).add_files(files)

    @classmethod
    def from_url(cls, url: str) -> ShinyliveApp:
        """
        Create an instance of a Shiny App from a shinylive.io URL.

        Parameters
        ----------
        url
            The shinylive.io URL to decode.
        """

        url = url.strip()
        bundle = bundle_from_url(url)
        language = "r" if "shinylive.io/r/" in url else "py"
        mode = "app" if f"{language}/app/" in url else "editor"
        header = False if "h=0" in url else True
        scheme, netloc, *_ = urlparse(url)

        return cls(
            bundle,
            language=language,
            mode=mode,
            header=header,
            host=f"{scheme}://{netloc}",
        )

    def __str__(self) -> str:
        return self.to_url()

    def to_url(
        self,
        mode: Optional[Literal["editor", "app"]] = None,
        header: Optional[bool] = None,
        host: Optional[str] = None,
    ) -> str:
        """
        Get the URL of the Shinylive application.

        Parameters
        ----------
        mode
            The mode of the application, either "editor" or "app". Defaults to the
            current mode.
        header
            Whether to include a header bar in the UI. This is used only if ``mode`` is
            "app". Defaults to the current header value.
        host
            The host URL of the Shinylive application. Defaults to the current host URL,
            which is typically ``"https://shinylive.io"``.

        Returns
        -------
        str
            The URL of the Shinylive application.
        """
        mode = mode or self.mode
        header = header if header is not None else self.header

        if mode not in ["editor", "app"]:
            raise ValueError(
                f"Invalid mode '{mode}', must be either 'editor' or 'app'."
            )

        file_lz = lzstring_file_bundle(self._bundle)

        base = (host or self.host).rstrip("/")

        h = "h=0&" if not header and mode == "app" else ""

        return f"{base}/{self._language}/{mode}/#{h}code={file_lz}"

    def view(self) -> None:
        """
        Open the Shinylive application in a browser.
        """
        import webbrowser

        webbrowser.open(self.to_url())

    def to_chunk_contents(self) -> str:
        """
        Create the contents of a Shinylive chunk based on the files in the app. This
        output does not include the Shinylive chunk header or options.

        Returns
        -------
        str
            The contents of the Shinylive chunk.
        """
        lines: list[str] = []
        for file in self._bundle:
            lines.append(f"## file: {file['name']}")
            if "type" in file and file["type"] == "binary":
                lines.append("## type: binary")
            lines.append(
                file["content"].encode("utf-8", errors="ignore").decode("utf-8")
            )
            lines.append("")

        return "\n".join(lines)

    def to_chunk(
        self,
        components: Sequence[Literal["editor", "viewer"]] = ("editor", "viewer"),
        layout: Literal["horizontal", "vertical"] = "horizontal",
        viewer_height: int = 500,
    ) -> str:
        """
        Create a Shinylive chunk based on the files in the app for use in a Quarto
        web document.

        Parameters
        ----------
        components
            Which components to include in the chunk. Defaults to both "editor" and
            "viewer".
        layout
            The layout of the components, either "horizontal" or "vertical". Defaults
            to "horizontal".
        viewer_height
            The height of the viewer component in pixels. Defaults to 500.

        Returns
        -------
        str
            The full Shinylive chunk, including the chunk header and options.
        """
        if layout not in ["horizontal", "vertical"]:
            raise ValueError(
                f"Invalid layout '{layout}', must be either 'horizontal' or 'vertical'."
            )

        if not isinstance(components, Sequence) or not all(
            component in ["editor", "viewer"] for component in components
        ):
            raise ValueError(
                f"Invalid components '{components}', must be a list or tuple of 'editor' or 'viewer'."
            )

        return SHINYLIVE_CODE_TEMPLATE.format(
            language="python" if self._language == "py" else "r",
            components=", ".join(components),
            layout=layout,
            viewer_height=viewer_height,
            contents=self.to_chunk_contents(),
        )

    def to_json(self, **kwargs: Any) -> str:
        """
        Get the JSON representation of the Shinylive application.

        Parameters
        ----------
        kwargs
            Keyword arguments passed to ``json.dumps``.

        Returns
        -------
        str
            The JSON representation of the Shinylive application.
        """
        return json.dumps(self._bundle, **kwargs)

    def write_files(self, dest: str | Path) -> Path:
        """
        Write the files in the Shinylive application to a directory.

        Parameters
        ----------
        dest
            The directory to write the files to.

        Returns
        -------
        Path
            The directory that the files were written to.
        """
        out_dir = Path(dest)
        out_dir.mkdir(parents=True, exist_ok=True)
        for file in self._bundle:
            if "type" in file and file["type"] == "binary":
                import base64

                with open(out_dir / file["name"], "wb") as f_out:
                    f_out.write(base64.b64decode(file["content"]))
            else:
                with open(out_dir / file["name"], "w") as f_out:
                    f_out.write(
                        file["content"].encode("utf-8", errors="ignore").decode("utf-8")
                    )

        return out_dir

    def add_files(
        self,
        files: Optional[str | Path | Sequence[str | Path]] = None,
    ) -> ShinyliveApp:
        """
        Add files to the Shinylive application. For more control over the file name,
        use the ``add_file`` method.

        Parameters
        ----------
        files
            File(s) or directory path(s) to include in the application. On shinylive,
            these files will be stored relative to the main ``app`` file. Use the
            ``add_file`` method to add a single file if you need to rename the files.
            In app bundles created from local files, added files will be stored relative
            to the location of the local ``app`` file. In app bundles created from text,
            files paths are flattened to include only the file name.
        """
        if files is None:
            return self

        if isinstance(files, (str, Path)):
            files = [files]

        for file in files or []:
            if self._app_path is not None and Path(file) == self._app_path:
                continue
            self.add_file(file)

        return self

    def add_dir(
        self,
        dir: str | Path,
        flatten: bool = False,
        overwrite: bool = False,
    ) -> ShinyliveApp:
        """
        Add all files in a directory to the Shinylive application.

        Parameters
        ----------
        dir
            The directory to add to the application.
        flatten
            Whether or not to flatten the directory structure. Defaults to ``False``.
            When ``True``, all files are added to the root directory of the application,
            otherwise all files are added into a directory with the same name as the
            input ``dir``.
        overwrite
            Whether or not to overwrite an existing file with the same name. Defaults
            to ``False``.
        """
        dir = Path(dir)
        if not dir.is_dir():
            raise ValueError(f"Directory '{dir}' does not exist or is not a directory.")

        for file in listdir_recursive(dir):
            if flatten:
                # The contents of the directory are added into the "root" of the app
                # bundle, e.g. `"../some_dir/www"` adds its contents to the bundle,
                # i.e. the bundle will have `styles.css` and `app.js`, etc.
                name = str(Path(file).relative_to(dir))
            else:
                # The directory is added into the bundle, e.g. `"../some_dir/www"`
                # is added as `www/` in the bundle.
                name = os.path.join(
                    os.path.basename(dir),
                    str(Path(file).relative_to(dir)),
                )
            self.add_file(file, name, overwrite=overwrite)

        return self

    def add_file_contents(self, file_contents: dict[str, str]) -> ShinyliveApp:
        """
        Directly adds a text file to the Shinylive app.

        Parameters
        ----------
        file_contents
            A dictionary of file names and file contents.
        """
        for file in file_contents:
            self._bundle.append(
                {
                    "name": file,
                    "content": file_contents[file],
                }
            )

        return self

    def add_file(
        self,
        file: str | Path,
        name: Optional[str | Path] = None,
        overwrite: bool = False,
    ) -> ShinyliveApp:
        """
        Add a file to the Shinylive application.

        Parameters
        ----------
        file
            File or directory path to include in the application. On shinylive, this
            file will be stored relative to the main ``app`` file. All files should be
            contained in the same directory as or a subdirectory of the main ``app`` file.
        name
            The name of the file to be used in the app. If not provided, the file name
            will be used, using the relative path from the main ``app`` file if the
            ``ShinyliveIoApp`` was created from local files.
        overwrite
            Whether or not to overwrite an existing file with the same name. Defaults
            to ``False``.
        """
        file_new = read_file(file, self._root_dir)
        if name is not None:
            file_new["name"] = str(name)

        file_names = [file["name"] for file in self._bundle]

        if any([name == file_new["name"] for name in file_names]):
            if overwrite:
                index = file_names.index(file_new["name"])
                self._bundle[index] = file_new
            else:
                raise ValueError(
                    f"File '{file_new['name']}' already exists in app bundle and `overwrite` was `False`."
                )

        self._bundle.append(file_new)

        return self

    def remove_file(self, file: str | Path) -> ShinyliveApp:
        file_names = [file["name"] for file in self._bundle]
        index = None

        if file in file_names and isinstance(file, str):
            # find the index of the file to remove
            index = file_names.index(file)

        if self._root_dir is not None:
            root_dir = self._root_dir.absolute()

            other_path = str(Path(file).absolute().relative_to(root_dir))
            if other_path in file_names:
                index = file_names.index(other_path)

        if index is None:
            raise ValueError(f"File '{file}' not found in app bundle.")

        return self

    def __add__(self, other: str | Path) -> ShinyliveApp:
        other = Path(other)
        new: ShinyliveApp = copy.deepcopy(self)
        if other.is_dir():
            new.add_dir(other)
        else:
            new.add_file(other)
        return new

    def __sub__(self, other: str | Path) -> ShinyliveApp:
        new: ShinyliveApp = copy.deepcopy(self)
        new.remove_file(other)
        return new


def url_encode(
    app: str | Path,
    files: Optional[str | Path | Sequence[str | Path]] = None,
    language: Optional[Literal["py", "r"]] = None,
    mode: Literal["editor", "app"] = "editor",
    header: bool = True,
    host: str = "https://shinylive.io",
) -> str:
    """
    Generate a URL for a [Shinylive application](https://shinylive.io).

    Parameters
    ----------
    app
        The main app file of the Shinylive application. This file should be a Python
        `app.py` or an R `app.R`, `ui.R`, or `server.R` file. This file will be renamed
         `app.py` or `app.R` for shinylive, unless it's named `ui.R` or `server.R`.
    files
        File(s) or directory path(s) to include in the application. On shinylive, these
        files will be stored relative to the main `app` file.
    mode
        The mode of the application, either "editor" or "app". Defaults to "editor".
    language
        The language of the application, or None to autodetect the language. Defaults to
        None.
    header
        Whether to include a header bar in the UI. This is used only if ``mode`` is
        "app". Defaults to True.


    Returns
    -------
        A ShinyliveApp object. Use the `.url()` method to retrieve the Shinylive URL.
    """

    if language is not None and language not in ["py", "r"]:
        raise ValueError(f"Invalid language '{language}', must be either 'py' or 'r'.")

    lang = language if language is not None else detect_app_language(app)

    if isinstance(app, str) and "\n" in app:
        sl_app = ShinyliveApp.from_text(
            app, files, lang, mode=mode, header=header, host=host
        )
    else:
        sl_app = ShinyliveApp.from_local(
            app, files, lang, mode=mode, header=header, host=host
        )

    return sl_app.to_url()


def url_decode(url: str) -> ShinyliveApp:
    """
    Decode a Shinylive URL into a ShinyliveIoApp object.

    Parameters
    ----------
    url
        The Shinylive URL to decode.

    Returns
    -------
        A ShinyliveIoApp object.
    """
    return ShinyliveApp.from_url(url)


def bundle_from_url(url: str) -> list[FileContentJson]:
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
        raise ValueError("Could not parse and decode the Shinylive URL code payload.")

    ret: list[FileContentJson] = []

    # bundle should be an array of FileContentJson objects, otherwise raise an error
    if not isinstance(bundle, list):
        raise ValueError(
            "The Shinylive URL was not formatted correctly: `code` did not decode to a list."
        )

    for file in bundle:  # type: ignore
        if not isinstance(file, dict):
            raise ValueError(
                "Invalid Shinylive URL: `code` did not decode to a list of dictionaries."
            )
        if not all(key in file for key in ["name", "content"]):
            raise ValueError(
                "Invalid Shinylive URL: `code` included an object that was missing required fields `name` or `content`."
            )

        for key in ["name", "content"]:
            if not isinstance(file[key], str):
                raise ValueError(
                    f"Invalid Shinylive URL: encoded file bundle contains an file where `{key}` was not a string."
                )

        fc: FileContentJson = {
            "name": file["name"],
            "content": file["content"],
        }

        if "type" in file:
            if file["type"] == "binary":
                fc["type"] = "binary"
            elif file["type"] == "text":
                pass
            else:
                raise ValueError(
                    f"Invalid Shinylive URL: unexpected file type '{file['type']}' in '{file['name']}'."
                )

        if not all(isinstance(value, str) for value in file.values()):  # type: ignore
            raise ValueError(
                f"Invalid Shinylive URL: not all items in '{file['name']}' were strings."
            )
        ret.append(fc)

    return ret


def detect_app_language(app: str | Path) -> Literal["py", "r"]:
    err_not_detected = """
    Could not automatically detect the language of the app. Please specify `language`."""

    if isinstance(app, str) and "\n" in app:
        if re.search(r"^(import|from) shiny", app, re.MULTILINE):
            return "py"
        elif re.search(r"^library\(shiny\)", app, re.MULTILINE):
            return "r"
        else:
            raise ValueError(err_not_detected)

    app = Path(app)

    if app.suffix.lower() == ".py":
        return "py"
    elif app.suffix.lower() == ".r":
        return "r"
    else:
        raise ValueError(err_not_detected)


def listdir_recursive(dir: str | Path) -> list[str]:
    """
    List files in a directory, recursively. Ignores directories or files that start with
    "." or "__".
    """
    dir = Path(dir)
    all_files: list[str] = []

    for root, dirs, files in os.walk(dir):
        # Exclude files and directories that start with `.` or `__`
        dirs[:] = [d for d in dirs if not (d.startswith(".") or d.startswith("__"))]
        files[:] = [f for f in files if not (f.startswith(".") or f.startswith("__"))]

        for file in files:
            if not (file.startswith(".") or file.startswith("__")):
                all_files.append(os.path.join(root, file))

    return all_files


# Copied from https://github.com/posit-dev/py-shiny/blob/main/docs/_renderer.py#L231
def read_file(file: str | Path, root_dir: str | Path | None = None) -> FileContentJson:
    file = Path(file)

    type: Literal["text", "binary"] = "text"

    try:
        with open(file, "r", encoding="utf-8") as f:
            file_content = f.read()
            type = "text"
    except UnicodeDecodeError:
        # If text failed, try binary.
        with open(file, "rb") as f:
            file_content_bin = f.read()
            file_content = base64.b64encode(file_content_bin).decode("utf-8")
            type = "binary"

    file_name = str(file.relative_to(root_dir)) if root_dir else file.name

    return {
        "name": file_name,
        "content": file_content,
        "type": type,
    }


def lzstring_file_bundle(file_bundle: list[FileContentJson]) -> str:
    from lzstring import LZString  # type: ignore[reportMissingTypeStubs]

    file_json = json.dumps(file_bundle)
    file_lz = LZString.compressToEncodedURIComponent(file_json)  # type: ignore[reportUnknownMemberType]
    return file_lz
