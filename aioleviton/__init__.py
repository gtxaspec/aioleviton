"""Async Python client for the Leviton My Leviton cloud API."""

__version__ = "0.3.0"

import logging


def enable_debug_logging() -> None:
    """Enable DEBUG logging for the aioleviton library.

    Sets the root 'aioleviton' logger to DEBUG so all modules
    (client, websocket, etc.) emit debug output. Callers can also
    do this manually: logging.getLogger("aioleviton").setLevel(logging.DEBUG)
    """
    logging.getLogger(__name__).setLevel(logging.DEBUG)


from .base_client import BaseLevitonClient
from .client import LevitonClient
from .exceptions import (
    LevitonAuthError,
    LevitonConnectionError,
    LevitonError,
    LevitonInvalidCode,
    LevitonTokenExpired,
    LevitonTwoFactorRequired,
)
from .models import AuthToken, Breaker, Ct, Panel, Permission, Residence, Whem
from .websocket import LevitonWebSocket

__all__ = [
    "AuthToken",
    "BaseLevitonClient",
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
]
