from __future__ import annotations

import collections
import sys
from pathlib import Path
from typing import MutableMapping, Optional

import click

from . import _assets, _deps, _export, _version
from ._utils import print_as_json


# Make sure commands are listed in the order they are added in the code.
class OrderedGroup(click.Group):
    def __init__(
        self,
        name: Optional[str] = None,
        commands: Optional[MutableMapping[str, click.Command]] = None,
        **kwargs: object,
    ):
        super(OrderedGroup, self).__init__(name, commands, **kwargs)
        #: the registered subcommands by their exported names.
        self.commands = commands or collections.OrderedDict()

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())


version_txt = f"""
    \b
    shinylive Python package version: {_version.SHINYLIVE_PACKAGE_VERSION}
    shinylive web assets version:     {_assets.SHINYLIVE_ASSETS_VERSION}
"""

# CLI structure:
# * shinylive
#     * --version
#     * export
#         * Options: --subdir, --full-shinylive, --verbose
#     * assets
#         * download
#             * Options: --version, --dir, --url
#         * cleanup
#             * Options: --dir
#         * remove VERSION
#             * Options: --dir
#         * info
#             * Options: --dir
#         * install-from-local BUILD
#             * Options: --version, --dir
#         * link-from-local BUILD
#             * Options: --version, --dir
#         * version
#     * extension
#         * info
#         * base-htmldeps
#             * Options: --sw-dir (required)
#         * language-resources
#         * app-resources
#             * Options: --json-file / stdin (required)


# #############################################################################
# ## Main
# #############################################################################


@click.group(
    invoke_without_command=True,
    no_args_is_help=True,
    help=version_txt,
    cls=OrderedGroup,
)
# > Add a --version option which immediately prints the version number and exits the
# > program.
@click.version_option(_version.SHINYLIVE_PACKAGE_VERSION, message="%(version)s")
def main() -> None:
    ...


# #############################################################################
# ## Export
# #############################################################################


@main.command(
    short_help="Turn a Shiny app into a bundle that can be deployed to a static web host.",
    help="""
Turn a Shiny app into a bundle that can be deployed to a static web host.

APPDIR is the directory containing the Shiny application.

DESTDIR is the destination directory where the output files will be written to. This
directory can be deployed as a static web site.

This command will not include the contents of venv/ or any files that start with '.'

After writing the output files, you can serve them locally with the following command:

    python3 -m http.server --directory DESTDIR --bind localhost 8008
""",
    no_args_is_help=True,
)
@click.argument("appdir", type=str)
@click.argument("destdir", type=str)
@click.option(
    "--subdir",
    type=str,
    default=None,
    help="Subdir in which to put the app.",
    show_default=True,
)
@click.option(
    "--full-shinylive",
    is_flag=True,
    default=False,
    help="Include the full Shinylive assets, including all Pyodide packages. Without this flag, only the packages needed to run the application are included.",
    show_default=True,
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Print debugging information when copying files.",
    show_default=True,
)
def export(
    appdir: str,
    destdir: str,
    subdir: str | None,
    verbose: bool,
    full_shinylive: bool,
) -> None:
    _export.export(
        appdir,
        destdir,
        subdir=subdir,
        verbose=verbose,
        full_shinylive=full_shinylive,
    )


# #############################################################################
# ## Assets
# #############################################################################


@main.group(
    short_help="Manage local copy of Shinylive web assets.",
    help=f"""Manage local copy of Shinylive web assets
    {version_txt}
""",
    no_args_is_help=True,
    cls=OrderedGroup,
)
def assets() -> None:
    pass


def upgrade_dir(dir: str | Path | None) -> Path:
    if dir is None:
        dir = _assets.shinylive_cache_dir()
    dir = Path(dir)
    return dir


@assets.command(
    name="info",
    help="Print information about the local assets.",
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory where shinylive assets are stored (if not using the default).",
)
def assets_info(
    dir: Optional[str | Path],
) -> None:
    _assets.print_shinylive_local_info(destdir=upgrade_dir(dir))


