"""Tests for choosing the Shinylive assets version. No test uses the network."""

from __future__ import annotations

import io
import json
import os
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import pytest
from click.testing import CliRunner

import shinylive._assets as assets
import shinylive._assets_version as av
from shinylive._main import main, use_quarto_assets_version
from shinylive._version import SHINYLIVE_ASSETS_VERSION_FALLBACK

# Saved before the `offline` fixture replaces it
real_fetch_assets_versions = av.fetch_assets_versions
REAL_DOWNLOAD = assets.download_shinylive

NOW = datetime(2026, 11, 20, 17, 3, 0, tzinfo=timezone.utc)


class Calls:
    def __init__(self) -> None:
        self.latest = 0
        self.versions = 0
        self.downloads: list[str] = []


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Calls]:
    """Fail on any network use unless a test replaces these functions."""
    av._reset()
    monkeypatch.delenv("SHINYLIVE_ASSETS_VERSION", raising=False)
    monkeypatch.setattr(assets, "shinylive_cache_dir", lambda: str(tmp_path))
    calls = Calls()

    def no_network() -> str:
        raise AssertionError("network used")

    def fake_download(destdir: Path, version: str, **kwargs: object) -> None:
        calls.downloads.append(version)
        (Path(destdir) / f"shinylive-{version}").mkdir(parents=True)

    monkeypatch.setattr(av, "fetch_latest_assets_version", no_network)
    monkeypatch.setattr(av, "fetch_assets_versions", no_network)
    monkeypatch.setattr(assets, "download_shinylive", fake_download)
    yield calls
    av._reset()


def fake_github(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, latest: str, versions: list[str]
) -> None:
    def fetch_latest() -> str:
        calls.latest += 1
        return latest

    def fetch_versions() -> list[str]:
        calls.versions += 1
        return versions

    monkeypatch.setattr(av, "fetch_latest_assets_version", fetch_latest)
    monkeypatch.setattr(av, "fetch_assets_versions", fetch_versions)


def write_info(dir: Path, versions: list[str], *, hours_ago: float = 0, **kw: str):
    info = av.VersionsInfo(
        checked_at=NOW - timedelta(hours=hours_ago),
        latest=versions[0] if versions else None,
        versions=versions,
        **kw,
    )
    av.write_versions_json(info, dir)


def test_parse_assets_version():
    assert av.parse_assets_version("0.10.16") == ("exact", "0.10.16", (0, 10, 16))
    assert av.parse_assets_version("0.10.*") == ("pattern", "0.10.*", (0, 10))
    assert av.parse_assets_version("latest").kind == "latest"
    for bad in ["", "*", "v0.10.16", "0.*.*", "0.10.x", "0.10.16 ", "newest"]:
        with pytest.raises(ValueError):
            av.parse_assets_version(bad)


def test_assets_version_matches():
    series = av.parse_assets_version("0.10.*")
    assert av.assets_version_matches("0.10.17", series)
    assert not av.assets_version_matches("0.10", series)
    assert not av.assets_version_matches("0.100.1", series)
    assert not av.assets_version_matches("0.1.0", series)
    assert not av.assets_version_matches("dev", series)
    exact = av.parse_assets_version("0.10.16")
    assert av.assets_version_matches("0.10.16", exact)
    assert not av.assets_version_matches("0.10.17", exact)
    assert av.max_version(["0.10.9", "0.10.16", "0.9.20"]) == "0.10.16"


def test_versions_json_round_trip_and_r_format(tmp_path: Path):
    write_info(tmp_path, ["0.10.17", "0.10.16"], error="boom")
    info = av.read_versions_json(tmp_path)
    assert info == av.VersionsInfo(NOW, "0.10.17", ["0.10.17", "0.10.16"], "boom")
    assert not list(tmp_path.glob("versions-*"))

    # As written by the R package (jsonlite)
    (tmp_path / "versions.json").write_text(
        '{\n  "checked_at": "2026-11-20T17:03:00Z",\n  "latest": "0.11.0",\n'
        '  "versions": ["0.11.0", "0.10.17"]\n}'
    )
    info = av.read_versions_json(tmp_path)
    assert info is not None and info.error is None
    assert info.versions == ["0.11.0", "0.10.17"]

    for broken in ["{", "[]", '{"checked_at": "yesterday"}']:
        (tmp_path / "versions.json").write_text(broken)
        assert av.read_versions_json(tmp_path) is None
    (tmp_path / "versions.json").write_text(
        '{"checked_at": "2026-11-20T17:03:00Z", "versions": "0.10.17"}'
    )
    assert av.read_versions_json(tmp_path).versions == []  # type: ignore


