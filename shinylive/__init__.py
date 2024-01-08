"""A package for packaging Shiny applications that run on Python in the browser."""

from ._url import decode_shinylive_url, encode_shinylive_url
from .version import SHINYLIVE_PACKAGE_VERSION

__version__ = SHINYLIVE_PACKAGE_VERSION

__all__ = ("decode_shinylive_url", "encode_shinylive_url")
