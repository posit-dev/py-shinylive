"""Choosing which Shinylive assets version to use.

A version input is one of:

* an exact version, such as `"0.10.16"`
* a series, such as `"0.10.*"` (the highest 0.10.x)
* `"latest"` (the newest release, checked on GitHub every time)

This matches the R package (posit-dev/r-shinylive#218). Both packages use the same
cache folder and the same `versions.json` file, so they choose the same version.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, NamedTuple, Optional, cast

from ._version import (
    SHINYLIVE_ASSETS_VERSION_DEFAULT,
    SHINYLIVE_ASSETS_VERSION_FALLBACK,
)

VERSIONS_CHECK_HOURS = 24
VERSIONS_RETRY_HOURS = 1
VERSIONS_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ASSETS_RELEASES_URL = "https://github.com/posit-dev/shinylive/releases"
ASSETS_RELEASES_API_URL = "https://api.github.com/repos/posit-dev/shinylive/releases"


class VersionSpec(NamedTuple):
    kind: Literal["exact", "pattern", "latest"]
    value: str
    prefix: tuple[int, ...]


def parse_assets_version(x: str) -> VersionSpec:
    if x == "latest":
        return VersionSpec("latest", x, ())
    if re.fullmatch(r"[0-9]+(\.[0-9]+)*", x):
        return VersionSpec("exact", x, _parts(x))
    if re.fullmatch(r"[0-9]+(\.[0-9]+)*\.\*", x):
        return VersionSpec("pattern", x, _parts(x[:-2]))
    raise ValueError(
        f"Invalid Shinylive assets version: {x!r}. Use an exact version "
        '("0.10.16"), a series ("0.10.*"), or "latest".'
    )


def _parts(x: str) -> tuple[int, ...]:
    return tuple(int(p) for p in x.split("."))


def _is_version(x: str) -> bool:
    return re.fullmatch(r"[0-9]+(\.[0-9]+)*", x) is not None


def assets_version_matches(version: str, spec: VersionSpec) -> bool:
    if not _is_version(version):
        return False
    parts = _parts(version)
    if spec.kind == "latest":
        return True
    if spec.kind == "exact":
        return parts == spec.prefix
    n = len(spec.prefix)
    return len(parts) > n and parts[:n] == spec.prefix


def max_version(versions: list[str]) -> str:
    return max(versions, key=_parts)


# versions.json -------------------------------------------------------------------
#
# Saved in the assets cache folder, and shared with the R package:
# {
#   "checked_at": "2026-11-20T17:03:00Z",
#   "latest": "0.11.0",
#   "versions": ["0.11.0", "0.10.17"],
#   "error": "<reason>"            # only when the last check failed
# }


@dataclass
class VersionsInfo:
    checked_at: datetime
    latest: Optional[str] = None
    versions: list[str] = field(default_factory=list[str])
    error: Optional[str] = None


def versions_json_path(dir: str | Path) -> Path:
    return Path(dir) / "versions.json"


def read_versions_json(dir: str | Path) -> VersionsInfo | None:
    # Return `None` for a missing or broken file, so the next check rewrites it
    try:
        with open(versions_json_path(dir), "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        checked_at = datetime.strptime(
            data["checked_at"], VERSIONS_TIME_FORMAT
        ).replace(tzinfo=timezone.utc)
        raw: Any = data.get("versions")
        versions = cast("list[Any]", raw) if isinstance(raw, list) else []
        latest, error = data.get("latest"), data.get("error")
        return VersionsInfo(
            checked_at=checked_at,
            latest=latest if isinstance(latest, str) else None,
            versions=[v for v in versions if isinstance(v, str)],
            error=error if isinstance(error, str) else None,
        )
    except Exception:
        return None


def write_versions_json(info: VersionsInfo, dir: str | Path) -> None:
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "checked_at": info.checked_at.strftime(VERSIONS_TIME_FORMAT),
        "latest": info.latest,
        "versions": info.versions,
    }
    if info.error is not None:
        data["error"] = info.error
    # Write to a temp file and rename, so other processes never read a half-written
    # file. The "versions-" prefix lets `assets cleanup` remove leftovers.
    fd, tmp = tempfile.mkstemp(prefix="versions-", suffix=".json", dir=dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, versions_json_path(dir))
    finally:
        Path(tmp).unlink(missing_ok=True)


def versions_check_due(info: VersionsInfo | None, now: datetime) -> bool:
    if info is None:
        return True
    hours = (now - info.checked_at).total_seconds() / 3600
    if hours < 0:
        # The clock changed
        return True
    wait = VERSIONS_CHECK_HOURS if info.error is None else VERSIONS_RETRY_HOURS
    return hours >= wait


def update_versions_info(
    dir: str | Path, *, force: bool = False, now: Optional[datetime] = None
) -> VersionsInfo | None:
    """Run the GitHub check when due (or when `force=True`) and return the versions
    info. A failed check records `error` but keeps the old versions."""
    now = now or datetime.now(timezone.utc)
    info = read_versions_json(dir)
    if not force and not versions_check_due(info, now):
        return info

    old_latest = info.latest if info else None
    old_versions = info.versions if info else []
    latest: Optional[str] = None
    try:
        latest = fetch_latest_assets_version()
        versions = old_versions
        # Fetch the full list only when the latest tag changes. This assumes releases
        # only move forward: an older series gets no new patch release after a newer
        # series is out.
        if latest != old_latest or len(versions) == 0:
            versions = fetch_assets_versions()
        new_info = VersionsInfo(checked_at=now, latest=latest, versions=versions)
    except Exception as e:
        known = ([latest] if latest else []) + old_versions
        new_info = VersionsInfo(
            checked_at=now,
            # Keep the old `latest`, so the next check fetches the full list
            latest=old_latest,
            # A newly seen latest tag is still a known release
            versions=list(dict.fromkeys(known)),
            error=str(e) or type(e).__name__,
        )

    try:
        write_versions_json(new_info, dir)
    except OSError:
        # A read-only cache (such as in a Docker image) must not stop the export. Use
        # what is saved, so that later commands that only read `versions.json` (like
        # the Quarto ones) choose the same version.
        return read_versions_json(dir)
    return new_info


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def fetch_latest_assets_version() -> str:
    """Return the newest release version, read from where `<releases>/latest`
    redirects to. This is not the GitHub API, so it has no rate limit."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(ASSETS_RELEASES_URL + "/latest", method="HEAD")
    try:
        resp = opener.open(req, timeout=3)
        url = resp.geturl()
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        url = e.headers.get("Location", "")
    return latest_tag_version(url)