def test_versions_check_due():
    def info(hours: float, error: str | None = None):
        return av.VersionsInfo(NOW - timedelta(hours=hours), error=error)

    assert av.versions_check_due(None, NOW)
    assert not av.versions_check_due(info(23), NOW)
    assert av.versions_check_due(info(24), NOW)
    assert not av.versions_check_due(info(0.5, "boom"), NOW)
    assert av.versions_check_due(info(1, "boom"), NOW)
    assert av.versions_check_due(info(-1), NOW)


def test_update_versions_info_fetches_list_only_for_new_latest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    fake_github(monkeypatch, offline, "0.10.17", ["0.10.17", "0.10.16"])
    av.update_versions_info(tmp_path, now=NOW)
    assert (offline.latest, offline.versions) == (1, 1)

    # Not due yet
    av.update_versions_info(tmp_path, now=NOW + timedelta(hours=1))
    assert (offline.latest, offline.versions) == (1, 1)

    # Due, same latest tag: only the HEAD request
    info = av.update_versions_info(tmp_path, now=NOW + timedelta(hours=25))
    assert (offline.latest, offline.versions) == (2, 1)
    assert info is not None and info.versions == ["0.10.17", "0.10.16"]

    # New latest tag: the full list again
    fake_github(monkeypatch, offline, "0.10.18", ["0.10.18", "0.10.17"])
    av.update_versions_info(tmp_path, force=True, now=NOW + timedelta(hours=26))
    assert offline.versions == 2
    assert av.read_versions_json(tmp_path).versions[0] == "0.10.18"  # type: ignore


def test_update_versions_info_failure_keeps_old_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    write_info(tmp_path, ["0.10.17", "0.10.16"], hours_ago=30)
    monkeypatch.setattr(av, "fetch_latest_assets_version", lambda: "0.10.18")

    def fail() -> list[str]:
        raise OSError("rate limited")

    monkeypatch.setattr(av, "fetch_assets_versions", fail)
    info = av.update_versions_info(tmp_path, now=NOW)
    assert info is not None
    assert info.error == "rate limited"
    # The old latest is kept, so the next check fetches the full list
    assert info.latest == "0.10.17"
    assert info.versions == ["0.10.18", "0.10.17", "0.10.16"]
    assert av.read_versions_json(tmp_path) == info


def test_resolve_series_uses_versions_json(tmp_path: Path, offline: Calls):
    write_info(tmp_path, ["0.11.0", "0.10.17", "0.10.16"])
    assert av.resolve_assets_version("0.10.*", tmp_path, now=NOW) == "0.10.17"
    assert offline.downloads == ["0.10.17"]
    assert av.resolve_assets_version("0.11.*", tmp_path, download=False) == "0.11.0"
    assert av.resolve_assets_version("0.10.16", tmp_path) == "0.10.16"


def test_resolve_check_false_never_uses_network(tmp_path: Path):
    write_info(tmp_path, ["0.10.17"], hours_ago=100)
    v = av.resolve_assets_version("0.10.*", tmp_path, check=False, download=False)
    assert v == "0.10.17"


def test_resolve_latest_always_checks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    write_info(tmp_path, ["0.10.17"])
    fake_github(monkeypatch, offline, "0.11.0", ["0.11.0", "0.10.17"])
    assert av.resolve_assets_version("latest", tmp_path, download=False) == "0.11.0"
    assert offline.latest == 1


def test_resolve_offline_uses_local_then_fallback(tmp_path: Path):
    # The failed check is recorded, and the newest downloaded match is used
    (tmp_path / "shinylive-0.10.12").mkdir()
    (tmp_path / "shinylive-0.10.15").mkdir()
    with pytest.warns(UserWarning, match="may not be the newest"):
        v = av.resolve_assets_version("0.10.*", tmp_path, now=NOW)
    assert v == "0.10.15"
    assert av.read_versions_json(tmp_path).error  # type: ignore

    av._reset()
    empty = tmp_path / "empty"
    with pytest.warns(UserWarning):
        v = av.resolve_assets_version("0.10.*", empty, now=NOW, download=False)
    assert v == SHINYLIVE_ASSETS_VERSION_FALLBACK

    av._reset()
    with pytest.raises(RuntimeError, match="No Shinylive assets version matches"):
        av.resolve_assets_version("0.99.*", empty, now=NOW, check=False)