@assets.command(help="""Download specific assets from the remote server.""")
@click.option(
    "--version",
    type=str,
    default=_version.SHINYLIVE_ASSETS_VERSION,
    help="Shinylive version to download.",
    show_default=True,
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory to store shinylive assets (if not using the default).",
)
@click.option(
    "--url",
    type=str,
    default=None,
    help="URL to download from. If used, this will override --version.",
)
def download(
    version: str,
    dir: Optional[str | Path],
    url: Optional[str],
) -> None:
    if version is None:  # pyright: ignore[reportUnnecessaryComparison]
        version = _version.SHINYLIVE_ASSETS_VERSION
    _assets.download_shinylive(destdir=upgrade_dir(dir), version=version, url=url)


cleanup_help = f"Remove all versions of local assets except the currently-used version, {_assets.SHINYLIVE_ASSETS_VERSION}."


@assets.command(
    short_help=cleanup_help,
    help=cleanup_help,
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory where shinylive assets are stored (if not using the default).",
)
def cleanup(
    dir: Optional[str | Path],
) -> None:
    _assets.cleanup_shinylive_assets(shinylive_dir=upgrade_dir(dir))


@assets.command(
    short_help="Remove a specific version of local copies of assets.",
    help=f"""Remove a specific version (`VERSION`) of local copies of assets."

    For example, `VERSION` might be `{ _version.SHINYLIVE_ASSETS_VERSION }`.
    """,
    no_args_is_help=True,
)
@click.argument(
    "version",
    type=str,
    required=True,
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory where shinylive assets are stored (if not using the default).",
)
def remove(
    version: str,
    dir: Optional[str | Path],
) -> None:
    if version is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise click.UsageError("Must specify --version")
    dir = upgrade_dir(dir)
    _assets.remove_shinylive_assets(shinylive_dir=dir, version=version)


@assets.command(
    short_help="Install shinylive assets from a local shinylive build directory.",
    help="""Install shinylive assets from a local shinylive build directory (`BUILD`).

    For example, `BUILD` might be the `./build` directory of a local shinylive repository.
    """,
    no_args_is_help=True,
)
@click.option(
    "--version",
    type=str,
    default=_version.SHINYLIVE_ASSETS_VERSION,
    help="Version of the shinylive assets being copied.",
    show_default=True,
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory to store shinylive assets (if not using the default).",
)
@click.argument(
    "BUILD",
    type=str,
    required=True,
)
def install_from_local(
    source: str,
    version: str,
    dir: Optional[str | Path],
) -> None:
    if source is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise click.UsageError("Must specify --source")
    dir = upgrade_dir(dir)
    if version is None:  # pyright: ignore[reportUnnecessaryComparison]
        version = _version.SHINYLIVE_ASSETS_VERSION
    print(f"Copying shinylive-{version} from {source} to {dir}")
    _assets.copy_shinylive_local(source_dir=source, destdir=dir, version=version)


link_from_local_help = (
    "Create a symlink to shinylive assets from a local shinylive build directory."
)


@assets.command(
    short_help="Create a symlink to shinylive assets from a local shinylive build directory.",
    help="""Create a symlink to shinylive assets from a local shinylive build directory (`BUILD`).

    For example, `BUILD` might be the `./build` directory of a local shinylive repository.
    """,
    no_args_is_help=True,
)
@click.option(
    "--version",
    type=str,
    default=_version.SHINYLIVE_ASSETS_VERSION,
    help="Version of shinylive assets being linked.",
    show_default=True,
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory to store shinylive assets (if not using the default).",
)
@click.argument(
    "build",
    type=str,
    required=True,
)
def link_from_local(
    build: str,
    version: str,
    dir: Optional[str | Path],
) -> None:
    if build is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise click.UsageError("Must specify BUILD")
    dir = upgrade_dir(dir)
    if version is None:  # pyright: ignore[reportUnnecessaryComparison]
        version = _version.SHINYLIVE_ASSETS_VERSION
    print(f"Creating symlink for shinylive-{version} from {build} to {dir}")
    _assets.link_shinylive_local(source_dir=build, destdir=dir, version=version)


