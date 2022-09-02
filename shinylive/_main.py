import json
from pathlib import Path
from typing import Optional, Union

import click

from . import _assets, _deps, _export, _version


@click.group(
    no_args_is_help=True,
    help=f"""
    \b
    shinylive Python package version: {_version.SHINYLIVE_PACKAGE_VERSION}
    shinylive web assets version:     {_assets.SHINYLIVE_ASSETS_VERSION}
""",
)
def main() -> None:
    pass


@main.command(
    help="""
Turn a Shiny app into a bundle that can be deployed to a static web host.

APPDIR is the directory containing the Shiny application.

DESTDIR is the destination directory where the output files will be written to. This
directory can be deployed as a static web site.

This command will not include the contents of venv/ or any files that start with '.'

After writing the output files, you can serve them locally with the following command:

    python3 -m http.server --directory DESTDIR 8008
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
    subdir: Union[str, None],
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
    Commands:
      download: Download assets from the remote server.
      remove: Remove local copies of assets. By default, removes all versions except {_assets.SHINYLIVE_ASSETS_VERSION}. Can be used with --version to remove a specific version.
      info: Print information about the local assets.
      install-from-local: Install shinylive assets from a local directory. Must be used with --source.

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
    dir: Union[str, Path],
    source: Optional[str],
) -> None:
    if dir is None:
        dir = _assets.shinylive_cache_dir()
    dir = Path(dir)

    if command == "download":
        if version is None:
            version = _version.SHINYLIVE_ASSETS_VERSION
        _assets.download_shinylive(destdir=dir, version=version, url=url)
    elif command == "remove":
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
    else:
        raise click.UsageError(f"Unknown command: {command}")


@main.command(
    help="""Get a set of base dependencies for a Shinylive application.

    This is intended for use by the Shinylive Quarto extension.
""",
    no_args_is_help=True,
)
@click.option(
    "--path-prefix",
    type=str,
    default="shinylive-dist/",
    help="A prefix to prepend to the `path` for each dependency.",
    show_default=True,
)
def base_deps(path_prefix: str) -> None:
    deps = _deps.shinylive_base_deps_htmldep(path_prefix)
    print(json.dumps(deps, indent=2))


@main.command(
    help="""Get a set of dependencies for a set of Python files packaged into a .json file.

    This is intended for use by the Shinylive Quarto extension.
""",
    no_args_is_help=True,
)
@click.argument("json_file", type=str)
def package_deps(json_file: str) -> None:
    deps = _deps.package_deps_htmldep(json_file)
    print(json.dumps(deps, indent=2))
