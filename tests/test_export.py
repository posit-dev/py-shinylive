"""Tests for `shinylive export`, with a small offline assets cache."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shinylive._export import export

from .conftest import app_json_names, make_app


def test_export_writes_site(fake_assets: Path, tmp_path: Path):
    app = make_app(tmp_path / "myapp")
    site = tmp_path / "site"
    export(app, site)
    assert app_json_names(site) == ["app.py", "www/style.css"]
    assert (site / "index.html").read_text() == "<title>Shiny App</title>"
    assert (site / "shinylive" / "shinylive.js").exists()
    # The base packages and their dependencies are copied, others are not
    pyodide = site / "shinylive" / "pyodide"
    assert (pyodide / "micropip-1.0-py3-none-any.whl").exists()
    assert (pyodide / "packaging-1.0-py3-none-any.whl").exists()
    assert not (pyodide / "numpy-1.0-py3-none-any.whl").exists()


@pytest.mark.parametrize(
    "appdir, destdir", [(".", "."), ("myapp", "."), ("site/myapp", "site")]
)
def test_export_destdir_must_not_hold_appdir(
    fake_assets: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    appdir: str,
    destdir: str,
):
    monkeypatch.chdir(tmp_path)
    make_app(tmp_path / appdir)
    with pytest.raises(ValueError, match="separate"):
        export(appdir, destdir)
    assert not (tmp_path / destdir / "app.json").exists()


def test_export_inside_app_with_mixed_paths(
    fake_assets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    app = make_app(tmp_path / "myapp")
    monkeypatch.chdir(app)
    # An absolute appdir and a relative destdir inside it
    export(app, "site")
    export(app, "site")
    assert app_json_names(app / "site") == ["app.py", "www/style.css"]
    # And the other way around
    app2 = make_app(tmp_path / "myapp2")
    monkeypatch.chdir(app2)
    export(".", app2 / "site")
    export(".", app2 / "site")
    assert app_json_names(app2 / "site") == ["app.py", "www/style.css"]


def test_read_app_files_order_is_stable(tmp_path: Path):
    from shinylive._app_json import read_app_files

    app = make_app(tmp_path / "myapp")
    for d in ["c", "a", "b", "venv", ".git", "__pycache__"]:
        (app / d).mkdir()
        (app / d / "f.txt").write_text("x")
    names = [f["name"] for f in read_app_files(app, tmp_path / "site")]
    assert names == ["app.py", "a/f.txt", "b/f.txt", "c/f.txt", "www/style.css"]


def test_export_nested_subdir_and_destdir(fake_assets: Path, tmp_path: Path):
    app = make_app(tmp_path / "myapp")
    site = tmp_path / "out" / "site"
    export(app, site, subdir="a/b")
    assert app_json_names(site / "a" / "b") == ["app.py", "www/style.css"]
    assert (site / "a" / "b" / "edit" / "index.html").read_text() == "../../"


@pytest.mark.parametrize("subdir", ["..", "../x", "a/../../x"])
def test_export_subdir_must_stay_inside_destdir(
    fake_assets: Path, tmp_path: Path, subdir: str
):
    app = make_app(tmp_path / "myapp")
    with pytest.raises(ValueError, match="subdir"):
        export(app, tmp_path / "site", subdir=subdir)
    assert not (tmp_path / "x").exists()


def test_export_subdir_dot_is_no_subdir(fake_assets: Path, tmp_path: Path):
    app = make_app(tmp_path / "myapp")
    export(app, tmp_path / "site", subdir=".")
    assert (tmp_path / "site" / "edit" / "index.html").read_text() == ""
