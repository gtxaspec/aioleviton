"""Tests for aioleviton exception hierarchy."""

from aioleviton import (
    LevitonAuthError,
    LevitonConnectionError,
    LevitonError,
    LevitonInvalidCode,
    LevitonTokenExpired,
    LevitonTwoFactorRequired,
)


def test_exception_hierarchy():
    """Verify inheritance design decisions that consumers depend on.

    - LevitonTokenExpired IS-A LevitonAuthError (so ``except LevitonAuthError``
      catches both bad-creds and expired-token).
    - 2FA, invalid-code, and connection errors are NOT LevitonAuthError
      (they require distinct handling paths).
    - Everything is catchable via ``except LevitonError``.
    """
    # TokenExpired must be caught by "except LevitonAuthError"
    assert issubclass(LevitonTokenExpired, LevitonAuthError)

    # These must NOT be caught by "except LevitonAuthError"
    for cls in (LevitonTwoFactorRequired, LevitonInvalidCode, LevitonConnectionError):
        assert not issubclass(cls, LevitonAuthError), (
            f"{cls.__name__} should not inherit LevitonAuthError"
        )

    # Everything inherits from LevitonError
    for cls in (
        LevitonAuthError,
        LevitonTokenExpired,
        LevitonTwoFactorRequired,
        LevitonInvalidCode,
        LevitonConnectionError,
    ):
        assert issubclass(cls, LevitonError), (
            f"{cls.__name__} should inherit LevitonError"
        )
