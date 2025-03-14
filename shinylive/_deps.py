from __future__ import annotations

import ast
import copy
import functools
import json
import os
import re
import sys
from pathlib import Path
from textwrap import dedent
from typing import Callable, Iterable, Literal, Optional, Tuple

# Even though TypedDict is available in Python 3.8, because it's used with NotRequired,
# they should both come from the same typing module.
# https://peps.python.org/pep-0655/#usage-in-python-3-11
if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict

from ._app_json import FileContentJson
from ._assets import (
    ensure_shinylive_assets,
    pyodide_lock_json_file,
    shinylive_assets_dir,
)
from ._version import SHINYLIVE_ASSETS_VERSION

# Files in Pyodide that should always be included.
BASE_PYODIDE_FILES = {
    "pyodide.asm.js",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
}

# Packages that should always be included in a Shinylive deployment.
BASE_PYODIDE_PACKAGE_NAMES = {"distutils", "micropip", "ssl", "pyodide-http"}
AssetType = Literal["base", "python", "r"]


# =============================================================================
# Data structures used in pyodide/pyodide-lock.json
# =============================================================================
# Note: This block of code is copied from /scripts/pyodide_packages.py
class PyodidePackageInfo(TypedDict):
    name: str
    version: str
    file_name: str
    install_dir: Literal["lib", "site"]
    sha256: str
    depends: list[str]
    imports: list[str]
    unvendored_tests: NotRequired[bool]


# The package information structure used by Pyodide's pyodide-lock.json.
# Note that the key in `packages` may be something like "jsonschema-specifications",
# but the actual name of the package may be different, like "jsonschema_specifications".
# (The "name" entry in the PyodidePackageInfo object is the actual package name.)
# And also further note that the module names in the "imports" list are not necessarily
# the same as either: the "opencv-python" package has a module name "cv2".
class PyodideLockFile(TypedDict):
    info: dict[str, str]
    packages: dict[str, PyodidePackageInfo]


# =============================================================================
# HTML Dependency types
# =============================================================================
class HtmlDepItem(TypedDict):
    name: str
    path: str
    attribs: NotRequired[dict[str, str]]


class HtmlDepServiceworkerItem(TypedDict):
    source: str
    destination: str


class QuartoHtmlDependency(TypedDict):
    name: str
    version: NotRequired[str]
    scripts: NotRequired[list[str | HtmlDepItem]]
    stylesheets: NotRequired[list[str | HtmlDepItem]]
    resources: NotRequired[list[HtmlDepItem]]
    meta: NotRequired[dict[str, str]]
    serviceworkers: NotRequired[list[HtmlDepServiceworkerItem]]


# =============================================================================
# Conversion functions
# =============================================================================
def _dep_names_to_pyodide_pkg_infos(
    dep_names: Iterable[str],
) -> list[PyodidePackageInfo]:
    pyodide_lock = _pyodide_lock_data()
    pkg_infos: list[PyodidePackageInfo] = []

    for dep_name in dep_names:
        dep_key = dep_name_to_dep_key(dep_name)
        if dep_key is None:
            continue
        pkg_info = copy.deepcopy(pyodide_lock["packages"][dep_key])
        pkg_infos.append(pkg_info)

    return pkg_infos


def _pyodide_pkg_info_to_quarto_html_dep_item(
    pkg: PyodidePackageInfo,
) -> HtmlDepItem:
    """
    Convert a PyodidePackageInfo object to a HtmlDepItem object.
    """

    assets_dir = shinylive_assets_dir()

    return {
        "name": os.path.join("shinylive", "pyodide", pkg["file_name"]),
        "path": os.path.join(assets_dir, "shinylive", "pyodide", pkg["file_name"]),
    }


def _pyodide_pkg_infos_to_quarto_html_dep_items(
    pkgs: list[PyodidePackageInfo],
) -> list[HtmlDepItem]:
    return [_pyodide_pkg_info_to_quarto_html_dep_item(pkg) for pkg in pkgs]


# =============================================================================
# Shinylive base dependencies
# =============================================================================
def shinylive_base_deps_htmldep(
    sw_dir: Optional[str] = None,
    *,
    asset_type: Tuple[AssetType] = ("base",),
) -> list[QuartoHtmlDependency]:
    return [
        _serviceworker_dep(sw_dir),
        _shinylive_common_dep_htmldep(asset_type=asset_type),
    ]


def shinylive_python_resources() -> list[HtmlDepItem]:
    ret: list[HtmlDepItem] = []

    # Add python support file
    rel_paths = shinylive_common_files(asset_type=("python",))
    assets_dir = shinylive_assets_dir()
    ret.extend(
        [
            {"name": rel_path, "path": os.path.join(assets_dir, rel_path)}
            for rel_path in rel_paths
        ]
    )

    # Add base python packages as resources
    ret.extend(base_package_deps_htmldepitems())

    return ret


