"""Tests for choosing the Shinylive assets version. No test uses the network."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pytest

import shinylive._assets as assets
import shinylive._assets_version as av
from shinylive._version import SHINYLIVE_ASSETS_VERSION_FALLBACK

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
    with pytest.warns(UserWarning, match="Can't check GitHub"):
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


def test_local_assets_versions(tmp_path: Path):
    for name in ["shinylive-0.10.9", "shinylive-0.10.16", "shinylive-dev", "other"]:
        (tmp_path / name).mkdir()
    (tmp_path / "shinylive-0.10.17").write_text("not a folder")
    write_info(tmp_path, ["0.10.17"])
    assert av.local_assets_versions(tmp_path) == ["0.10.16", "0.10.9"]
    assert av.local_assets_versions(tmp_path / "missing") == []
