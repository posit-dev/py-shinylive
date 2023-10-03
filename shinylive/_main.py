from __future__ import annotations

import collections
import json
import sys
from pathlib import Path
from typing import MutableMapping, Optional

import click

from . import _assets, _deps, _export, _version


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
#         * Options: --verbose, --subdir, --full-shinylive
#     * assets
#         * download
#             * Options: --version, --dir, --url
#         * cleanup
#             * Options: --dir
#         * remove
#             * Options: --version (required), --dir
#         * info
#             * Options: --dir
#         * install-from-local
#             * Options: --version, --dir, --source (required)
#         * link-from-local
#             * Options: --version, --dir, --source (required)
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
    "--verbose",
    is_flag=True,
    default=False,
    help="Print debugging information when copying files.",
    show_default=True,
)
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


@assets.command(help="""Download assets from the remote server.""")
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


@assets.command(
    help=f"Remove all versions of local assets except the currently-used version, {_assets.SHINYLIVE_ASSETS_VERSION}."
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
    help="Remove a specific version of local copies of assets.",
    no_args_is_help=True,
)
@click.option(
    "--version",
    type=str,
    help="Shinylive version to remove.",
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


@assets.command(
    help="Install shinylive assets from a local directory.",
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
@click.option(
    "--source",
    type=str,
    default=None,
    help="Directory where shinylive assets will be copied from.",
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


@assets.command(
    help="""Create a symlink to shinylive assets from a local shinylive build directory.""",
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
@click.option(
    "--source",
    type=str,
    default=None,
    help="Directory where shinylive assets will be linked from.",
    required=True,
)
def link_from_local(
    source: str,
    version: str,
    dir: Optional[str | Path],
) -> None:
    if source is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise click.UsageError("Must specify --source")
    dir = upgrade_dir(dir)
    if version is None:  # pyright: ignore[reportUnnecessaryComparison]
        version = _version.SHINYLIVE_ASSETS_VERSION
    print(f"Creating symlink for shinylive-{version} from {source} to {dir}")
    _assets.link_shinylive_local(source_dir=source, destdir=dir, version=version)


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
    help="""Retrieve python package version, web assets version, and script locations.

    \b
    Scripts:
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


@extension.command(
    help="""Retrieve the HTML dependencies for language agnostic shinylive assets."""
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


@extension.command(
    help="""Retrieve HTML dependency resources for python, specifically the pyodide and pyright support."""
)
def language_resources() -> None:
    print_as_json(_deps.shinylive_python_resources())
    return


@extension.command(
    help="""Retrieve HTML dependency resources specific to a shiny app."""
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


@main.command(
    help="""Please update your Quarto shinylive extension to the latest version.""",
    hidden=True,
    deprecated=True,
)
def base_deps() -> None:
    raise RuntimeError(
        "This command is deprecated. Please update your Quarto shinylive extension."
    )


@main.command(
    help="""Please update your Quarto shinylive extension to the latest version.""",
    hidden=True,
    deprecated=True,
)
def package_deps() -> None:
    raise RuntimeError(
        "This command is deprecated. Please update your Quarto shinylive extension."
    )


@main.command(
    help="""Please update your Quarto shinylive extension to the latest version.""",
    hidden=True,
    deprecated=True,
)
def codeblock_to_json() -> None:
    raise RuntimeError(
        "This command is deprecated. Please update your Quarto shinylive extension."
    )


def print_as_json(x: object) -> None:
    print(json.dumps(x, indent=None))
