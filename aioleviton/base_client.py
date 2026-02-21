"""Base REST API client for the Leviton My Leviton cloud API.

Provides authentication, HTTP plumbing, and WebSocket creation.
Product-specific methods live in subclasses (e.g., LevitonClient).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import (
    API_BASE_URL,
    HTTP_STATUS_2FA_REQUIRED,
    HTTP_STATUS_INVALID_CODE,
    HTTP_STATUS_UNAUTHORIZED,
    LOGIN_ENDPOINT,
    LOGOUT_ENDPOINT,
    USER_AGENT,
)
from .exceptions import (
    LevitonAuthError,
    LevitonConnectionError,
    LevitonError,
    LevitonInvalidCode,
    LevitonTokenExpired,
    LevitonTwoFactorRequired,
)
from .models import AuthToken

if TYPE_CHECKING:
    from .websocket import LevitonWebSocket

_LOGGER = logging.getLogger(__name__)


class BaseLevitonClient:
    """Async base client for the Leviton My Leviton REST API.

    Handles authentication, session management, and HTTP requests.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client.

        Args:
            session: An aiohttp ClientSession for making HTTP requests.
                     Callers should manage the session lifecycle.
        """
        self._session = session
        self._token: str | None = None
        self._user_id: str | None = None
        self._auth_token: AuthToken | None = None

    @property
    def token(self) -> str | None:
        """Return the current authentication token."""
        return self._token

    @property
    def user_id(self) -> str | None:
        """Return the authenticated user ID."""
        return self._user_id

    @property
    def authenticated(self) -> bool:
        """Return True if the client has a valid token."""
        return self._token is not None

    async def login(
        self,
        email: str,
        password: str,
        code: str | None = None,
    ) -> AuthToken:
        """Authenticate with the Leviton API.

        Args:
            email: User's email address.
            password: User's password.
            code: Optional 2FA code.

        Returns:
            AuthToken with session details.

        Raises:
            LevitonTwoFactorRequired: If 2FA is required.
            LevitonInvalidCode: If the 2FA code is invalid.
            LevitonAuthError: If authentication fails.
            LevitonConnectionError: If the API is unreachable.
        """
        body: dict[str, str] = {"email": email, "password": password}
        if code is not None:
            body["code"] = code

        data = await self._request(
            "POST",
            LOGIN_ENDPOINT,
            json_data=body,
            params={"include": "user"},
            authenticated=False,
        )

        self._token = data["id"]
        self._user_id = data["userId"]
        self._auth_token = AuthToken(
            token=data["id"],
            ttl=data["ttl"],
            created=data["created"],
            user_id=data["userId"],
            user=data.get("user", {}),
        )
        return self._auth_token

    def restore_session(self, token: str, user_id: str) -> None:
        """Restore a previous session from a stored token.

        Args:
            token: A previously obtained auth token.
            user_id: The user ID associated with the token.
        """
        self._token = token
        self._user_id = user_id
        self._auth_token = AuthToken(
            token=token,
            ttl=0,
            created="",
            user_id=user_id,
            user={},
        )

    async def logout(self) -> None:
        """Invalidate the current token."""
        if self._token:
            try:
                await self._request(
                    "POST",
                    LOGOUT_ENDPOINT,
                    params={"access_token": self._token},
                    json_data={},
                    authenticated=False,
                    expect_json=False,
                )
            except LevitonError:
                pass
            finally:
                self._token = None
                self._user_id = None
                self._auth_token = None

    def create_websocket(self) -> LevitonWebSocket:
        """Create a WebSocket client using the current session and auth token.

        Returns:
            A LevitonWebSocket ready to connect.

        Raises:
            LevitonAuthError: If the client is not authenticated.
        """
        if self._auth_token is None:
            raise LevitonAuthError("Not authenticated. Call login() first.")
        from .websocket import LevitonWebSocket

        return LevitonWebSocket(
            session=self._session,
            token=self._auth_token.token,
            user_id=self._auth_token.user_id,
            user=self._auth_token.user,
            token_created=self._auth_token.created,
            token_ttl=self._auth_token.ttl,
        )

    def _ensure_authenticated(self) -> None:
        """Raise if not authenticated."""
        if not self._token:
            raise LevitonAuthError("Not authenticated. Call login() first.")

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        filter_header: dict[str, Any] | None = None,
        authenticated: bool = True,
        expect_json: bool = True,
    ) -> Any:  # noqa: ANN401
        """Make an HTTP request to the Leviton API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH).
            endpoint: API endpoint path (appended to base URL).
            json_data: JSON body data.
            params: Query parameters.
            filter_header: LoopBack filter to send in the filter header.
            authenticated: Whether to include the auth token.
            expect_json: Whether to parse the response as JSON.

        Returns:
            Parsed JSON response data, or None for non-JSON responses.

        Raises:
            LevitonTwoFactorRequired: On HTTP 406.
            LevitonInvalidCode: On HTTP 408.
            LevitonTokenExpired: On HTTP 401.
            LevitonAuthError: On other auth failures.
            LevitonConnectionError: On network errors.
        """
        url = f"{API_BASE_URL}{endpoint}"

        headers: dict[str, str] = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": USER_AGENT,
        }

        if authenticated and self._token:
            headers["authorization"] = self._token

        if filter_header is not None:
            headers["filter"] = json.dumps(filter_header)

        _LOGGER.debug("API %s %s", method, endpoint)

        try:
            async with self._session.request(
                method,
                url,
                json=json_data,
                params=params,
                headers=headers,
            ) as resp:
                _LOGGER.debug("API %s %s → %d", method, endpoint, resp.status)

                if resp.status == HTTP_STATUS_2FA_REQUIRED:
                    raise LevitonTwoFactorRequired(
                        "Two-factor authentication code required"
                    )

                if resp.status == HTTP_STATUS_INVALID_CODE:
                    raise LevitonInvalidCode("Invalid two-factor authentication code")

                if resp.status == HTTP_STATUS_UNAUTHORIZED:
                    # Parse the actual error message from the API
                    try:
                        error_data = await resp.json()
                        msg = error_data.get("error", {}).get(
                            "message", "Authorization Required"
                        )
                    except Exception:
                        msg = "Authorization Required"
                    # Distinguish login failure from token expiry:
                    # if we're making an authenticated request, it's a token issue;
                    # if unauthenticated (login), it's wrong credentials
                    if authenticated and self._token:
                        raise LevitonTokenExpired(msg)
                    raise LevitonAuthError(msg)

                if resp.status >= 500:
                    try:
                        error_data = await resp.json()
                        msg = error_data.get("error", {}).get(
                            "message", f"HTTP {resp.status}"
                        )
                    except Exception:
                        msg = f"HTTP {resp.status}"
                    _LOGGER.debug("API server error %s %s: %s", method, endpoint, msg)
                    raise LevitonConnectionError(f"Server error: {msg}")

                if resp.status >= 400:
                    try:
                        error_data = await resp.json()
                        msg = error_data.get("error", {}).get(
                            "message", f"HTTP {resp.status}"
                        )
                    except Exception:
                        msg = f"HTTP {resp.status}"
                    _LOGGER.debug("API client error %s %s: %s", method, endpoint, msg)
                    raise LevitonError(f"API error ({resp.status}): {msg}")

                if not expect_json or resp.status == 204:
                    return None

                return await resp.json()

        except LevitonError:
            raise
        except aiohttp.ClientError as err:
            _LOGGER.debug("API connection error %s %s: %s", method, endpoint, err)
            raise LevitonConnectionError(f"Connection error: {err}") from err
        except Exception as err:
            _LOGGER.debug("API unexpected error %s %s: %s", method, endpoint, err)
            raise LevitonConnectionError(f"Unexpected error: {err}") from err