def test_resolve_download_failure_uses_local_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    write_info(tmp_path, ["0.10.17", "0.10.16"])
    (tmp_path / "shinylive-0.10.12").mkdir()

    def fail(**kwargs: object) -> None:
        raise OSError("offline")

    monkeypatch.setattr(assets, "download_shinylive", fail)
    with pytest.warns(UserWarning, match="Using downloaded v0.10.12"):
        assert av.resolve_assets_version("0.10.*", tmp_path, now=NOW) == "0.10.12"

    av._reset()
    (tmp_path / "shinylive-0.10.12").rmdir()
    with pytest.raises(RuntimeError, match="Can't download"):
        av.resolve_assets_version("0.10.*", tmp_path, now=NOW)


def test_resolve_download_failure_tries_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    write_info(tmp_path, ["0.10.99"])

    def download(destdir: Path, version: str, **kwargs: object) -> None:
        if version == "0.10.99":
            raise OSError("broken release")
        (Path(destdir) / f"shinylive-{version}").mkdir()

    monkeypatch.setattr(assets, "download_shinylive", download)
    with pytest.warns(UserWarning, match="broken release"):
        v = av.resolve_assets_version("0.10.*", tmp_path, now=NOW)
    assert v == SHINYLIVE_ASSETS_VERSION_FALLBACK


def test_exact_version_outside_default_warns_once():
    with pytest.warns(UserWarning, match="outside the default"):
        av.resolve_assets_version("0.9.1")
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        av.resolve_assets_version("0.9.1")
        av.resolve_assets_version(SHINYLIVE_ASSETS_VERSION_FALLBACK)


def test_assets_version_input_and_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    assert av.assets_version_input() == "0.10.*"
    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", "")
    assert av.assets_version_input() == "0.10.*"
    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", "0.10.15")
    assert av.assets_version_input() == "0.10.15"
    assert av.assets_version_input("latest") == "latest"

    assert av.assets_version() == "0.10.15"
    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", "0.10.16")
    # One process uses one version
    assert av.assets_version() == "0.10.15"
    assert assets.shinylive_assets_dir() == str(tmp_path / "shinylive-0.10.15")


def test_local_assets_versions(tmp_path: Path):
    for name in ["shinylive-0.10.9", "shinylive-0.10.16", "shinylive-dev", "other"]:
        (tmp_path / name).mkdir()
    (tmp_path / "shinylive-0.10.17").write_text("not a folder")
    write_info(tmp_path, ["0.10.17"])
    assert av.local_assets_versions(tmp_path) == ["0.10.16", "0.10.9"]
    assert av.local_assets_versions(tmp_path / "missing") == []


def test_update_versions_info_read_only_cache_returns_saved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    write_info(tmp_path, ["0.10.16"], hours_ago=30)
    fake_github(monkeypatch, offline, "0.10.17", ["0.10.17", "0.10.16"])

    def read_only(info: av.VersionsInfo, dir: Path) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(av, "write_versions_json", read_only)
    # The check finds 0.10.17, but it can't be saved. Return what is saved, so later
    # `check=False` calls (like Quarto's) choose the same version.
    info = av.update_versions_info(tmp_path, now=NOW)
    assert info is not None and info.versions == ["0.10.16"]
    checked = av.resolve_assets_version("0.10.*", tmp_path, now=NOW, download=False)
    saved = av.resolve_assets_version("0.10.*", tmp_path, check=False, download=False)
    assert checked == saved == "0.10.16"


def test_resolve_exact_version_downloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    assert av.resolve_assets_version("0.10.16", tmp_path) == "0.10.16"
    assert av.resolve_assets_version("0.10.16", tmp_path) == "0.10.16"
    assert offline.downloads == ["0.10.16"]
    assert av.resolve_assets_version("0.10.15", tmp_path, download=False) == "0.10.15"
    assert offline.downloads == ["0.10.16"]

    def fail(**kwargs: object) -> None:
        raise OSError("not found")

    monkeypatch.setattr(assets, "download_shinylive", fail)
    with pytest.raises(RuntimeError, match="Can't download Shinylive assets v0.10.99"):
        av.resolve_assets_version("0.10.99", tmp_path)


