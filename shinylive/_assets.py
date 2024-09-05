from __future__ import annotations

import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

from ._utils import tar_safe_extractall
from ._version import SHINYLIVE_ASSETS_VERSION


def download_shinylive(
    destdir: str | Path | None = None,
    version: str = SHINYLIVE_ASSETS_VERSION,
    url: Optional[str] = None,
    status: bool = True,
) -> None:
    if destdir is None:
        # Note that this is the cache directory, which is the parent of the assets
        # directory. The tarball will have the assets directory as the top-level subdir.
        destdir = shinylive_cache_dir()

    if url is None:
        url = shinylive_bundle_url(version)

    destdir = Path(destdir)
    tmp_name = None

    try:
        print(f"Downloading {url}...", file=sys.stderr)

        start_time = time.time()
        last_update_time = start_time

        def reporthook(count: int, block_size: int, total_size: int):
            if not status:
                return

            nonlocal last_update_time
            current_time = time.time()

            if current_time - last_update_time < 1:
                return

            duration = current_time - start_time
            progress_size = int(count * block_size)
            speed = int(progress_size / (1024 * duration))
            percent = min(int(count * block_size * 100 / total_size), 100)
            sys.stderr.write(
                f"\r{percent}%, {speed} KB/s, {progress_size / (1024 * 1024):.1f}/{total_size / (1024 * 1024):.1f} MB"
            )
            sys.stderr.flush()
            last_update_time = current_time

        tmp_name, _ = urllib.request.urlretrieve(url, reporthook=reporthook)
        sys.stderr.write("\n")

        print(f"Unzipping to {destdir}/", file=sys.stderr)
        tar_safe_extractall(tmp_name, destdir)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)


def shinylive_bundle_url(version: str = SHINYLIVE_ASSETS_VERSION) -> str:
    """
    Returns the URL for the Shinylive assets bundle.
    """
    return (
        "https://github.com/posit-dev/shinylive/releases/download/"
        + f"v{version}/shinylive-{version}.tar.gz"
    )


def shinylive_cache_dir() -> str:
    """
    Returns the directory used for caching Shinylive assets. This directory can contain
    multiple versions of Shinylive assets.
    """
    import appdirs  # pyright: ignore[reportMissingTypeStubs]

    return appdirs.user_cache_dir("shinylive")  # pyright: ignore


def shinylive_assets_dir(version: str = SHINYLIVE_ASSETS_VERSION) -> str:
    """
    Returns the directory containing cached Shinylive assets, for a particular version
    of Shinylive.
    """
    return os.path.join(shinylive_cache_dir(), "shinylive-" + version)


def pyodide_lock_json_file(version: str = SHINYLIVE_ASSETS_VERSION) -> Path:
    return (
        Path(shinylive_assets_dir(version))
        / "shinylive"
        / "pyodide"
        / "pyodide-lock.json"
    )


def codeblock_to_json_file() -> str:
    p = Path(shinylive_assets_dir()) / "scripts" / "codeblock-to-json.js"
    return str(p)


def copy_shinylive_local(
    source_dir: str | Path,
    destdir: Optional[str | Path] = None,
    version: str = SHINYLIVE_ASSETS_VERSION,
):
    if destdir is None:
        destdir = Path(shinylive_cache_dir())

    destdir = Path(destdir)

    target_dir = destdir / f"shinylive-{version}"

    source_dir = Path(source_dir)

    if target_dir.is_symlink():
        target_dir.unlink()
    elif target_dir.is_dir():
        shutil.rmtree(target_dir)

    shutil.copytree(source_dir, target_dir)


def link_shinylive_local(
    source_dir: str | Path,
    destdir: Optional[str | Path] = None,
    version: str = SHINYLIVE_ASSETS_VERSION,
):
    if destdir is None:
        destdir = Path(shinylive_cache_dir())

    destdir = Path(destdir)

    target_dir = destdir / f"shinylive-{version}"

    source_dir = Path(source_dir).absolute()
    if not source_dir.is_dir():
        raise RuntimeError("Source directory does not exist: " + str(source_dir))

    # Ensure parent dir exists before we create a symlink in it.
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if target_dir.is_symlink():
        target_dir.unlink()
    elif target_dir.is_dir():
        shutil.rmtree(target_dir)

    target_dir.symlink_to(source_dir)