@assets.command(
    help="Print the version of the Shinylive assets.",
)
def version() -> None:
    print(_assets.SHINYLIVE_ASSETS_VERSION)


# #############################################################################
# ## Extension
# #############################################################################


@main.group(
    invoke_without_command=True,
    no_args_is_help=True,
    short_help="Integrate with the Quarto shinylive extension.",
    help=f"""Integrate with the Quarto shinylive extension.

    All values are returned as JSON to stdout.
    {version_txt}
""",
    cls=OrderedGroup,
)
def extension() -> None:
    pass


@extension.command(
    name="info",
    short_help="Return python package version, web assets version, and script locations.",
    help="""Return python package version, web assets version, and script locations.

    \b
    Returns:
        version: The version of the shinylive Python package.
        assets_version: The version of the supported shinylive web assets.
        scripts:
            codeblock-to-json: The path to a codeblock-to-json.js file, to be executed by Deno.
""",
)
def extension_info() -> None:
    print_as_json(
        {
            "version": _version.SHINYLIVE_PACKAGE_VERSION,
            "assets_version": _version.SHINYLIVE_ASSETS_VERSION,
            "scripts": {
                "codeblock-to-json": _assets.codeblock_to_json_file(),
            },
        }
    )
    return


base_htmldeps_help = (
    "Return the HTML dependencies for language agnostic shinylive assets."
)


@extension.command(
    short_help=base_htmldeps_help,
    help=base_htmldeps_help,
)
@click.option(
    "--sw-dir",
    type=str,
    default=None,
    help="Directory where shinylive-sw.js is located, relative to the output directory.",
)
def base_htmldeps(
    sw_dir: Optional[str] = None,
) -> None:
    print_as_json(
        _deps.shinylive_base_deps_htmldep(sw_dir=sw_dir, asset_type=("base",))
    )
    return


language_resources_help = "Return HTML dependency resources for python, specifically the pyodide and pyright support."


@extension.command(
    short_help=language_resources_help,
    help=language_resources_help,
)
def language_resources() -> None:
    print_as_json(_deps.shinylive_python_resources())
    return


app_resources_help = "Return HTML dependency resources specific to a shiny app."


@extension.command(
    short_help=app_resources_help,
    help=app_resources_help,
)
@click.option(
    "--json-file",
    type=str,
    default=None,
    help="Path to a JSON file containing the app's contents. If not specified, the JSON will be read from stdin. The JSON should be an array of objects with the following keys: 'name', 'content', 'type'.",
    show_default=True,
)
def app_resources(
    json_file: Optional[str] = None,
) -> None:
    json_content: str | None = None
    if json_file is None:
        json_content = sys.stdin.read()

    print_as_json(_deps.shinylive_app_resources(json_file, json_content))
    return


def defunct_help(cmd: str) -> str:
    return f"""The shinylive CLI command `{cmd}` is defunct.

You are using a newer version of the Python shinylive package ({ _version.SHINYLIVE_PACKAGE_VERSION }) with an older
version of the Quarto shinylive extension, and these versions are not compatible.

Please update your Quarto shinylive extension by running this command in the top level
of your Quarto project:

    quarto add quarto-ext/shinylive
"""


def defunct_error_txt(cmd: str) -> str:
    return f"Error: { defunct_help(cmd) }"


def raise_defunct(cmd: str) -> None:
    # By raising a `SystemExit()`, we avoid printing the traceback.
    raise SystemExit(defunct_error_txt(cmd))


@main.command(help=defunct_help("base-deps"), hidden=True)
def base_deps() -> None:
    raise_defunct("base-deps")


@main.command(help=defunct_help("package-deps"), hidden=True)
def package_deps() -> None:
    raise_defunct("package-deps")


@main.command(help=defunct_help("codeblock-to-json"), hidden=True)
def codeblock_to_json() -> None:
    raise_defunct("codeblock-to-json")
