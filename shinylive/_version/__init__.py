# The version of this Python package.
SHINYLIVE_PACKAGE_VERSION = "0.8.13"

# The Shinylive assets series used by default. Patch releases in this series are picked
# up without a package release. Bump for a new minor series.
SHINYLIVE_ASSETS_VERSION_DEFAULT = "0.10.*"

# A known-good version in the default series, tested at package release. Used when no
# matching version is known.
SHINYLIVE_ASSETS_VERSION_FALLBACK = "0.10.16"


def __getattr__(name: str) -> str:
    # Kept for code that imported it, with a warning: it used to be the version in
    # use, but the version in use now changes over time.
    if name == "SHINYLIVE_ASSETS_VERSION":
        import warnings

        warnings.warn(
            "`SHINYLIVE_ASSETS_VERSION` is no longer the Shinylive assets version in "
            "use. It is now the fallback version, "
            f"{SHINYLIVE_ASSETS_VERSION_FALLBACK!r}. To get the version in use, run "
            "`shinylive assets version`.",
            FutureWarning,
            stacklevel=2,
        )
        return SHINYLIVE_ASSETS_VERSION_FALLBACK
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