def test_fetch_assets_versions_retries_without_bad_token(
    monkeypatch: pytest.MonkeyPatch,
):
    import urllib.error

    tokens: list[str | None] = []

    def get(url: str, token: str | None) -> list[dict[str, object]]:
        tokens.append(token)
        if token is not None:
            raise urllib.error.HTTPError(url, 401, "Bad credentials", {}, None)  # type: ignore
        return [{"tag_name": "v0.10.17"}, {"tag_name": "v0.10.18", "draft": True}]

    monkeypatch.setattr(av, "_get_github_json", get)
    monkeypatch.setenv("GITHUB_PAT", "expired")
    assert real_fetch_assets_versions() == ["0.10.17"]
    assert tokens == ["expired", None]

    # Without a token, a 401 is a real error
    monkeypatch.delenv("GITHUB_PAT")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def get_no_token(url: str, token: str | None) -> list[dict[str, object]]:
        return get(url, "rejected")

    monkeypatch.setattr(av, "_get_github_json", get_no_token)
    with pytest.raises(urllib.error.HTTPError):
        real_fetch_assets_versions()


def test_warnings_point_outside_the_package(monkeypatch: pytest.MonkeyPatch):
    # Called through `assets_version()`, the warning still points here
    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", "0.9.2")
    with pytest.warns(UserWarning, match="outside the default") as record:
        av.assets_version()
    assert record[0].filename == __file__


def test_bad_env_var_names_the_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", "v0.10")
    with pytest.raises(ValueError, match="SHINYLIVE_ASSETS_VERSION environment"):
        av.assets_version_input()


def test_latest_tag_version():
    url = "https://github.com/posit-dev/shinylive/releases/tag/v0.10.17"
    assert av.latest_tag_version(url) == "0.10.17"
    for bad in ["v0.10.", "v..", "v0..10", ""]:
        with pytest.raises(RuntimeError):
            av.latest_tag_version(f"https://x/releases/tag/{bad}")


def test_stale_warning_names_the_next_check(tmp_path: Path):
    write_info(tmp_path, [], error="rate limited")
    with pytest.warns(UserWarning, match="rate limited") as record:
        av.resolve_assets_version("0.10.*", tmp_path, now=NOW, download=False)
    assert "checked again after 2026-11-20T18:03:00Z" in str(record[0].message)


def test_failed_fallback_download_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    write_info(tmp_path, ["0.10.99"])

    def fail(destdir: Path, version: str, **kwargs: object) -> None:
        raise OSError(f"no v{version}")

    monkeypatch.setattr(assets, "download_shinylive", fail)
    match = f"fallback v{SHINYLIVE_ASSETS_VERSION_FALLBACK} also failed: no v"
    with pytest.raises(RuntimeError, match=match):
        av.resolve_assets_version("0.10.*", tmp_path, now=NOW)


def test_update_versions_info_skips_list_for_same_latest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    # Releases are assumed to only move forward. With the latest tag unchanged, a new
    # patch release in an older series (here 0.10.17 after 0.11.0) is not seen until
    # the latest tag changes. Change this test only on purpose.
    write_info(tmp_path, ["0.11.0", "0.10.16"], hours_ago=30)
    fake_github(monkeypatch, offline, "0.11.0", ["0.11.0", "0.10.17", "0.10.16"])
    info = av.update_versions_info(tmp_path, now=NOW)
    assert info is not None and info.versions == ["0.11.0", "0.10.16"]
    assert offline.versions == 0


