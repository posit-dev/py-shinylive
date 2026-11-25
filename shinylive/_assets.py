from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

from ._assets_version import (
    VERSIONS_TIME_FORMAT,
    assets_version,
    assets_version_input,
    assets_version_matches,
    local_assets_versions,
    parse_assets_version,
    read_versions_json,
    resolve_assets_version,
)
from ._utils import tar_safe_extractall
from ._version import (
    SHINYLIVE_ASSETS_VERSION_DEFAULT,
    SHINYLIVE_ASSETS_VERSION_FALLBACK,
)


def download_shinylive(
    destdir: str | Path | None = None,
    version: Optional[str] = None,
    url: Optional[str] = None,
    status: bool = True,
) -> None:
    """Download the assets. `version` may be an exact version, a series, or "latest".
    When `None`, `SHINYLIVE_ASSETS_VERSION` or the default series is used."""
    if destdir is None:
        # Note that this is the cache directory, which is the parent of the assets
        # directory. The tarball will have the assets directory as the top-level subdir.
        destdir = shinylive_cache_dir()
    destdir = Path(destdir)

    if url is None:
        version = resolve_assets_version(
            assets_version_input(version), dir=destdir, download=False
        )
        url = shinylive_bundle_url(version)

    destdir.mkdir(parents=True, exist_ok=True)
    existed_before = {p.name for p in destdir.iterdir()}
    tmp_name = None
    # Extract to a temp dir, then move into place, so a half-extracted folder is never
    # picked up as a version. The "extract-" prefix lets `assets cleanup` remove
    # leftovers from an interrupted download.
    tmp_dir = Path(tempfile.mkdtemp(prefix="extract-", dir=destdir))

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
        tar_safe_extractall(tmp_name, tmp_dir)
        for src in tmp_dir.iterdir():
            _move_into_place(src, destdir / src.name, src.name in existed_before)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _move_into_place(src: Path, target: Path, existed_before: bool) -> None:
    if target.exists() or target.is_symlink():
        if not existed_before:
            # Another process (R or Python) just finished the same download. Keep its
            # folder, which it may be reading from.
            return
        # A re-download replaces the old folder. Move it aside first, so the folder is
        # missing only between two renames, not during a delete.
        old = target.parent / f"old-{uuid.uuid4().hex}"
        os.rename(target, old)
        _remove_path(old)
    try:
        os.rename(src, target)
    except OSError:
        # Another process moved its folder in after the check above
        if not target.exists():
            raise


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def shinylive_bundle_url(version: Optional[str] = None) -> str:
    """
    Returns the URL for the Shinylive assets bundle. `version` may also be a series or
    "latest"; building a URL never downloads the assets.
    """
    version = resolve_assets_version(assets_version_input(version), download=False)
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


def shinylive_assets_dir(version: Optional[str] = None) -> str:
    """
    Returns the directory containing cached Shinylive assets, for a particular version
    of Shinylive. When `version` is `None`, `assets_version()` is used.
    """
    if version is None:
        version = assets_version()
    return os.path.join(shinylive_cache_dir(), "shinylive-" + version)


def pyodide_lock_json_file(version: Optional[str] = None) -> Path:
    return (
        Path(shinylive_assets_dir(version))
        / "shinylive"
        / "pyodide"
        / "pyodide-lock.json"
    )


def codeblock_to_json_file(version: Optional[str] = None) -> str:
    p = Path(shinylive_assets_dir(version)) / "scripts" / "codeblock-to-json.js"
    return str(p)


def _local_target_dir(destdir: Optional[str | Path], version: Optional[str]) -> Path:
    if destdir is None:
        destdir = Path(shinylive_cache_dir())
    destdir = Path(destdir)
    # Name the folder after an exact version, so the default series can find it
    version = resolve_assets_version(
        assets_version_input(version), dir=destdir, download=False
    )
    return destdir / f"shinylive-{version}"


def copy_shinylive_local(
    source_dir: str | Path,
    destdir: Optional[str | Path] = None,
    version: Optional[str] = None,
):
    target_dir = _local_target_dir(destdir, version)
    source_dir = Path(source_dir)
    _remove_path(target_dir)
    shutil.copytree(source_dir, target_dir)


def link_shinylive_local(
    source_dir: str | Path,
    destdir: Optional[str | Path] = None,
    version: Optional[str] = None,
):
    target_dir = _local_target_dir(destdir, version)

    source_dir = Path(source_dir).absolute()
    if not source_dir.is_dir():
        raise RuntimeError("Source directory does not exist: " + str(source_dir))

    # Ensure parent dir exists before we create a symlink in it.
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    _remove_path(target_dir)
    target_dir.symlink_to(source_dir)


