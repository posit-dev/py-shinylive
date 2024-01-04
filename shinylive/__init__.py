"""A package for packaging Shiny applications that run on Python in the browser."""

from . import _version
from ._url import make_shinylive_url

__version__ = _version.SHINYLIVE_PACKAGE_VERSION
