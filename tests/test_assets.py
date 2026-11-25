"""Tests for Shinylive assets."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import shinylive._assets

# Don't run this test in CI, unless we're triggered by a release event. In the future,
# it would make sense to run this test when we're on an rc branch.
skip_if_not_release = (
    os.environ.get("CI") == "true" and os.environ.get("GITHUB_EVENT_NAME") != "release"
)


@pytest.mark.skipif(
    skip_if_not_release,
    reason="Don't run this test in CI, unless we're on a release branch.",
)
def test_assets_available():
    """
    Test that the assets are available at the remote URL. Although this test might not
    pass during development due to changing version numbers, it must pass before making
    a release.
    """
    import urllib.request

    from shinylive._version import SHINYLIVE_ASSETS_VERSION_FALLBACK

    url = shinylive._assets.shinylive_bundle_url(SHINYLIVE_ASSETS_VERSION_FALLBACK)
    req = urllib.request.Request(url, method="HEAD")
    # Raises `HTTPError` for a missing release
    with urllib.request.urlopen(req, timeout=60) as resp:
        assert resp.getcode() == 200


def test_copy_local_build_keeps_old_folder_when_source_is_missing(tmp_path: Path):
    old = tmp_path / "shinylive-0.10.16"
    old.mkdir()
    with pytest.raises(RuntimeError, match="does not exist"):
        shinylive._assets.copy_shinylive_local(
            tmp_path / "missing", tmp_path, "0.10.16"
        )
    assert old.exists()


def test_download_progress_without_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    import io
    import tarfile
    import time

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("shinylive-0.10.16/file.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    data = io.BytesIO(buf.getvalue() + b"\0" * 20000)

    class Response:
        headers: dict[str, str] = {}

        def read(self, n: int) -> bytes:
            return data.read(n)

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    clock = iter(range(0, 1000, 2))
    monkeypatch.setattr(time, "time", lambda: next(clock))

    def urlopen(*args: object, **kwargs: object) -> Response:
        return Response()

    monkeypatch.setattr(shinylive._assets.urllib.request, "urlopen", urlopen)
    shinylive._assets.download_shinylive(tmp_path, url="https://example.com/x.tar.gz")
    err = capsys.readouterr().err
    assert "MB" in err
    assert "-" not in err.split("Unzipping")[0].split("...")[1]
    assert (tmp_path / "shinylive-0.10.16" / "file.txt").exists()
