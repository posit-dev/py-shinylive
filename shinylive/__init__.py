"""A package for packaging Shiny applications that run on Python in the browser."""

from . import _version
from ._url import (
    create_shinylive_bundle_file,
    create_shinylive_bundle_text,
    create_shinylive_url,
    decode_shinylive_url,
)

__version__ = _version.SHINYLIVE_PACKAGE_VERSION

__all__ = (
    "decode_shinylive_url",
    "create_shinylive_url",
    "create_shinylive_bundle_text",
    "create_shinylive_bundle_file",
)