# Not used in practice!
def shinylive_r_resources() -> list[HtmlDepItem]:
    rel_paths = shinylive_common_files(asset_type=("r",))
    assets_dir = shinylive_assets_dir()
    return [
        {"name": rel_path, "path": os.path.join(assets_dir, rel_path)}
        for rel_path in rel_paths
    ]


# =============================================================================
# Common dependencies
# =============================================================================
def _shinylive_common_dep_htmldep(
    *,
    asset_type: Tuple[AssetType, ...] = (
        "base",
        "python",
    ),
) -> QuartoHtmlDependency:
    """
    Return an HTML dependency object consisting of files that are base dependencies; in
    other words, the files that are always included in a Shinylive deployment.
    """
    assets_dir = shinylive_assets_dir()

    # First, get the list of base files.
    base_files = shinylive_common_files(asset_type=asset_type)

    # Next, categorize the base files into scripts, stylesheets, and resources.
    scripts: list[str | HtmlDepItem] = []
    stylesheets: list[str | HtmlDepItem] = []
    resources: list[HtmlDepItem] = []

    for file in base_files:
        if os.path.basename(file) in [
            "load-shinylive-sw.js",
            "run-python-blocks.js",
        ]:
            script_item: HtmlDepItem = {
                "name": file,
                "path": os.path.join(assets_dir, file),
                "attribs": {"type": "module"},
            }

            scripts.append(script_item)

        if os.path.basename(file) in [
            "shinylive.css",
        ]:
            stylesheets.append(
                {
                    "name": file,
                    "path": os.path.join(assets_dir, file),
                }
            )
        else:
            resources.append(
                {
                    "name": file,
                    "path": os.path.join(assets_dir, file),
                }
            )

    # Sort scripts so that load-shinylive-sw.js is first, and run-python-blocks.js is
    # last.
    def scripts_sort_fun(x: str | HtmlDepItem) -> int:
        if isinstance(x, str):
            filename = x
        else:
            filename = os.path.basename(x["name"])

        if filename == "load-shinylive-sw.js":
            return 0
        elif filename == "run-python-blocks.js":
            return 2
        else:
            return 1

    scripts.sort(key=scripts_sort_fun)

    return {
        "name": "shinylive",
        "version": SHINYLIVE_ASSETS_VERSION,
        "scripts": scripts,
        "stylesheets": stylesheets,
        "resources": resources,
    }


def shinylive_common_files(
    *,
    asset_type: Tuple[AssetType, ...],
) -> list[str]:
    """
    Return a list of asset files for Python, and/or R, and/or language-agnostic (base) dependencies
    """
    ensure_shinylive_assets()

    has_base = "base" in asset_type
    has_python = "python" in asset_type
    has_r = "r" in asset_type

    base_files: list[str] = []
    for root, dirs, files in os.walk(shinylive_assets_dir()):
        root = Path(root)
        rel_root = root.relative_to(shinylive_assets_dir())
        if rel_root == Path("."):
            dirs.remove("scripts")
            dirs.remove("export_template")
            if not has_base:
                # No files to add here
                files = []
        elif rel_root == Path("shinylive"):
            files.remove("examples.json")
            # Remove webr folder as it is only needed for R support
            if not has_r:
                dirs.remove("webr")
            if not has_python:
                dirs.remove("pyodide")
                dirs.remove("pyright")
            if not has_base:
                # No files to add here
                files = []
        elif rel_root == Path("shinylive/pyodide"):
            dirs.remove("fonts")
            files[:] = BASE_PYODIDE_FILES

        for file in files:
            if file.startswith("."):
                continue
            base_files.append(str(rel_root / file))

    return base_files


def _serviceworker_dep(sw_dir: Optional[str] = None) -> QuartoHtmlDependency:
    dep: QuartoHtmlDependency = {
        "name": "shinylive-serviceworker",
        "version": SHINYLIVE_ASSETS_VERSION,
        "serviceworkers": [
            {
                "source": shinylive_assets_dir() + "/shinylive-sw.js",
                "destination": "/shinylive-sw.js",
            }
        ],
    }

    if sw_dir is not None:
        # Add meta tag to tell load-shinylive-sw.js where to find shinylive-sw.js.
        dep["meta"] = {"shinylive:serviceworker_dir": sw_dir}

    return dep


