"""Tests for shinylive.io URL encoding and decoding."""

from shinylive._url import *

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
