from __future__ import annotations

import filecmp
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable

import chevron


def is_relative_to(path: Path, base: Path) -> bool:
    """
    Wrapper for `PurePath.is_relative_to`, which was added in Python 3.9.
    """
    if sys.version_info >= (3, 9):
        return path.is_relative_to(base)
    else:
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False


def path_length(path: str | Path) -> int:
    """Returns the number of elements in a path.

    For example 'a' has length 1, 'a/b' has length 2, etc.
    """

    path = str(path)
    if os.path.isabs(path):
        raise ValueError("path must be a relative path")

    # Unfortunately, there's no equivalent of os.path.normpath for Path objects.
    path = os.path.normpath(path)
    if path == ".":
        return 0

    # On Windows, replace backslashes with forward slashes.
    if os.name == "nt":
        path.replace("\\", "/")

    return len(path.split("/"))


def listdir_recursive(dir: str | Path) -> list[str]:
    dir = Path(dir)
    all_files: list[str] = []

    for root, _dirs, files in os.walk(dir):
        root = Path(root)
        rel_root = root.relative_to(dir)

        for file in files:
            all_files.append(os.path.join(rel_root / file))

    return all_files


def copy_file_and_substitute(
    src: str | Path,
    dest: str | Path,
    data: dict[str, object],
) -> None:
    with open(src, "r", encoding="utf-8") as fin:
        in_content = fin.read()
        out_content = chevron.render(in_content, data)
        with open(dest, "w") as fout:
            fout.write(out_content)


def create_copy_fn(
    overwrite: bool,
    verbose_print: Callable[..., None] = lambda *args: None,
) -> Callable[..., None]:
    """Returns a function that can be used as a copy_function for shutil.copytree.

    If overwrite is True, the copy function will overwrite files that already exist.
    If overwrite is False, the copy function will not overwrite files that already exist.
    """

    def copy_fn(src: str, dst: str, follow_symlinks: bool = True) -> None:
        if os.path.exists(dst):
            if filecmp.cmp(src, dst) is False:
                print(
                    "\nSource and destination copies differ:",
                    dst,
                    """\nThis is probably because your shinylive sources have been updated and differ from the copy in the exported app.""",
                    """\nYou probably should remove the export directory and re-export the application.""",
                    file=sys.stderr,
                )
            if overwrite:
                verbose_print(f"Overwriting {dst}")
                os.remove(dst)
            else:
                verbose_print(f"Skipping {dst}")
                return

        shutil.copy2(src, dst, follow_symlinks=follow_symlinks)

    return copy_fn


# Wrapper for TarFile.extractall(), to avoid CVE-2007-4559.
def tar_safe_extractall(file: str | Path, destdir: str | Path) -> None:
    import tarfile

    destdir = Path(destdir).resolve()

    with tarfile.open(file) as tar:
        if sys.version_info >= (3, 12):
            # Python 3.12 adds a `filter` argument to `TarFile.extractall`, which eliminates
            # the security vulnerability in CVE-2007-4559. The `tar_safe_extractall`
            # function can be removed once we no longer support Python versions older than
            # 3.12. Also, in Python 3.14, "data" will be the default value.
            tar.extractall(destdir, filter="data")
        else:
            for member in tar.getmembers():
                member_path = (destdir / member.name).resolve()
                if not is_relative_to(member_path, destdir):
                    raise RuntimeError("Attempted path traversal in tar file.")

            tar.extractall(destdir)  # pyright: ignore[reportDeprecated]


def print_as_json(x: object) -> None:
    print(json.dumps(x, indent=None))
