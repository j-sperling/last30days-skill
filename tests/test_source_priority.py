"""Tests for source resolution priority hierarchy (v3 subset).

Validates the core priority chain for X source resolution:
  Bird authenticated -> XAI_API_KEY -> ScrapeCreators -> None

Note: Tests for get_x_source_with_method, extract_browser_credentials,
_AUTH_TOKEN_SOURCE tracking, and SETUP_COMPLETE gating are omitted
(those APIs are not yet ported to v3).
"""

from unittest.mock import patch

import pytest

from scripts.lib import env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_config(**overrides):
    """Return a minimal config dict with typical defaults."""
    cfg = {
        "AUTH_TOKEN": None,
        "CT0": None,
        "XAI_API_KEY": None,
        "SCRAPECREATORS_API_KEY": None,
        "OPENAI_API_KEY": None,
        "OPENROUTER_API_KEY": None,
        "PARALLEL_API_KEY": None,
        "BRAVE_API_KEY": None,
        "BSKY_HANDLE": None,
        "BSKY_APP_PASSWORD": None,
        "TRUTHSOCIAL_TOKEN": None,
        "FROM_BROWSER": None,
    }
    cfg.update(overrides)
    return cfg


def _mock_bird_installed(installed=True):
    """Patch bird_x.is_bird_installed to return the given value."""
    return patch("scripts.lib.bird_x.is_bird_installed", return_value=installed)


def _mock_bird_authenticated(username=None):
    """Patch bird_x.is_bird_authenticated to return the given value."""
    return patch("scripts.lib.bird_x.is_bird_authenticated", return_value=username)


def _mock_bird_status(installed=True, authenticated=True, username="env AUTH_TOKEN"):
    """Patch bird_x.get_bird_status to return a status dict."""
    return patch("scripts.lib.bird_x.get_bird_status", return_value={
        "installed": installed,
        "authenticated": authenticated,
        "username": username,
        "can_install": True,
    })


# ---------------------------------------------------------------------------
# Tests: get_x_source() backward compat
# ---------------------------------------------------------------------------

class TestGetXSourceBackwardCompat:
    """Ensure get_x_source() returns the correct source string."""

    def test_bird_returns_bird(self):
        config = _base_config(AUTH_TOKEN="tok", CT0="ct0")
        with _mock_bird_installed(True), _mock_bird_authenticated("env AUTH_TOKEN"):
            assert env.get_x_source(config) == "bird"

    def test_xai_returns_xai(self):
        config = _base_config(XAI_API_KEY="key")
        with _mock_bird_installed(True), _mock_bird_authenticated(None):
            assert env.get_x_source(config) == "xai"

    def test_scrapecreators_returns_scrapecreators(self):
        config = _base_config(SCRAPECREATORS_API_KEY="sc_key")
        with _mock_bird_installed(True), _mock_bird_authenticated(None):
            assert env.get_x_source(config) == "scrapecreators"

    def test_none_returns_none(self):
        config = _base_config()
        with _mock_bird_installed(False):
            assert env.get_x_source(config) is None


# ---------------------------------------------------------------------------
# Tests: get_x_source_status()
# ---------------------------------------------------------------------------

class TestGetXSourceStatus:
    """Test that get_x_source_status() returns expected fields."""

    def test_bird_authenticated(self):
        config = _base_config(AUTH_TOKEN="tok", CT0="ct0")
        with _mock_bird_installed(True), _mock_bird_authenticated("env AUTH_TOKEN"), \
             _mock_bird_status(installed=True, authenticated=True, username="env AUTH_TOKEN"):
            status = env.get_x_source_status(config)

        assert status["source"] == "bird"
        assert status["bird_installed"] is True
        assert status["bird_authenticated"] is True
        assert "xai_available" in status

    def test_xai_api(self):
        config = _base_config(XAI_API_KEY="key")
        with _mock_bird_installed(True), _mock_bird_authenticated(None), \
             _mock_bird_status(installed=True, authenticated=False, username=None):
            status = env.get_x_source_status(config)

        assert status["source"] == "xai"
        assert status["xai_available"] is True

    def test_no_source(self):
        config = _base_config()
        with _mock_bird_installed(False), \
             _mock_bird_status(installed=False, authenticated=False, username=None):
            status = env.get_x_source_status(config)

        assert status["source"] is None


# ---------------------------------------------------------------------------
# Tests: get_available_sources() with various configs
# ---------------------------------------------------------------------------

class TestGetAvailableSources:
    """Test get_available_sources() returns correct strings."""

    def test_no_x_no_web_reddit_only(self):
        """No X source, no web keys -> 'reddit' (Reddit always available)."""
        config = _base_config()
        result = env.get_available_sources(config)
        assert result == "reddit"

    def test_xai_key_no_web(self):
        """XAI_API_KEY set, no web keys -> 'both'."""
        config = _base_config(XAI_API_KEY="key")
        result = env.get_available_sources(config)
        assert result == "both"

    def test_no_x_with_web(self):
        """No X source, web keys -> 'reddit-web'."""
        config = _base_config(BRAVE_API_KEY="brave-key")
        result = env.get_available_sources(config)
        assert result == "reddit-web"

    def test_xai_with_web(self):
        """XAI_API_KEY + web keys -> 'all'."""
        config = _base_config(XAI_API_KEY="key", BRAVE_API_KEY="brave-key")
        result = env.get_available_sources(config)
        assert result == "all"

    def test_reddit_hn_polymarket_always_available(self):
        """Reddit, HN, and Polymarket are always available regardless of config."""
        assert env.is_hackernews_available() is True
        assert env.is_polymarket_available() is True
        # Reddit: get_available_sources always includes it
        config = _base_config()
        result = env.get_available_sources(config)
        assert result in ("reddit", "reddit-web")  # never 'none'
