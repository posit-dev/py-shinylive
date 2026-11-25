# The version of this Python package.
SHINYLIVE_PACKAGE_VERSION = "0.8.13"

# The Shinylive assets series used by default. Patch releases in this series are picked
# up without a package release. Bump for a new minor series.
SHINYLIVE_ASSETS_VERSION_DEFAULT = "0.10.*"

# A known-good version in the default series, tested at package release. Used when no
# matching version is known.
SHINYLIVE_ASSETS_VERSION_FALLBACK = "0.10.16"

# Kept for code that imported it. The version in use is `assets_version()`.
SHINYLIVE_ASSETS_VERSION = SHINYLIVE_ASSETS_VERSION_FALLBACK
