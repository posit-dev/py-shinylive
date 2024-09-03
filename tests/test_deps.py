"""Tests for Shinylive dependency detection."""

import os

import pytest

from shinylive._assets import ensure_shinylive_assets


def test_requirements_txt():
    from shinylive._deps import _find_packages_in_requirements

    requirements_txt = """
    typing_extensions
    jsonschema-specifications (<1.0)
    # comment
    """

    # This should convert '_' to '-', and remove the version constraints.
    assert _find_packages_in_requirements(requirements_txt) == [
        "typing-extensions",
        "jsonschema-specifications",
    ]

    # Should preserve case here (in other steps it will be lowercased).
    assert _find_packages_in_requirements("Jinja2") == ["Jinja2"]
    assert _find_packages_in_requirements("jinja2") == ["jinja2"]


# ======================================================================================
# Don't run remaining tests in CI, unless we're triggered by a release event. This is
# because they require the assets to be installed. In the future, it would make sense to
# run this test when we're on an rc branch.
# ======================================================================================
skip_if_not_release = (
    os.environ.get("CI") == "true" and os.environ.get("GITHUB_EVENT_NAME") != "release"
)


@pytest.mark.skipif(
    skip_if_not_release,
    reason="Don't run this test in CI, unless we're on a release branch.",
)
def test_module_to_package_key():
    ensure_shinylive_assets()

    from shinylive._deps import module_to_package_key

    assert module_to_package_key("cv2") == "opencv-python"
    assert module_to_package_key("black") == "black"
    assert module_to_package_key("jinja2") == "jinja2"

    # Should be case sensitive for module names.
    assert module_to_package_key("Jinja2") is None

    assert module_to_package_key("foobar") is None


@pytest.mark.skipif(
    skip_if_not_release,
    reason="Don't run this test in CI, unless we're on a release branch.",
)
def test_dep_name_to_dep_key():
    ensure_shinylive_assets()

    from shinylive._deps import dep_name_to_dep_key

    assert dep_name_to_dep_key("black") == "black"
    assert dep_name_to_dep_key("typing-extensions") == "typing-extensions"
    assert (
        dep_name_to_dep_key("jsonschema_specifications-tests")
        == "jsonschema-specifications-tests"
    )

    # Should not convert `_` to `-`
    assert dep_name_to_dep_key("typing_extensions") is None

    # Should be case insensitive to input.
    assert dep_name_to_dep_key("Jinja2") == "jinja2"
    assert dep_name_to_dep_key("JiNJa2") == "jinja2"

    assert dep_name_to_dep_key("cv2") is None

    # Special case for a base pyodide package. It is not in pyodide_lock.json but should
    # be included in the list of dependencies.
    assert dep_name_to_dep_key("distutils") == "distutils"


@pytest.mark.skipif(
    skip_if_not_release,
    reason="Don't run this test in CI, unless we're on a release branch.",
)
def test_find_recursive_deps():
    ensure_shinylive_assets()

    from shinylive._deps import _find_recursive_deps

    # It is possible that these dependencies will change in future versions of Pyodide,
    # but the reason we're testing jsonschema specifically is because it includes
    # jsonschema_specifications, which is the package name (and not the key).
    assert sorted(_find_recursive_deps(["jsonschema"])) == [
        "attrs",
        "jsonschema",
        "jsonschema_specifications",
        "pyrsistent",
        "referencing",
        "rpds-py",
        "six",
    ]

    assert sorted(_find_recursive_deps(["opencv-python"])) == [
        "numpy",
        "opencv-python",
    ]