def test_cleanup_keeps_newest_of_series(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    for v in ["0.9.1", "0.10.12", "0.10.15", "0.10.16"]:
        (tmp_path / f"shinylive-{v}").mkdir()
    old_tmp = tmp_path / "extract-abc"
    old_tmp.mkdir()
    os.utime(old_tmp, (time.time() - 3600, time.time() - 3600))
    new_tmp = tmp_path / "versions-xyz.json"
    new_tmp.write_text("")

    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", "0.10.12")
    assets.cleanup_shinylive_assets(tmp_path)
    assert av.local_assets_versions(tmp_path) == ["0.10.16", "0.10.12"]
    assert not old_tmp.exists()
    assert new_tmp.exists()

    assets.cleanup_shinylive_assets(tmp_path, keep=["0.10.12"])
    assert av.local_assets_versions(tmp_path) == ["0.10.12"]


def make_bundle(path: Path, version: str, content: str) -> None:
    with tarfile.open(path, "w:gz") as tar:
        data = content.encode()
        info = tarfile.TarInfo(f"shinylive-{version}/file.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


@pytest.fixture
def real_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(assets, "download_shinylive", REAL_DOWNLOAD)
    bundle = tmp_path / "bundle.tar.gz"

    def urlretrieve(url: str, reporthook: object = None) -> tuple[str, None]:
        copy = tmp_path / "download.tar.gz"
        copy.write_bytes(bundle.read_bytes())
        return str(copy), None

    monkeypatch.setattr(assets.urllib.request, "urlretrieve", urlretrieve)
    return bundle


def test_download_moves_into_place(real_download: Path, tmp_path: Path):
    cache = tmp_path / "cache"
    make_bundle(real_download, "0.10.16", "one")
    assets.download_shinylive(destdir=cache, version="0.10.16")
    assert (cache / "shinylive-0.10.16" / "file.txt").read_text() == "one"

    # A re-download replaces the folder
    make_bundle(real_download, "0.10.16", "two")
    assets.download_shinylive(destdir=cache, version="0.10.16")
    assert (cache / "shinylive-0.10.16" / "file.txt").read_text() == "two"
    assert sorted(p.name for p in cache.iterdir()) == ["shinylive-0.10.16"]


def run_extension_info() -> dict[str, Any]:
    result = CliRunner().invoke(main, ["extension", "info"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_extension_commands_use_one_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    fake_github(monkeypatch, offline, "0.10.17", ["0.10.17", "0.10.16"])
    info = run_extension_info()
    assert info["assets_version"] == "0.10.17"
    assert info["scripts"]["codeblock-to-json"] == str(
        tmp_path / "shinylive-0.10.17" / "scripts" / "codeblock-to-json.js"
    )
    # `info` checks GitHub and downloads, so the script it reports exists
    assert offline.latest == 1 and offline.downloads == ["0.10.17"]

    # Later commands only read versions.json, even when a new release is out
    fake_github(monkeypatch, offline, "0.10.18", ["0.10.18", "0.10.17"])
    av._reset()
    use_quarto_assets_version()
    assert av.assets_version() == "0.10.17"
    assert offline.latest == 1 and offline.downloads == ["0.10.17"]


def test_extension_commands_agree_with_read_only_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    # A Docker image: 0.10.16 is downloaded, the cache can't be written, and GitHub
    # has 0.10.17
    (tmp_path / "shinylive-0.10.16").mkdir()
    fake_github(monkeypatch, offline, "0.10.17", ["0.10.17", "0.10.16"])

    def read_only(info: av.VersionsInfo, dir: Path) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(av, "write_versions_json", read_only)
    assert run_extension_info()["assets_version"] == "0.10.16"
    av._reset()
    use_quarto_assets_version()
    assert av.assets_version() == "0.10.16"
    assert offline.downloads == []


def test_ensure_assets_with_url_does_not_use_github(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, offline: Calls
):
    urls: list[str | None] = []

    def download(destdir: Path, version: str, url: str | None = None, **kw: object):
        urls.append(url)
        (Path(destdir) / f"shinylive-{version}").mkdir()

    monkeypatch.setattr(assets, "download_shinylive", download)
    write_info(tmp_path, ["0.10.17"])
    mirror = "https://example.com/shinylive-0.10.17.tar.gz"
    assets.ensure_shinylive_assets(tmp_path, version="0.10.*", url=mirror)
    assets.ensure_shinylive_assets(tmp_path, version="0.10.15", url=mirror)
    assert urls == [mirror, mirror]

    # Without a URL, the resolver downloads from GitHub, and only once
    assets.ensure_shinylive_assets(tmp_path, version="0.10.16")
    assert urls == [mirror, mirror, None]


def test_download_keeps_folder_from_another_process(
    monkeypatch: pytest.MonkeyPatch, real_download: Path, tmp_path: Path
):
    cache = tmp_path / "cache"
    make_bundle(real_download, "0.10.16", "ours")
    real_extract = assets.tar_safe_extractall

    def extract(tarfile: str, destdir: Path) -> None:
        # Another process finishes the same download while ours runs
        (cache / "shinylive-0.10.16").mkdir()
        (cache / "shinylive-0.10.16" / "file.txt").write_text("theirs")
        real_extract(tarfile, destdir)

    monkeypatch.setattr(assets, "tar_safe_extractall", extract)
    assets.download_shinylive(destdir=cache, version="0.10.16")
    assert (cache / "shinylive-0.10.16" / "file.txt").read_text() == "theirs"
    assert sorted(p.name for p in cache.iterdir()) == ["shinylive-0.10.16"]


def test_download_makes_extract_folder_after_download(
    monkeypatch: pytest.MonkeyPatch, real_download: Path, tmp_path: Path
):
    cache = tmp_path / "cache"
    make_bundle(real_download, "0.10.16", "one")
    seen: list[str] = []
    real_urlretrieve = assets.urllib.request.urlretrieve

    def urlretrieve(url: str, reporthook: object = None) -> tuple[str, None]:
        # A cleanup during the download must find no extract folder to remove
        seen.extend(p.name for p in cache.iterdir())
        return real_urlretrieve(url, reporthook)  # type: ignore

    monkeypatch.setattr(assets.urllib.request, "urlretrieve", urlretrieve)
    assets.download_shinylive(destdir=cache, version="0.10.16")
    assert seen == []


def test_remove_stale_temp_files_ignores_files_already_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    old = time.time() - 3600
    for name in ["extract-a", "old-b"]:
        (tmp_path / name).mkdir()
        os.utime(tmp_path / name, (old, old))
    real_remove = assets._remove_path

    def remove(path: Path) -> None:
        # Another process removes "old-b" first
        if path.name == "old-b":
            real_remove(path)
            raise FileNotFoundError(path)
        real_remove(path)

    monkeypatch.setattr(assets, "_remove_path", remove)
    assets.remove_stale_temp_files(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cli_rejects_bad_versions():
    runner = CliRunner()
    for args in [
        ["assets", "cleanup", "--keep", "0.10.x"],
        ["assets", "download", "--version", "newest"],
        ["export", "--assets-version", "v0.10.16", "app", "site"],
    ]:
        result = runner.invoke(main, args)
        assert result.exit_code == 2, args
        assert "Invalid Shinylive assets version" in result.output


def test_old_assets_version_constant_warns():
    import shinylive._version as version

    with pytest.warns(FutureWarning, match="no longer the Shinylive assets version"):
        assert version.SHINYLIVE_ASSETS_VERSION == SHINYLIVE_ASSETS_VERSION_FALLBACK


def make_local_build(tmp_path: Path, version: str) -> Path:
    repo = tmp_path / "shinylive-repo"
    (repo / "build").mkdir(parents=True)
    (repo / "build" / "file.txt").write_text("dev")
    (repo / "package.json").write_text(
        json.dumps({"name": "shinylive", "version": version})
    )
    return repo / "build"


def test_local_build_version(tmp_path: Path):
    build = make_local_build(tmp_path, "0.10.18")
    assert assets.local_build_version(build) == "0.10.18"
    assert assets.local_build_version(build.parent) == "0.10.18"

    (build.parent / "package.json").write_text('{"name": "other", "version": "1.0"}')
    with pytest.raises(RuntimeError, match="Can't find the shinylive version"):
        assets.local_build_version(build)


def test_install_and_link_from_local_use_build_version(tmp_path: Path):
    build = make_local_build(tmp_path, "0.10.18")
    cache = tmp_path / "cache"
    runner = CliRunner()
    for command in ["install-from-local", "link-from-local"]:
        result = runner.invoke(
            main, ["assets", command, "--dir", str(cache), str(build)]
        )
        assert result.exit_code == 0, result.output
        assert "SHINYLIVE_ASSETS_VERSION=0.10.18" in result.output
        assert (cache / "shinylive-0.10.18" / "file.txt").read_text() == "dev"

    # An explicit version still wins
    assets.copy_shinylive_local(build, cache, version="0.10.17")
    assert av.local_assets_versions(cache) == ["0.10.18", "0.10.17"]


def test_ensure_assets_with_url_errors_on_wrong_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    def download(destdir: Path, **kw: object) -> None:
        (Path(destdir) / "shinylive-other").mkdir()

    monkeypatch.setattr(assets, "download_shinylive", download)
    with pytest.raises(RuntimeError, match="has no shinylive-0.10.16 folder"):
        assets.ensure_shinylive_assets(
            tmp_path, version="0.10.16", url="https://example.com/x.tar.gz"
        )