# =============================================================================
# Find which packages are used by a Shiny application
# =============================================================================
def shinylive_app_resources(
    json_file: Optional[str | Path],
    json_content: Optional[str],
) -> list[HtmlDepItem]:
    """
    Find package dependencies from an app.json file, and return as a list of
    QuartoHtmlDependency objects.

    Requires either `json_file` or `json_content`, but not both.
    """

    if (json_file is None and json_content is None) or (
        json_file is not None and json_content is not None
    ):
        raise RuntimeError("Must provide either `json_file` or `json_content`.")

    file_contents: list[FileContentJson] = []

    if json_file is not None:
        json_file = Path(json_file)
        with open(json_file, encoding="utf-8") as f:
            file_contents = json.load(f)

    if json_content is not None:
        file_contents = json.loads(json_content)

    pkg_infos = find_package_deps(file_contents)
    deps = _pyodide_pkg_infos_to_quarto_html_dep_items(pkg_infos)
    return deps


def find_package_deps(
    app_contents: list[FileContentJson],
    verbose_print: Callable[..., None] = lambda *args: None,
) -> list[PyodidePackageInfo]:
    """
    Find package dependencies from the contents of an app.json file. The returned data
    structure is a list of PyodidePackageInfo objects.
    """

    imports: set[str] = _find_import_app_contents(app_contents)
    imports = imports.union(_find_requirements_app_contents(app_contents))

    verbose_print("Imports detected in app:\n ", ", ".join(sorted(imports)))

    dep_names = _find_recursive_deps(imports, verbose_print)
    pkg_infos = _dep_names_to_pyodide_pkg_infos(dep_names)

    return pkg_infos


def base_package_deps_htmldepitems() -> list[HtmlDepItem]:
    """
    Return list of python packages that should be included in all python Shinylive
    deployments. The returned data structure is a list of HtmlDepItem objects
    representing PyodidePackageInfo objects.
    """
    pkg_infos = base_package_deps()
    deps = _pyodide_pkg_infos_to_quarto_html_dep_items(pkg_infos)

    return deps


def base_package_deps() -> list[PyodidePackageInfo]:
    """
    Return list of python packages that should be included in all python Shinylive
    deployments. The returned data structure is a list of PyodidePackageInfo objects.
    """
    dep_names = _find_recursive_deps(BASE_PYODIDE_PACKAGE_NAMES)
    pkg_infos = _dep_names_to_pyodide_pkg_infos(dep_names)

    return pkg_infos


# =============================================================================
# Internal functions
# =============================================================================
def _find_recursive_deps(
    dep_names: Iterable[str],
    verbose_print: Callable[..., None] = lambda *args: None,
) -> list[str]:
    """
    Given a list of packages, recursively find all dependencies that are contained in
    pyodide-lock.json. This returns a list of all dependencies, including the original
    packages passed in.
    """
    pyodide_lock = _pyodide_lock_data()

    # The keys in pyodide_lock are not the same as the package names. For example, the
    # key "jsonschema-specifications" points to an object where the "name" entry is
    # "jsonschema_specifications". The dependencies are listed with names, not keys.

    dep_names = list(dep_names)
    i = 0
    while i < len(dep_names):
        dep_name = dep_names[i]
        dep_key: str | None = dep_name_to_dep_key(dep_name)

        if dep_key not in pyodide_lock["packages"]:
            if dep_name not in BASE_PYODIDE_PACKAGE_NAMES:
                # TODO: Need to distinguish between built-in packages and external ones in
                # requirements.txt.
                verbose_print(
                    f"  {dep_name} not in pyodide-lock.json. Assuming it is in base Pyodide or in requirements.txt."
                )
            dep_names.remove(dep_name)
            continue

        dep_depnames = set(pyodide_lock["packages"][dep_key]["depends"])
        new_depnames = dep_depnames.difference(dep_names)
        dep_names.extend(new_depnames)
        i += 1

    return dep_names


def dep_name_to_dep_key(name: str) -> str | None:
    """
    Convert a package name to a key that can be used to look up the package in
    pyodide-lock.json.

    The keys in pyodide-lock.json are not the same as the package names. For example,
    the key "jsonschema-specifications" points to an object where the "name" entry is
    "jsonschema_specifications".

    Note that the names are lowercased because the package names should be treated as
    case-insensitive. https://github.com/pyodide/pyodide/issues/1614
    """
    # Special case for base pyodide packages
    if name in BASE_PYODIDE_PACKAGE_NAMES:
        return name

    name = name.lower()
    if name not in _dep_name_to_dep_key_mappings():
        return None

    return _dep_name_to_dep_key_mappings()[name]


@functools.lru_cache
def _dep_name_to_dep_key_mappings() -> dict[str, str]:
    """
    Return a dictionary that maps package names to keys. This is needed because
    sometimes the package name and package key are different. For example, the package
    name is "jsonschema_specifications", but the package key is
    "jsonschema-specifications".

    Note that the names are lowercased because the package names should be treated as
    case-insensitive. https://github.com/pyodide/pyodide/issues/1614
    """
    name_to_key: dict[str, str] = {}

    pyodide_lock = _pyodide_lock_data()
    for key, pkg_info in pyodide_lock["packages"].items():
        name = pkg_info["name"].lower()
        name_to_key[name] = key

    return name_to_key


