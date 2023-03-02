from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from . import _assets, _deps, _export, _version


@click.group(
    invoke_without_command=True,
    no_args_is_help=True,
    help=f"""
    \b
    shinylive Python package version: {_version.SHINYLIVE_PACKAGE_VERSION}
    shinylive web assets version:     {_assets.SHINYLIVE_ASSETS_VERSION}
""",
)
@click.option(
    "--version",
    is_flag=True,
    default=False,
    help="Print version of shinylive python package.",
    show_default=True,
)
def main(version: bool) -> None:
    if version:
        print(_version.SHINYLIVE_PACKAGE_VERSION)


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


@main.command(
    help=f"""Manage local copy of Shinylive web assets

    \b
    shinylive Python package version: {_version.SHINYLIVE_PACKAGE_VERSION}
    shinylive web assets version:     {_assets.SHINYLIVE_ASSETS_VERSION}

    \b
    Commands:
      download: Download assets from the remote server.
      cleanup: Remove all versions of local assets except the currently-used version, {_assets.SHINYLIVE_ASSETS_VERSION}.
      remove: Remove a specific version of local copies of assets. Must be used with --version.
      info: Print information about the local assets.
      install-from-local: Install shinylive assets from a local directory. Must be used with --source.
      link-from-local: Create a symlink to shinylive assets from a local directory. Must be used with --source. This is useful when doing development on the Shinylive web assets.

""",
    no_args_is_help=True,
)
@click.argument("command", type=str)
@click.option(
    "--version",
    type=str,
    default=None,
    help="Shinylive version to download or remove.",
    show_default=True,
)
@click.option(
    "--url",
    type=str,
    default=None,
    help="URL to download from. If used, this will override --version.",
    show_default=True,
)
@click.option(
    "--dir",
    type=str,
    default=None,
    help="Directory to store shinylive assets (if not using the default)",
)
@click.option(
    "--source",
    type=str,
    default=None,
    help="Directory where shinylive assets will be copied from. Must be used with 'copy' command.",
)
def assets(
    command: str,
    version: Optional[str],
    url: Optional[str],
    dir: Optional[str | Path],
    source: Optional[str],
) -> None:
    if dir is None:
        dir = _assets.shinylive_cache_dir()
    dir = Path(dir)

    if command == "download":
        if version is None:
            version = _version.SHINYLIVE_ASSETS_VERSION
        _assets.download_shinylive(destdir=dir, version=version, url=url)
    elif command == "cleanup":
        _assets.cleanup_shinylive_assets(shinylive_dir=dir)
    elif command == "remove":
        if version is None:
            raise click.UsageError("Must specify --version")
        _assets.remove_shinylive_assets(shinylive_dir=dir, version=version)
    elif command == "info":
        _assets.print_shinylive_local_info()
    elif command == "install-from-local":
        if source is None:
            raise click.UsageError("Must specify --source")
        if version is None:
            version = _version.SHINYLIVE_ASSETS_VERSION
        print(f"Copying shinylive-{version} from {source} to {dir}")
        _assets.copy_shinylive_local(source_dir=source, destdir=dir, version=version)
    elif command == "link-from-local":
        if source is None:
            raise click.UsageError("Must specify --source")
        if version is None:
            version = _version.SHINYLIVE_ASSETS_VERSION
        print(f"Creating symlink for shinylive-{version} from {source} to {dir}")
        _assets.link_shinylive_local(source_dir=source, destdir=dir, version=version)
    elif command == "version":
        print(_assets.SHINYLIVE_ASSETS_VERSION)
    else:
        raise click.UsageError(f"Unknown command: {command}")


@main.command(
    help="""Get a set of base dependencies for a Shinylive application.

    This is intended for use by the Shinylive Quarto extension.
""",
)
@click.option(
    "--sw-dir",
    type=str,
    default=None,
    help="Directory where shinylive-sw.js is located, relative to the output directory.",
)
def base_deps(sw_dir: Optional[str]) -> None:
    deps = _deps.shinylive_base_deps_htmldep(sw_dir)
    print(json.dumps(deps, indent=2))


@main.command(
    help="""Get a set of dependencies for a set of Python files packaged into a .json file.

    If JSON_FILE is provided, read from that file. Otherwise, read from stdin.

    This is intended for use by the Shinylive Quarto extension.
"""
)
@click.argument(
    "json_file",
    required=False,
    type=str,
    default=None,
)
def package_deps(json_file: Optional[str]) -> None:
    json_content: str | None = None
    if json_file is None:
        json_content = sys.stdin.read()

    deps = _deps.package_deps_htmldepitems(json_file, json_content)
    print(json.dumps(deps, indent=2))


@main.command(
    help="""Return the path to a codeblock-to-json.js file, to be executed by Deno.

    This is intended for use by the Shinylive Quarto extension.
"""
)
def codeblock_to_json_path() -> None:
    p = Path(_assets.shinylive_assets_dir()) / "scripts" / "codeblock-to-json.js"
    print(str(p))
