"""Tests for shinylive.io URL encoding and decoding."""

from shinylive._url import FileContentJson, ShinyliveApp, url_decode

LINKS = {
    "py": {
        "editor": "https://shinylive.io/py/editor/#code=NobwRAdghgtgpmAXGKAHVA6VBPMAaMAYwHsIAXOcpMAMwCdiYACAZwAsBLCbJjmVYnTJMAgujxM6lACZw6EgK4cAOhDABfALpA5g",
        "app": "https://shinylive.io/py/app/#code=NobwRAdghgtgpmAXGKAHVA6VBPMAaMAYwHsIAXOcpMAMwCdiYACAZwAsBLCbJjmVYnTJMAgujxM6lACZw6EgK4cAOhDABfALpA",
        "app_no_header": "https://shinylive.io/py/app/#h=0&code=NobwRAdghgtgpmAXGKAHVA6VBPMAaMAYwHsIAXOcpMAMwCdiYACAZwAsBLCbJjmVYnTJMAgujxM6lACZw6EgK4cAOhDABfALpA",
    },
    "r": {
        "editor": "https://shinylive.io/r/editor/#code=NobwRAdghgtgpmAXGKAHVA6ASmANGAYwHsIAXOMpMAGwEsAjAJykYE8AKAZwAtaJWAlAB0IYAL4BdIA",
        "app": "https://shinylive.io/r/app/#code=NobwRAdghgtgpmAXGKAHVA6ASmANGAYwHsIAXOMpMAGwEsAjAJykYE8AKAZwAtaJWAlAB0IYAL4BdIA",
        "app_no_header": "https://shinylive.io/r/app/#h=0&code=NobwRAdghgtgpmAXGKAHVA6ASmANGAYwHsIAXOMpMAGwEsAjAJykYE8AKAZwAtaJWAlAB0IYAL4BdIA",
    },
}


def test_decode_py_editor():
    app = url_decode(LINKS["py"]["editor"])
    assert app._language == "py"
    assert app.mode == "editor"
    assert app._bundle[0]["name"] == "app.py"
    assert "from shiny import" in app._bundle[0]["content"]
    assert "type" not in app._bundle[0]


def test_decode_py_app():
    app = url_decode(LINKS["py"]["app"])
    assert app._language == "py"
    assert app.mode == "app"
    assert app.header
    assert app._bundle[0]["name"] == "app.py"
    assert "from shiny import" in app._bundle[0]["content"]
    assert "type" not in app._bundle[0]


def test_decode_py_app_no_header():
    app = url_decode(LINKS["py"]["app_no_header"])
    assert app._language == "py"
    assert app.mode == "app"
    assert not app.header
    assert app._bundle[0]["name"] == "app.py"
    assert "from shiny import" in app._bundle[0]["content"]
    assert "type" not in app._bundle[0]


def test_decode_r_editor():
    app = url_decode(LINKS["r"]["editor"])
    assert app._language == "r"
    assert app.mode == "editor"
    assert app._bundle[0]["name"] == "app.R"
    assert "library(shiny)" in app._bundle[0]["content"]
    assert "type" not in app._bundle[0]


def test_decode_r_app():
    app = url_decode(LINKS["r"]["app"])
    assert app._language == "r"
    assert app.mode == "app"
    assert app.header
    assert app._bundle[0]["name"] == "app.R"
    assert "library(shiny)" in app._bundle[0]["content"]
    assert "type" not in app._bundle[0]


def test_decode_r_app_no_header():
    app = url_decode(LINKS["r"]["app_no_header"])
    assert app._language == "r"
    assert app.mode == "app"
    assert not app.header
    assert app._bundle[0]["name"] == "app.R"
    assert "library(shiny)" in app._bundle[0]["content"]
    assert "type" not in app._bundle[0]


def test_encode_py_app_content():
    app_code = "from shiny.express import ui\nui.div()"
    app = ShinyliveApp.from_text(app_code)

    assert app._language == "py"
    assert str(app) == app.to_url()
    assert app._bundle == [
        {
            "name": "app.py",
            "content": app_code,
        }
    ]
    assert "## file: app.py" in app.to_chunk_contents()
    assert app_code in app.to_chunk_contents()


def test_encode_r_app_content():
    app_code = "library(shiny)\n\nshinyApp(pageFluid(), function(...) { })"
    app = ShinyliveApp.from_text(app_code)

    assert app._language == "r"
    assert str(app) == app.to_url()
    assert app._bundle == [
        {
            "name": "app.R",
            "content": app_code,
        }
    ]
    assert "## file: app.R" in app.to_chunk_contents()
    assert app_code in app.to_chunk_contents()


