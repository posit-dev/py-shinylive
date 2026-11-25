"""Tests for the `shinylive` command line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from shinylive._main import main

from .conftest import make_app


def test_export_long_template_params(
    fake_assets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A JSON string longer than a file name can be
    title = "x" * 300
    app = make_app(tmp_path / "myapp")
    site = tmp_path / "site"
    params = json.dumps({"title": title})
    result = CliRunner().invoke(
        main, ["export", str(app), str(site), "--template-params", params]
    )
    assert result.exit_code == 0, result.output
    assert (site / "index.html").read_text() == f"<title>{title}</title>"


def test_assets_remove_help_has_no_stray_quote():
    result = CliRunner().invoke(main, ["assets", "remove", "--help"])
    assert 'of local copies of assets."' not in result.output
