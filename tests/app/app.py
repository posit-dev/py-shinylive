"""Small app used by `.github/workflows/test-deploy-app.yaml`.

It depends on `faicons` (see `requirements.txt`) so the export also exercises
the path where a package is installed from the app's requirements rather than
coming from base Pyodide.
"""

from faicons import icon_svg
from shiny import App, render, ui

app_ui = ui.page_fluid(
    ui.h2(icon_svg("gear"), " shinylive export smoke test"),
    ui.input_slider("n", "N", 0, 100, 40),
    ui.output_code("txt"),
)


def server(input, output, session):
    @render.code
    def txt():
        return f"n*2 is {input.n() * 2}"


app = App(app_ui, server)