def latest_tag_version(url: str) -> str:
    m = re.search(r"/releases/tag/v([0-9.]+)$", url)
    if m is None:
        raise RuntimeError(f"Can't find the latest Shinylive assets version in {url}")
    return m.group(1)


def _get_github_json(url: str, token: Optional[str]) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def fetch_assets_versions() -> list[str]:
    """Return all published (not draft, not prerelease) release versions."""
    token = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
    versions: list[str] = []
    page = 1
    while True:
        url = f"{ASSETS_RELEASES_API_URL}?per_page=100&page={page}"
        try:
            releases = _get_github_json(url, token)
        except urllib.error.HTTPError as e:
            # An expired or wrong token fails, but public releases need no token
            if e.code != 401 or not token:
                raise
            token = None
            releases = _get_github_json(url, token)
        for r in releases:
            if r.get("draft") or r.get("prerelease"):
                continue
            version = re.sub("^v", "", str(r.get("tag_name", "")))
            if _is_version(version):
                versions.append(version)
        if len(releases) < 100:
            return versions
        page += 1


# Resolving a version ---------------------------------------------------------------

_memo: dict[tuple[str, str, bool, bool], str] = {}
_warned: set[str] = set()
# The version used by this process, once chosen. See `assets_version()`.
_session_version: Optional[str] = None


def _reset() -> None:
    global _session_version
    _memo.clear()
    _warned.clear()
    _session_version = None


def assets_version_input(version: Optional[str] = None) -> str:
    """Return the version input to use: a non-`None` value wins, then the
    `SHINYLIVE_ASSETS_VERSION` environment variable, then the package default."""
    if version is not None:
        return version
    return (
        os.environ.get("SHINYLIVE_ASSETS_VERSION") or SHINYLIVE_ASSETS_VERSION_DEFAULT
    )


def assets_version() -> str:
    """Return the exact assets version used by this process.

    The first call resolves the version (which may use the network or download the
    assets). Later calls return the same version, so one command uses one version.
    """
    global _session_version
    if _session_version is None:
        _session_version = resolve_assets_version(assets_version_input())
    return _session_version


def set_assets_version(version: str) -> None:
    """Set the exact assets version that `assets_version()` returns."""
    global _session_version
    if version != _session_version:
        from ._deps import clear_pyodide_caches

        # The cached Pyodide package data belongs to the old version
        clear_pyodide_caches()
    _session_version = version