def ensure_shinylive_assets(
    destdir: Path | None = None,
    version: Optional[str] = None,
    url: Optional[str] = None,
) -> Path:
    """Ensure that there is a local copy of shinylive."""

    if destdir is None:
        destdir = Path(shinylive_cache_dir())
        # Resolving a series or "latest" downloads the chosen version
        if version is None:
            version = assets_version()
    version = resolve_assets_version(assets_version_input(version), dir=destdir)

    if not destdir.exists():
        print("Creating directory " + str(destdir), file=sys.stderr)
        destdir.mkdir(parents=True)

    shinylive_bundle_dir = destdir / f"shinylive-{version}"
    if not shinylive_bundle_dir.exists():
        print(f"{shinylive_bundle_dir} does not exist.", file=sys.stderr)
        download_shinylive(url=url, version=version, destdir=destdir)

    return shinylive_bundle_dir


def cleanup_shinylive_assets(
    shinylive_dir: str | Path,
    keep: Optional[list[str]] = None,
) -> None:
    """Removes local copies of shinylive web assets, except for those matched by
    `keep`. Also removes temp files left by interrupted downloads.

    Parameters
    ----------
    shinylive_dir
        The directory where shinylive is stored.
    keep
        Exact versions (`"0.10.16"`), series (`"0.10.*"`), or `"latest"`. For a
        series, only the newest downloaded match is kept. Defaults to the default
        series, plus the `SHINYLIVE_ASSETS_VERSION` environment variable if set.
    """

    shinylive_dir = Path(shinylive_dir)
    if not keep:
        env = os.environ.get("SHINYLIVE_ASSETS_VERSION")
        keep = [SHINYLIVE_ASSETS_VERSION_DEFAULT] + ([env] if env else [])

    versions = local_assets_versions(shinylive_dir)
    kept: list[str] = []
    for spec in [parse_assets_version(k) for k in keep]:
        matches = [v for v in versions if assets_version_matches(v, spec)]
        if spec.kind != "exact":
            # `local_assets_versions()` sorts newest first
            matches = matches[:1]
        kept.extend(v for v in matches if v not in kept)
    for v in kept:
        print("Keeping version " + v)

    remove_shinylive_assets(shinylive_dir, [v for v in versions if v not in kept])
    remove_stale_temp_files(shinylive_dir)


def remove_stale_temp_files(dir: str | Path, minutes: float = 10) -> None:
    """Removes temp files left behind when a download (R or Python) was killed. Only
    files older than `minutes` are removed, so a running download is not touched."""
    dir = Path(dir)
    if not dir.is_dir():
        return
    now = time.time()
    for path in dir.iterdir():
        if not path.name.startswith(("extract-", "old-", "versions-")):
            continue
        if now - path.lstat().st_mtime > minutes * 60:
            print(f"Removing leftover temp file {path}")
            _remove_path(path)


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
        The version, or versions, to remove.
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
        if target_dir.is_symlink() or target_dir.is_dir():
            _remove_path(target_dir)
        else:
            print(f"{target_dir} does not exist.")


def print_shinylive_local_info(
    destdir: Path | None = None,
) -> None:
    if destdir is None:
        destdir = Path(shinylive_cache_dir())

    # Report only: use the saved `versions.json`, with no network or download
    try:
        resolved = resolve_assets_version(
            assets_version_input(),
            dir=destdir,
            download=False,
            check=False,
            warn=False,
        )
    except Exception as e:
        resolved = f"unresolved ({e})"
    print(f"""    shinylive web assets version: {resolved}
    Default assets series: {SHINYLIVE_ASSETS_VERSION_DEFAULT}""")
    check = read_versions_json(destdir)
    if check is not None:
        checked_at = check.checked_at.strftime(VERSIONS_TIME_FORMAT)
        print(f"    Last checked for new assets: {checked_at}")
        if check.error is not None:
            print(f"    Last check failed: {check.error}")

    print(f"""
    Local cached shinylive asset dir:
    {str(destdir)}
    """)
    if destdir.exists():
        print("""    Installed versions:""")
        installed = local_assets_versions(destdir)
        if len(installed) > 0:
            print(
                "    "
                + "\n    ".join([str(destdir / f"shinylive-{v}") for v in installed])
            )
        else:
            print("    (None)")
    else:
        print("    (Cache dir does not exist)")


def _check_assets_url(
    version: str = SHINYLIVE_ASSETS_VERSION_FALLBACK, url: Optional[str] = None
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
