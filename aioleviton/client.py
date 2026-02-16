"""REST API client for the Leviton My Leviton cloud API."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import (
    ACCOUNT_RESIDENCES_ENDPOINT,
    API_BASE_URL,
    BREAKER_ENDPOINT,
    ENERGY_DAY_ENDPOINT,
    ENERGY_MONTH_ENDPOINT,
    ENERGY_WEEK_ENDPOINT,
    ENERGY_YEAR_ENDPOINT,
    FIRMWARE_CHECK_ENDPOINT,
    HTTP_STATUS_2FA_REQUIRED,
    HTTP_STATUS_INVALID_CODE,
    HTTP_STATUS_UNAUTHORIZED,
    LOGIN_ENDPOINT,
    LOGOUT_ENDPOINT,
    PANEL_BREAKERS_ENDPOINT,
    PANEL_ENDPOINT,
    PERMISSION_RESIDENCE_ENDPOINT,
    PERMISSIONS_ENDPOINT,
    RESIDENCE_PANELS_ENDPOINT,
    RESIDENCE_WHEMS_ENDPOINT,
    WHEM_BREAKERS_ENDPOINT,
    WHEM_CTS_ENDPOINT,
    WHEM_ENDPOINT,
)
from .exceptions import (
    LevitonAuthError,
    LevitonConnectionError,
    LevitonError,
    LevitonInvalidCode,
    LevitonTokenExpired,
    LevitonTwoFactorRequired,
)
from .models import AuthToken, Breaker, Ct, Panel, Permission, Residence, Whem

_LOGGER = logging.getLogger(__name__)


class LevitonClient:
    """Async client for the Leviton My Leviton REST API."""

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
            except LevitonConnectionError:
                pass
            finally:
                self._token = None
                self._user_id = None
                self._auth_token = None

    async def get_permissions(self) -> list[Permission]:
        """Get residential permissions for the authenticated user."""
        self._ensure_authenticated()
        assert self._user_id is not None
        data = await self._request(
            "GET",
            PERMISSIONS_ENDPOINT.format(person_id=self._user_id),
            filter_header={},
        )
        return [Permission.from_api(p) for p in data]

    async def get_residences(self, account_id: int) -> list[Residence]:
        """Get all residences for an account."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            ACCOUNT_RESIDENCES_ENDPOINT.format(account_id=account_id),
            filter_header={},
        )
        return [Residence.from_api(r) for r in data]

    async def get_whems(self, residence_id: int) -> list[Whem]:
        """Get all LWHEM hubs in a residence."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            RESIDENCE_WHEMS_ENDPOINT.format(residence_id=residence_id),
            filter_header={},
        )
        return [Whem.from_api(w) for w in data]

    async def get_panels(self, residence_id: int) -> list[Panel]:
        """Get all DAU/LDATA panels in a residence."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            RESIDENCE_PANELS_ENDPOINT.format(residence_id=residence_id),
            filter_header={"include": ["residentialBreakers"]},
        )
        return [Panel.from_api(p) for p in data]

    async def get_whem(self, whem_id: str) -> Whem:
        """Get a single LWHEM hub by ID."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            WHEM_ENDPOINT.format(whem_id=whem_id),
            filter_header={},
        )
        return Whem.from_api(data)

    async def get_panel(self, panel_id: str) -> Panel:
        """Get a single DAU panel by ID."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            PANEL_ENDPOINT.format(panel_id=panel_id),
            filter_header={},
        )
        return Panel.from_api(data)

    async def get_whem_breakers(self, whem_id: str) -> list[Breaker]:
        """Get all breakers managed by a LWHEM hub."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            WHEM_BREAKERS_ENDPOINT.format(whem_id=whem_id),
            filter_header={},
        )
        return [Breaker.from_api(b) for b in data]

    async def get_panel_breakers(self, panel_id: str) -> list[Breaker]:
        """Get all breakers in a DAU panel."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            PANEL_BREAKERS_ENDPOINT.format(panel_id=panel_id),
            filter_header={},
        )
        return [Breaker.from_api(b) for b in data]

    async def get_cts(self, whem_id: str) -> list[Ct]:
        """Get all current transformers for a LWHEM hub."""
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            WHEM_CTS_ENDPOINT.format(whem_id=whem_id),
            filter_header={},
        )
        return [Ct.from_api(c) for c in data]

    async def get_residence_from_permission(self, permission_id: int) -> Residence:
        """Get a residence via a residence-level permission.

        Used when the permission has a residenceId but no residentialAccountId.

        Args:
            permission_id: The residential permission ID.

        Returns:
            The Residence associated with this permission.
        """
        self._ensure_authenticated()
        data = await self._request(
            "GET",
            PERMISSION_RESIDENCE_ENDPOINT.format(permission_id=permission_id),
            params={"refresh": "true"},
        )
        return Residence.from_api(data)

    # ---- Firmware ----

    async def check_firmware(
        self,
        app_id: str,
        model: str,
        serial: str,
        model_type: str,
    ) -> list[dict[str, Any]]:
        """Check for available firmware updates for a device.

        Args:
            app_id: Application ID (e.g., "LWHEM").
            model: Device model code (e.g., "AZ").
            serial: Device serial number (e.g., "1000_XXXX_XXXX").
            model_type: LoopBack model name (e.g., "IotWhem").

        Returns:
            List of available firmware objects. Each contains:
            version, fileUrl, signature, hash, size, notes, release, etc.
            Empty list if no updates available.
        """
        self._ensure_authenticated()
        result: list[dict[str, Any]] = await self._request(
            "GET",
            FIRMWARE_CHECK_ENDPOINT,
            params={
                "appId": app_id,
                "model": model,
                "serial": serial,
                "modelType": model_type,
                "data": '{"condensed":false}',
            },
        )
        return result

    # ---- Energy History (traffic-verified 2026-02-16) ----
    #
    # The app calls /api/Residences/getAllEnergyConsumption* on my.leviton.com.
    # The server 307-redirects to AWS API Gateway (Lambda) which returns the
    # actual data. aiohttp follows redirects automatically.
    #
    # Response is keyed by hub ID, then by breaker position / CT channel:
    # {
    #   "<whem_id>": {
    #     "residentialBreakers": {"<position>": [...]},
    #     "iotCts": {"<channel>": [...]},
    #     "totals": [...]
    #   },
    #   "totals": [...]
    # }

    async def get_energy_for_day(
        self,
        residence_id: int,
        start_day: str,
        timezone: str,
    ) -> dict[str, Any]:
        """Get daily energy consumption for all devices in a residence.

        Args:
            residence_id: The residence ID.
            start_day: Date string (YYYY-MM-DD, e.g., "2026-02-16").
            timezone: IANA timezone (e.g., "America/Los_Angeles").

        Returns:
            Energy data keyed by hub ID with per-breaker/CT breakdowns.
            Each data point: {x, timestamp, energyConsumption, energyImport,
            total, totalCost}.
        """
        self._ensure_authenticated()
        result: dict[str, Any] = await self._request(
            "GET",
            ENERGY_DAY_ENDPOINT,
            params={
                "id": str(residence_id),
                "startDay": start_day,
                "timezone": timezone,
            },
        )
        return result

    async def get_energy_for_week(
        self,
        residence_id: int,
        start_day: str,
        timezone: str,
    ) -> dict[str, Any]:
        """Get weekly energy consumption for all devices in a residence.

        Args:
            residence_id: The residence ID.
            start_day: Week start date (YYYY-MM-DD, e.g., "2026-02-17").
            timezone: IANA timezone (e.g., "America/Los_Angeles").

        Returns:
            Energy data with 7 data points per device (one per day).
        """
        self._ensure_authenticated()
        result: dict[str, Any] = await self._request(
            "GET",
            ENERGY_WEEK_ENDPOINT,
            params={
                "id": str(residence_id),
                "startDay": start_day,
                "timezone": timezone,
            },
        )
        return result

    async def get_energy_for_month(
        self,
        residence_id: int,
        billing_day_in_month: str,
        timezone: str,
    ) -> dict[str, Any]:
        """Get monthly energy consumption for all devices in a residence.

        Args:
            residence_id: The residence ID.
            billing_day_in_month: End-of-billing-cycle date (YYYY-MM-DD).
            timezone: IANA timezone (e.g., "America/Los_Angeles").

        Returns:
            Energy data with daily data points for the billing month.
        """
        self._ensure_authenticated()
        result: dict[str, Any] = await self._request(
            "GET",
            ENERGY_MONTH_ENDPOINT,
            params={
                "id": str(residence_id),
                "billingDayInMonth": billing_day_in_month,
                "timezone": timezone,
            },
        )
        return result

    async def get_energy_for_year(
        self,
        residence_id: int,
        billing_day_in_end_month: str,
        timezone: str,
    ) -> dict[str, Any]:
        """Get yearly energy consumption for all devices in a residence.

        Args:
            residence_id: The residence ID.
            billing_day_in_end_month: Reference date (YYYY-MM-DD) for the
                year period. Use current date for YTD or Dec 31 for full year.
            timezone: IANA timezone (e.g., "America/Los_Angeles").

        Returns:
            Energy data with 12 data points per device (one per month).
        """
        self._ensure_authenticated()
        result: dict[str, Any] = await self._request(
            "GET",
            ENERGY_YEAR_ENDPOINT,
            params={
                "id": str(residence_id),
                "billingDayInEndMonth": billing_day_in_end_month,
                "timezone": timezone,
            },
        )
        return result

    async def trip_breaker(self, breaker_id: str) -> None:
        """Remotely trip a breaker (all smart breakers)."""
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"remoteTrip": True},
        )

    async def turn_on_breaker(self, breaker_id: str) -> None:
        """Remotely turn on a Gen 2 breaker."""
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"remoteOn": True},
        )

    async def turn_off_breaker(self, breaker_id: str) -> None:
        """Remotely turn off a Gen 2 breaker (via trip)."""
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"remoteTrip": True},
        )

    async def blink_led(self, breaker_id: str) -> None:
        """Blink the LED on a smart breaker."""
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"blinkLED": True},
        )

    async def identify_whem(self, whem_id: str) -> None:
        """Trigger identify LED on a LWHEM hub."""
        self._ensure_authenticated()
        await self._request(
            "PUT",
            WHEM_ENDPOINT.format(whem_id=whem_id),
            json_data={"identify": 10},
        )

    async def set_panel_bandwidth(self, panel_id: str, enabled: bool) -> None:
        """Enable or disable real-time push data on a DAU panel.

        Args:
            panel_id: The panel ID.
            enabled: True to enable bandwidth (real-time), False to disable.
        """
        self._ensure_authenticated()
        await self._request(
            "PUT",
            PANEL_ENDPOINT.format(panel_id=panel_id),
            json_data={"bandwidth": 1 if enabled else 0},
        )

    async def set_whem_bandwidth(self, whem_id: str, bandwidth: int) -> None:
        """Set the reporting bandwidth on a LWHEM hub.

        Args:
            whem_id: The WHEM ID.
            bandwidth: 0 (slow/off), 1 (fast), 2 (medium/default).
        """
        self._ensure_authenticated()
        await self._request(
            "PUT",
            WHEM_ENDPOINT.format(whem_id=whem_id),
            json_data={"bandwidth": bandwidth},
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
        }

        if authenticated and self._token:
            headers["authorization"] = self._token

        if filter_header is not None:
            headers["filter"] = json.dumps(filter_header)

        try:
            async with self._session.request(
                method,
                url,
                json=json_data,
                params=params,
                headers=headers,
            ) as resp:
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
                    raise LevitonConnectionError(f"Server error: {msg}")

                if resp.status >= 400:
                    try:
                        error_data = await resp.json()
                        msg = error_data.get("error", {}).get(
                            "message", f"HTTP {resp.status}"
                        )
                    except Exception:
                        msg = f"HTTP {resp.status}"
                    raise LevitonError(f"API error ({resp.status}): {msg}")

                if not expect_json or resp.status == 204:
                    return None

                return await resp.json()

        except (
            LevitonTwoFactorRequired,
            LevitonInvalidCode,
            LevitonTokenExpired,
            LevitonAuthError,
            LevitonError,
        ):
            raise
        except aiohttp.ClientError as err:
            raise LevitonConnectionError(f"Connection error: {err}") from err
        except Exception as err:
            raise LevitonConnectionError(f"Unexpected error: {err}") from err
