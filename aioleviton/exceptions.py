"""Exceptions for the aioleviton library."""


class LevitonError(Exception):
    """Base exception for Leviton API errors."""


class LevitonAuthError(LevitonError):
    """Authentication failed."""


class LevitonTwoFactorRequired(LevitonError):
    """Two-factor authentication code required (HTTP 406)."""


class LevitonInvalidCode(LevitonError):
    """Invalid two-factor authentication code (HTTP 408)."""


class LevitonConnectionError(LevitonError):
    """Network or API connection error."""


class LevitonTokenExpired(LevitonAuthError):
    """Authentication token has expired."""
