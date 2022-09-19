import filecmp
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, List, Union


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


def path_length(path: Union[str, Path]) -> int:
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


def listdir_recursive(dir: Union[str, Path]) -> List[str]:
    dir = Path(dir)
    all_files: List[str] = []

    for root, _dirs, files in os.walk(dir):
        root = Path(root)
        rel_root = root.relative_to(dir)

        for file in files:
            all_files.append(os.path.join(rel_root / file))

    return all_files


def copy_file_and_substitute(
    src: Union[str, Path], dest: Union[str, Path], search_str: str, replace_str: str
) -> None:
    with open(src, "r") as fin:
        in_content = fin.read()
        in_content = in_content.replace(search_str, replace_str)
        with open(dest, "w") as fout:
            fout.write(in_content)


def create_copy_fn(overwrite: bool) -> Callable[..., None]:
    """Returns a function that can be used as a copy_function for shutil.copytree.

    If overwrite is True, the copy function will overwrite files that already exist.
    If overwrite is False, the copy function will not overwrite files that already exist.
    """

    def copy_fn(src: str, dst: str, **kwargs: object) -> None:
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
                print(f"Overwriting {dst}", file=sys.stderr)
                os.remove(dst)
            else:
                print(f"Skipping {dst}", file=sys.stderr)
                return

        shutil.copy2(src, dst, **kwargs)

    return copy_fn