def _find_import_app_contents(app_contents: list[FileContentJson]) -> set[str]:
    """
    Given an app.json file, find packages that are imported.
    """
    imports: set[str] = set()
    for file_content in app_contents:
        if not file_content["name"].endswith(".py"):
            continue

        imports = imports.union(_find_imports(file_content["content"]))

    # Note that at this point, the imports are module names, like "cv2", but these can
    # sometimes differ from the package names, like "opencv-python". We need to map from
    # module names to package names.
    packages = [module_to_package_key(x) for x in imports]
    packages = [x for x in packages if x is not None]

    return set(packages)


def _find_requirements_app_contents(app_contents: list[FileContentJson]) -> set[str]:
    """
    Given an app.json file, find packages that are listed in requirements.txt. This does
    not include version constraints, nor does it include packages at URLs.

    The purpose of this function is to find packages that are provided by Pyodide, so
    that we can copy those dependencies into the Shinylive assets directory.
    """
    packages: set[str] = set()
    for file_content in app_contents:
        if file_content["name"] != "requirements.txt":
            continue

        packages = packages.union(
            _find_packages_in_requirements(file_content["content"])
        )

    return packages


def module_to_package_key(module: str) -> str | None:
    """
    Given a module name, like "cv2", return the corresponding package name, like
    "opencv-python". If not found, return None.
    """
    module_to_package = _module_to_package_key_mappings()
    if module in module_to_package:
        return module_to_package[module]
    else:
        return None


@functools.lru_cache
def _module_to_package_key_mappings() -> dict[str, str]:
    """
    Return a dictionary that maps module names to package names. This is needed because
    sometimes the module name and package name are different. For example, the module
    name is "cv2", but the package name is "opencv-python".
    """
    pyodide_lock = _pyodide_lock_data()
    module_to_package: dict[str, str] = {}
    for pkg_key, pkg_info in pyodide_lock["packages"].items():
        modules = pkg_info["imports"]
        for module in modules:
            module_to_package[module] = pkg_key

    return module_to_package


@functools.lru_cache
def _pyodide_lock_data() -> PyodideLockFile:
    """
    Read in the Pyodide pyodide-lock.json file and return the contents. The result is
    cached, so if the file changes, it won't register until the Python session is
    restarted.
    """
    with open(pyodide_lock_json_file(), "r", encoding="utf-8") as f:
        return json.load(f)


# From pyodide._base.find_imports
def _find_imports(source: str) -> list[str]:
    """
    Finds the imports in a Python source code string

    Parameters
    ----------
    source : str
       The Python source code to inspect for imports.

    Returns
    -------
    ``list[str]``
        A list of module names that are imported in ``source``. If ``source`` is not
        syntactically correct Python code (after dedenting), returns an empty list.

    Examples
    --------
    >>> from pyodide import find_imports
    >>> source = "import numpy as np; import scipy.stats"
    >>> find_imports(source)
    ['numpy', 'scipy']
    """
    # handle mis-indented input from multi-line strings
    source = dedent(source)

    try:
        mod = ast.parse(source)
    except SyntaxError:
        return []
    imports: set[str] = set()
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            for name in node.names:
                node_name = name.name
                imports.add(node_name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            if module_name is None:
                continue
            imports.add(module_name.split(".")[0])
    return list(sorted(imports))


def _find_packages_in_requirements(req_txt: str) -> list[str]:
    """
    Given the contents of a requirements.txt, return list of package names.

    This returns a list of package names in a requirements.txt file. The purpose of this
    function is to find packages that are provided by Pyodide, so that we can copy those
    dependencies into the Shinylive assets directory.

    This function only returns names; it does not include version constraints. It also
    ignores packages that are at URLs (because we can be sure those packages aren't be
    provided by Pyodide).

    Parameters
    ----------
    source : str
       The contents of a requirements.txt to inspect for package names.

    Returns
    -------
    :
        A list of package names.
    """
    reqs: list[str] = []
    lines = req_txt.split("\n")

    for line in lines:
        line = line.strip()
        if line == "" or line.startswith("#"):
            continue
        # If it's a URL, then it must be a wheel file. Ignore it.
        if line.startswith("http://") or line.startswith("https://"):
            continue
        else:
            # If we got here, it's a package specification.
            # Remove any trailing version info: "my-package (>= 1.0.0)" -> "my-package"
            pkg_name = re.sub(r"([a-zA-Z0-9._-]+)(.*)", r"\1", line).strip()
            # Replace underscores with hyphens: "typing_extensions" -> "typing-extensions"
            pkg_name = pkg_name.replace("_", "-")

            reqs.append(pkg_name)

    return reqs
