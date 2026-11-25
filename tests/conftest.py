from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest

import shinylive._assets as assets
import shinylive._assets_version as av
from shinylive._deps import clear_pyodide_caches
from shinylive._version import SHINYLIVE_ASSETS_VERSION_FALLBACK

FAKE_PACKAGES: dict[str, dict[str, Any]] = {
    "micropip": {
        "name": "micropip",
        "version": "1.0",
        "file_name": "micropip-1.0-py3-none-any.whl",
        "install_dir": "site",
        "sha256": "",
        "depends": ["packaging"],
        "imports": ["micropip"],
    },
    "packaging": {
        "name": "packaging",
        "version": "1.0",
        "file_name": "packaging-1.0-py3-none-any.whl",
        "install_dir": "site",
        "sha256": "",
        "depends": [],
        "imports": ["packaging"],
    },
    "numpy": {
        "name": "numpy",
        "version": "1.0",
        "file_name": "numpy-1.0-py3-none-any.whl",
        "install_dir": "site",
        "sha256": "",
        "depends": [],
        "imports": ["numpy"],
    },
}
FAKE_LOCK: dict[str, object] = {"info": {}, "packages": FAKE_PACKAGES}


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def fake_assets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """A small offline assets cache with the fallback version, used by this process.

    Returns the `shinylive-<version>` folder."""
    cache = tmp_path / "cache"
    root = cache / f"shinylive-{SHINYLIVE_ASSETS_VERSION_FALLBACK}"
    _write(root / "shinylive-sw.js")
    _write(root / "scripts" / "codeblock-to-json.js")
    _write(root / "export_template" / "index.html", "<title>{{title}}</title>")
    _write(root / "export_template" / "edit" / "index.html", "{{REL_PATH}}")
    sl = root / "shinylive"
    for f in ["shinylive.js", "shinylive.css", "load-shinylive-sw.js", "examples.json"]:
        _write(sl / f)
    _write(sl / "webr" / "webr.js")
    _write(sl / "pyright" / "pyright.js")
    _write(sl / "pyodide" / "fonts" / "font.woff")
    for f in ["pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip"]:
        _write(sl / "pyodide" / f)
    _write(sl / "pyodide" / "pyodide-lock.json", json.dumps(FAKE_LOCK))
    for pkg in FAKE_PACKAGES.values():
        _write(sl / "pyodide" / pkg["file_name"])

    av._reset()
    clear_pyodide_caches()
    monkeypatch.setenv("SHINYLIVE_ASSETS_VERSION", SHINYLIVE_ASSETS_VERSION_FALLBACK)
    monkeypatch.setattr(assets, "shinylive_cache_dir", lambda: str(cache))

    def no_warning(version: str) -> None:
        pass

    monkeypatch.setattr(av, "_warn_outside_default", no_warning)
    yield root
    av._reset()
    clear_pyodide_caches()


def make_app(dir: Path) -> Path:
    _write(dir / "app.py", "from shiny.express import ui\nui.p('hi')\n")
    _write(dir / "www" / "style.css", "p {}")
    return dir


def app_json_names(dir: Path) -> list[str]:
    with open(dir / "app.json", encoding="utf-8") as f:
        return [file["name"] for file in json.load(f)]