# Files ------------------------------------------------------------------------------
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402


def make_url_app(dir: Path) -> Path:
    (dir / "www").mkdir(parents=True)
    (dir / "app.py").write_text("from shiny import App\n")
    (dir / "x.txt").write_text("1")
    (dir / "www" / "s.css").write_text("p {}")
    return dir / "app.py"


def names(app: ShinyliveApp) -> list[str]:
    return [f["name"] for f in app._bundle]


def test_files_can_be_folders(tmp_path: Path):
    app_py = make_url_app(tmp_path)
    app = ShinyliveApp.from_local(app_py, [tmp_path / "www", tmp_path / "x.txt"])
    assert names(app) == ["app.py", "www/s.css", "x.txt"]


def test_add_file_overwrite_replaces(tmp_path: Path):
    app_py = make_url_app(tmp_path)
    app = ShinyliveApp.from_local(app_py, [tmp_path / "x.txt"])
    (tmp_path / "x.txt").write_text("2")
    app.add_file(tmp_path / "x.txt", overwrite=True)
    assert names(app) == ["app.py", "x.txt"]
    assert app._bundle[1]["content"] == "2"


def test_remove_file_removes(tmp_path: Path):
    app_py = make_url_app(tmp_path)
    app = ShinyliveApp.from_local(app_py, [tmp_path / "x.txt", tmp_path / "www"])
    assert names(app - "x.txt") == ["app.py", "www/s.css"]
    assert names(app - (tmp_path / "www" / "s.css")) == ["app.py", "x.txt"]
    app.remove_file("x.txt")
    assert names(app) == ["app.py", "www/s.css"]
    with pytest.raises(ValueError, match="not found"):
        app.remove_file("nope.txt")


def test_mixed_relative_and_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    app_py = make_url_app(tmp_path / "app")
    monkeypatch.chdir(tmp_path)
    app = ShinyliveApp.from_local(
        os.path.join("app", "app.py"), [app_py.parent / "x.txt"]
    )
    assert names(app) == ["app.py", "x.txt"]


def test_add_dir_outside_the_app_folder(tmp_path: Path):
    app_py = make_url_app(tmp_path / "app")
    other = tmp_path / "other" / "assets"
    other.mkdir(parents=True)
    (other / "z.css").write_text("z")
    app = ShinyliveApp.from_local(app_py).add_dir(other)
    assert names(app) == ["app.py", "assets/z.css"]


def test_files_folder_outside_the_app_keeps_its_name(tmp_path: Path):
    app_py = make_url_app(tmp_path / "app")
    shared = tmp_path / "shared" / "www"
    (shared / "a").mkdir(parents=True)
    (shared / "b").mkdir()
    (shared / "a" / "x.css").write_text("1")
    (shared / "b" / "x.css").write_text("2")
    app = ShinyliveApp.from_local(app_py, [shared])
    assert names(app) == ["app.py", "www/a/x.css", "www/b/x.css"]


def test_files_folder_in_text_app_keeps_its_name(tmp_path: Path):
    make_url_app(tmp_path)
    app = ShinyliveApp.from_text("from shiny import App\n", [tmp_path / "www"])
    assert names(app) == ["app.py", "www/s.css"]


def test_write_files_makes_folders(tmp_path: Path):
    bundle: list[FileContentJson] = [
        {"name": "app.py", "content": "from shiny import App\n"},
        {"name": "www/s.css", "content": "p { content: 'é' }"},
    ]
    out = ShinyliveApp(bundle, "py").write_files(tmp_path / "out")
    assert (out / "www" / "s.css").read_bytes().decode("utf-8") == "p { content: 'é' }"


@pytest.mark.parametrize("name", ["../evil.txt", "a/../../evil.txt", "/tmp/evil.txt"])
def test_write_files_stays_inside_dest(tmp_path: Path, name: str):
    bundle: list[FileContentJson] = [{"name": name, "content": "x"}]
    with pytest.raises(ValueError, match="outside"):
        ShinyliveApp(bundle, "py").write_files(tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_decode_language_and_mode_on_other_hosts():
    bundle: list[FileContentJson] = [{"name": "app.R", "content": "library(shiny)"}]
    url = ShinyliveApp(bundle, "r", mode="app", host="http://localhost:8080").to_url()
    app = url_decode(url)
    assert app._language == "r"
    assert app.mode == "app"
    assert app.host == "http://localhost:8080"


def test_files_folder_holding_the_app_skips_the_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    app_py = make_url_app(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = ShinyliveApp.from_local(app_py, ["."])
    assert names(app) == ["app.py", "x.txt", "www/s.css"]
