"""Tests for Shinylive dependency detection."""


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


def test_module_to_package_key():
    from shinylive._deps import module_to_package_key

    assert module_to_package_key("cv2") == "opencv-python"
    assert module_to_package_key("black") == "black"
    assert module_to_package_key("foobar") == None


def test_dep_name_to_dep_key():
    from shinylive._deps import dep_name_to_dep_key

    assert dep_name_to_dep_key("black") == "black"
    assert dep_name_to_dep_key("typing-extensions") == "typing-extensions"
    assert (
        dep_name_to_dep_key("jsonschema_specifications-tests")
        == "jsonschema-specifications-tests"
    )

    # Should not convert `_` to `-`
    assert dep_name_to_dep_key("typing_extensions") == None

    # Should be case insensitive to input.
    assert dep_name_to_dep_key("Jinja2") == "jinja2"
    assert dep_name_to_dep_key("JiNJa2") == "jinja2"

    assert dep_name_to_dep_key("cv2") == None


def test_find_recursive_deps():
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
