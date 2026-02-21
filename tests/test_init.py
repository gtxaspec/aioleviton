"""Tests for aioleviton package init."""

import logging

import aioleviton


def test_version_set():
    """Package exposes __version__."""
    assert isinstance(aioleviton.__version__, str)
    assert aioleviton.__version__  # not empty


def test_all_exports_importable():
    """Every name in __all__ is importable from the package."""
    for name in aioleviton.__all__:
        obj = getattr(aioleviton, name)
        assert obj is not None


def test_enable_debug_logging():
    """enable_debug_logging sets the aioleviton logger to DEBUG."""
    logger = logging.getLogger("aioleviton")
    original = logger.level
    try:
        aioleviton.enable_debug_logging()
        assert logger.level == logging.DEBUG
    finally:
        logger.setLevel(original)


def test_all_list_contents():
    """__all__ contains the expected public API names."""
    expected = {
        "AuthToken",
        "Breaker",
        "Ct",
        "enable_debug_logging",
        "LevitonAuthError",
        "LevitonClient",
        "LevitonConnectionError",
        "LevitonError",
        "LevitonInvalidCode",
        "LevitonTokenExpired",
        "LevitonTwoFactorRequired",
        "LevitonWebSocket",
        "Panel",
        "Permission",
        "Residence",
        "Whem",
    }
    assert set(aioleviton.__all__) == expected