def ensure_shinylive_assets(
    destdir: Path | None = None,
    version: str = SHINYLIVE_ASSETS_VERSION,
    url: Optional[str] = None,
) -> Path:
    """Ensure that there is a local copy of shinylive."""

    if destdir is None:
        destdir = Path(shinylive_cache_dir())

    if url is None:
        url = shinylive_bundle_url(version)

    if not destdir.exists():
        print("Creating directory " + str(destdir), file=sys.stderr)
        destdir.mkdir(parents=True)

    shinylive_bundle_dir = Path(shinylive_assets_dir(version))
    if not shinylive_bundle_dir.exists():
        print(f"{shinylive_bundle_dir} does not exist.", file=sys.stderr)
        download_shinylive(url=url, version=version, destdir=destdir)

    return shinylive_bundle_dir


def cleanup_shinylive_assets(
    shinylive_dir: str | Path,
) -> None:
    """Removes local copies of shinylive web assets, except for the one used by the
    current version of the shinylive python package.

    Parameters
    ----------
    shinylive_dir
        The directory where shinylive is stored. If None, the default directory will
        be used.
    """

    shinylive_dir = Path(shinylive_dir)

    version_paths = _installed_shinylive_version_paths(shinylive_dir)
    version_names = [
        re.sub("^shinylive-", "", os.path.basename(v)) for v in version_paths
    ]
    if SHINYLIVE_ASSETS_VERSION in version_names:
        print("Keeping version " + SHINYLIVE_ASSETS_VERSION)
        version_names.remove(SHINYLIVE_ASSETS_VERSION)

    remove_shinylive_assets(shinylive_dir, version_names)


def remove_shinylive_assets(
    shinylive_dir: str | Path,
    version: str | list[str],
) -> None:
    """Removes local copy of shinylive.

    Parameters
    ----------
    shinylive_dir
        The directory where shinylive is stored. If None, the default directory will
        be used.

    version
        If a version is specified, only that version will be removed.
        If None, all local versions except the version specified by SHINYLIVE_ASSETS_VERSION will be removed.
    """

    shinylive_dir = Path(shinylive_dir)

    target_dir = shinylive_dir

    if isinstance(version, str):
        version = [version]

    target_dirs = [shinylive_dir / f"shinylive-{v}" for v in version]

    if len(target_dirs) == 0:
        print(f"No versions of shinylive to remove from {shinylive_dir}/")
        return

    for target_dir in target_dirs:
        print("Removing " + str(target_dir))
        if target_dir.is_symlink():
            target_dir.unlink()
        elif target_dir.is_dir():
            shutil.rmtree(target_dir)
        else:
            print(f"{target_dir} does not exist.")


def _installed_shinylive_version_paths(
    shinylive_dir: Optional[Path] = None,
) -> list[Path]:
    if shinylive_dir is None:
        shinylive_dir = Path(shinylive_cache_dir())

    shinylive_dir = Path(shinylive_dir)
    subdirs = shinylive_dir.iterdir()
    # print(", ".join([str(s.name) for s in subdirs]))
    return [s for s in subdirs if not s.name.startswith(".")]
    subdir_names = [str(s.name) for s in subdirs]
    versions = [
        re.sub("^shinylive-", "", subdir_name)
        for subdir_name in subdir_names
        if not subdir_name.startswith(".")
    ]
    return versions


def print_shinylive_local_info(
    destdir: Path | None = None,
) -> None:
    if destdir is None:
        destdir = Path(shinylive_cache_dir())

    print(
        f"""    Local cached shinylive asset dir:
    {str(destdir)}
    """
    )
    if destdir.exists():
        print("""    Installed versions:""")
        installed_version_paths = _installed_shinylive_version_paths(destdir)
        if len(installed_version_paths) > 0:
            print("    " + "\n    ".join([str(v) for v in installed_version_paths]))
        else:
            print("    (None)")
    else:
        print("    (Cache dir does not exist)")


def _check_assets_url(
    version: str = SHINYLIVE_ASSETS_VERSION, url: Optional[str] = None
) -> bool:
    """Checks if the URL for the Shinylive assets bundle is valid.

    Returns True if the URL is valid (with a 200 status code), False otherwise.

    The reason it has both the `version` and `url` parameters is so that it behaves the
    same as `download_shinylive()` and `ensure_shinylive_assets()`.
    """
    if url is None:
        url = shinylive_bundle_url(version)

    req = urllib.request.Request(url, method="HEAD")
    resp = urllib.request.urlopen(req)
    status = resp.getcode()

    if status == 200:
        return True
    else:
        return False
