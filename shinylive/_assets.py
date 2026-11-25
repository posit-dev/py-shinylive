from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Optional, cast

from ._assets_version import (
    VERSIONS_TIME_FORMAT,
    _is_version,
    _warn_outside_default,
    assets_version,
    assets_version_input,
    assets_version_matches,
    local_assets_versions,
    max_version,
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
    """Download the Shinylive assets into `destdir`.

    Parameters
    ----------
    destdir
        The assets cache folder. Defaults to `shinylive_cache_dir()`.
    version
        The version to download from GitHub: an exact version, a series, or "latest".
        When `None`, `SHINYLIVE_ASSETS_VERSION` or the default series is used. Ignored
        when `url` is set.
    url
        A direct link to an assets tarball, such as a mirror. When set, `version` is
        not used. The folder made in `destdir` is the top-level folder of the tarball
        (`shinylive-<version>` for a release tarball).
    status
        Whether to show download progress.
    """
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
    tmp_dir = None

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
            progress_size = count * block_size
            speed = int(progress_size / (1024 * duration))
            progress_mb = f"{progress_size / (1024 * 1024):.1f}"
            if total_size > 0:
                percent = min(int(progress_size * 100 / total_size), 100)
                line = f"{percent}%, {speed} KB/s, {progress_mb}/{total_size / (1024 * 1024):.1f} MB"
            else:
                # The server did not send the size
                line = f"{speed} KB/s, {progress_mb} MB"
            sys.stderr.write("\r" + line)
            sys.stderr.flush()
            last_update_time = current_time

        tmp_name, _ = _urlretrieve(url, reporthook)
        sys.stderr.write("\n")

        print(f"Unzipping to {destdir}/", file=sys.stderr)
        # Extract to a temp dir, then move into place, so a half-extracted folder is
        # never picked up as a version. The "extract-" prefix lets `assets cleanup`
        # remove leftovers. It is made only now, so a slow download is not mistaken
        # for a leftover.
        tmp_dir = Path(tempfile.mkdtemp(prefix="extract-", dir=destdir))
        tar_safe_extractall(tmp_name, tmp_dir)
        for src in tmp_dir.iterdir():
            _move_into_place(src, destdir / src.name, src.name in existed_before)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


DOWNLOAD_TIMEOUT_SECONDS = 60


def _urlretrieve(
    url: str, reporthook: Callable[[int, int, int], None]
) -> tuple[str, None]:
    """Like `urllib.request.urlretrieve()`, but a stalled connection times out instead
    of hanging forever. The timeout is per read, so a slow download still finishes."""
    fd, name = tempfile.mkstemp(suffix=".tar.gz")
    try:
        with (
            os.fdopen(fd, "wb") as f,
            urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp,
        ):
            total = int(resp.headers.get("Content-Length") or -1)
            count = 0
            while block := resp.read(8192):
                f.write(block)
                count += 1
                reporthook(count, 8192, total)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return name, None


def _move_into_place(src: Path, target: Path, existed_before: bool) -> None:
    if target.exists() or target.is_symlink():
        if not existed_before:
            # Another process (R or Python) just finished the same download. Keep its
            # folder, which it may be reading from.
            return
        # A re-download replaces the old folder. Move it aside, move the new one in,
        # and only then delete the old one, so the folder is missing only between two
        # renames, not during a delete.
        old = target.parent / f"old-{uuid.uuid4().hex}"
        os.rename(target, old)
        try:
            _rename_into_place(src, target)
        finally:
            # `assets cleanup` (R or Python) may remove it first: `rename` keeps the
            # old folder's mtime, so it can look like an old leftover.
            if old.is_symlink():
                old.unlink(missing_ok=True)
            else:
                shutil.rmtree(old, ignore_errors=True)
        return
    _rename_into_place(src, target)


def _rename_into_place(src: Path, target: Path) -> None:
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
    "latest". Building a URL never downloads the assets, but for a series or "latest"
    (including the default, when `version` is `None`) it may check GitHub for new
    releases and update `versions.json`.
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
    import appdirs

    return appdirs.user_cache_dir("shinylive")


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


def local_build_version(build: str | Path) -> str:
    """Return the version of a local shinylive build.

    It is read from the `package.json` of the shinylive repository: in `build`, or in
    its parent (when `build` is the repository's `./build` folder).
    """
    build = Path(build).absolute()
    for dir in (build, build.parent):
        try:
            with open(dir / "package.json", encoding="utf-8") as f:
                package: object = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(package, dict):
            continue
        package = cast("dict[str, object]", package)
        version = package.get("version")
        if package.get("name") == "shinylive" and isinstance(version, str):
            if _is_version(version):
                return version
    raise RuntimeError(
        f"Can't find the shinylive version of {build}: no shinylive `package.json` "
        "in it or its parent folder. Pass the version to use."
    )


def local_build_target_version(source_dir: str | Path, version: Optional[str]) -> str:
    """Return the exact version to name a local build's folder after. When `version`
    is `None`, it is the build's own version.

    Only an exact version is allowed. A series or "latest" would pick a release
    version, and the local build would replace that downloaded release."""
    if version is None:
        return local_build_version(source_dir)
    if parse_assets_version(version).kind != "exact":
        raise ValueError(
            f"A local build needs an exact version, such as "
            f"{SHINYLIVE_ASSETS_VERSION_FALLBACK!r}, not {version!r}."
        )
    _warn_outside_default(version)
    return version


def _local_target_dir(
    source_dir: str | Path, destdir: Optional[str | Path], version: Optional[str]
) -> Path:
    if destdir is None:
        destdir = Path(shinylive_cache_dir())
    version = local_build_target_version(source_dir, version)
    return Path(destdir) / f"shinylive-{version}"


def copy_shinylive_local(
    source_dir: str | Path,
    destdir: Optional[str | Path] = None,
    version: Optional[str] = None,
):
    """Copy a local shinylive build into `destdir`, as `shinylive-<version>`.
    `version` defaults to the build's own version (see `local_build_version()`)."""
    target_dir = _local_target_dir(source_dir, destdir, version)
    source_dir = Path(source_dir)
    # Check before removing the old folder, so a bad path does not lose it
    if not source_dir.is_dir():
        raise RuntimeError("Source directory does not exist: " + str(source_dir))
    _remove_path(target_dir)
    shutil.copytree(source_dir, target_dir)


def link_shinylive_local(
    source_dir: str | Path,
    destdir: Optional[str | Path] = None,
    version: Optional[str] = None,
):
    """Link a local shinylive build into `destdir`, as `shinylive-<version>`.
    `version` defaults to the build's own version (see `local_build_version()`)."""
    target_dir = _local_target_dir(source_dir, destdir, version)

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
    """Ensure that there is a local copy of the Shinylive assets, and return its folder.

    Parameters
    ----------
    destdir
        The assets cache folder. Defaults to `shinylive_cache_dir()`.
    version
        An exact version, a series, or "latest". It is resolved to an exact version,
        which names the folder to look for: `<destdir>/shinylive-<version>`. When
        `None`, the version used by this process (`assets_version()`) is used.
    url
        A direct link to an assets tarball, such as a mirror. When set, GitHub is never
        used: the version is chosen from `versions.json` and the downloaded folders,
        and a missing folder is downloaded from `url`. For a series or "latest", the
        tarball may hold any matching version; for an exact version, its top-level
        folder must be `shinylive-<version>`. Otherwise an error is raised.
    """

    if destdir is None:
        destdir = Path(shinylive_cache_dir())
        if version is None and url is None:
            # The version used by this process (which also downloads it)
            version = assets_version()
    spec = parse_assets_version(assets_version_input(version))
    # With no `url`, resolving downloads the chosen version from GitHub
    version = resolve_assets_version(
        spec.value, dir=destdir, download=url is None, check=url is None
    )

    shinylive_bundle_dir = destdir / f"shinylive-{version}"
    if not shinylive_bundle_dir.exists():
        print(f"{shinylive_bundle_dir} does not exist.", file=sys.stderr)
        before = local_assets_versions(destdir)
        download_shinylive(url=url, version=version, destdir=destdir)
        if not shinylive_bundle_dir.exists():
            # For a series, the tarball may hold a newer match than the one chosen
            added = [
                v
                for v in local_assets_versions(destdir)
                if v not in before and assets_version_matches(v, spec)
            ]
            if len(added) == 0:
                raise RuntimeError(
                    f"The tarball at {url} has no {shinylive_bundle_dir.name} folder."
                )
            version = max_version(added)
            shinylive_bundle_dir = destdir / f"shinylive-{version}"

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
        # `assets_version_input()` also rejects a bad SHINYLIVE_ASSETS_VERSION
        keep = [SHINYLIVE_ASSETS_VERSION_DEFAULT, assets_version_input()]

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
        try:
            if now - path.lstat().st_mtime > minutes * 60:
                print(f"Removing leftover temp file {path}")
                _remove_path(path)
        except FileNotFoundError:
            # Another process (such as an R cleanup) removed it first
            pass


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