def local_assets_versions(dir: str | Path) -> list[str]:
    """Versions of the downloaded assets in `dir`, newest first."""
    dir = Path(dir)
    if not dir.is_dir():
        return []
    versions = [
        p.name.removeprefix("shinylive-")
        for p in dir.iterdir()
        if p.name.startswith("shinylive-") and p.is_dir()
    ]
    return sorted([v for v in versions if _is_version(v)], key=_parts, reverse=True)


def resolve_assets_version(
    version: str,
    dir: Optional[str | Path] = None,
    *,
    now: Optional[datetime] = None,
    download: bool = True,
    check: bool = True,
    warn: bool = True,
) -> str:
    """Return an exact assets version for an exact version, a series, or `"latest"`.

    When `download=True`, the chosen version is downloaded if needed. For a series or
    `"latest"`, if that fails, the highest downloaded match is used instead. When
    `check=False`, only the saved `versions.json` is read (no network). When
    `warn=False`, an exact version outside the default series does not warn.
    """
    from ._assets import download_shinylive, shinylive_cache_dir

    spec = parse_assets_version(version)
    dir = Path(dir) if dir is not None else Path(shinylive_cache_dir())
    if spec.kind == "exact":
        if warn:
            _warn_outside_default(spec.value)
        if download and spec.value not in local_assets_versions(dir):
            try:
                download_shinylive(destdir=dir, version=spec.value)
            except Exception as e:
                raise RuntimeError(
                    f"Can't download Shinylive assets v{spec.value}. Check that this "
                    "version exists and that you are online."
                ) from e
        return spec.value

    key = (spec.value, str(dir), download, check)
    if key in _memo:
        return _memo[key]

    if check:
        info = update_versions_info(dir, force=spec.kind == "latest", now=now)
    else:
        info = read_versions_json(dir)
    released = info.versions if info else []
    local = local_assets_versions(dir)
    local_matches = [v for v in local if assets_version_matches(v, spec)]
    known = list(dict.fromkeys(released + local))
    matches = [v for v in known if assets_version_matches(v, spec)]
    # The check failed and no known release matches, so the result may be old. Every
    # known release matches "latest", so any failed check makes it old.
    stale = (
        check
        and info is not None
        and info.error is not None
        and (
            spec.kind == "latest"
            or not any(assets_version_matches(v, spec) for v in released)
        )
    )

    fallback = SHINYLIVE_ASSETS_VERSION_FALLBACK
    if len(matches) == 0:
        if not assets_version_matches(fallback, spec):
            raise RuntimeError(
                f"No Shinylive assets version matches {spec.value!r}. "
                f"Known versions: {', '.join(known) or '(none)'}. "
                f"Pass an exact version instead, such as {fallback!r}."
            )
        matches = [fallback]
    chosen = max_version(matches)

    if stale:
        _warn(
            "Can't check GitHub for new Shinylive assets releases. Using "
            f"v{chosen}, which may not be the newest {spec.value!r} release. "
            f"({info.error if info else ''}) Set GITHUB_PAT if GitHub is limiting "
            "requests, or pass an exact version."
        )

    if download and chosen not in local:
        try:
            download_shinylive(destdir=dir, version=chosen)
        except Exception as e:
            if (
                len(local_matches) == 0
                and chosen != fallback
                and assets_version_matches(fallback, spec)
            ):
                try:
                    download_shinylive(destdir=dir, version=fallback)
                    local_matches = [fallback]
                except Exception:
                    pass
            if len(local_matches) == 0:
                raise RuntimeError(
                    f"Can't download Shinylive assets v{chosen}. Shinylive assets "
                    "must be downloaded once while online. Or pass the exact version "
                    "of downloaded assets."
                ) from e
            failed, chosen = chosen, max_version(local_matches)
            _warn(
                f"Can't download Shinylive assets v{failed}. Using downloaded "
                f"v{chosen} instead. ({e})"
            )

    _memo[key] = chosen
    return chosen


def _warn_outside_default(version: str) -> None:
    default = parse_assets_version(SHINYLIVE_ASSETS_VERSION_DEFAULT)
    if assets_version_matches(version, default) or version in _warned:
        return
    _warned.add(version)
    _warn(
        f"Shinylive assets v{version} are outside the default "
        f"{SHINYLIVE_ASSETS_VERSION_DEFAULT!r} series for this version of shinylive. "
        "Unexpected behavior may occur."
    )


def _warn(message: str) -> None:
    """Warn, pointing at the first caller outside the shinylive package."""
    package_dir = str(Path(__file__).parent)
    frame = sys._getframe(1)
    stacklevel = 2
    while frame.f_back is not None and frame.f_code.co_filename.startswith(package_dir):
        frame = frame.f_back
        stacklevel += 1
    warnings.warn(message, stacklevel=stacklevel)
