"""Tests for Shinylive assets."""

import os

import pytest

import shinylive._assets

# Don't run this test in CI, unless we're triggered by a release event. In the future,
# it would make sense to run this test when we're on an rc branch.
skip_if_not_release = (
    os.environ.get("CI") == "true" and os.environ.get("GITHUB_EVENT_NAME") != "release"
)


@pytest.mark.skipif(
    skip_if_not_release,
    reason="Don't run this test in CI, unless we're on a release branch.",
)
def test_assets_available():
    """
    Test that the assets are available at the remote URL. Although this test might not
    pass during development due to changing version numbers, it must pass before making
    a release.
    """
    assert shinylive._assets._check_assets_url() is True
