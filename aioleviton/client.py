"""Load Center REST API client for the Leviton My Leviton cloud API."""

from __future__ import annotations

import logging
from typing import Any

from .base_client import BaseLevitonClient
from .const import (
    ACCOUNT_RESIDENCES_ENDPOINT,
    BREAKER_ENDPOINT,
    ENERGY_DAY_ENDPOINT,
    ENERGY_MONTH_ENDPOINT,
    ENERGY_WEEK_ENDPOINT,
    ENERGY_YEAR_ENDPOINT,
    FIRMWARE_CHECK_ENDPOINT,
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
from .models import Breaker, Ct, Panel, Permission, Residence, Whem

_LOGGER = logging.getLogger(__name__)


class LevitonClient(BaseLevitonClient):
    """Async client for Leviton Load Center devices (LWHEM, DAU/LDATA)."""

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
        _LOGGER.debug("Tripping breaker %s", breaker_id)
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"remoteTrip": True},
        )

    async def turn_on_breaker(self, breaker_id: str) -> None:
        """Remotely turn on a Gen 2 breaker."""
        _LOGGER.debug("Turning on breaker %s", breaker_id)
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"remoteOn": True},
        )

    async def turn_off_breaker(self, breaker_id: str) -> None:
        """Remotely turn off a Gen 2 breaker (trip)."""
        _LOGGER.debug("Turning off breaker %s", breaker_id)
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

    async def stop_blink_led(self, breaker_id: str) -> None:
        """Stop blinking the LED on a smart breaker."""
        self._ensure_authenticated()
        await self._request(
            "PATCH",
            BREAKER_ENDPOINT.format(breaker_id=breaker_id),
            json_data={"blinkLED": False},
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
        _LOGGER.debug("Setting panel %s bandwidth to %s", panel_id, enabled)
        self._ensure_authenticated()
        await self._request(
            "PUT",
            PANEL_ENDPOINT.format(panel_id=panel_id),
            json_data={"bandwidth": 1 if enabled else 0},
        )

    async def trigger_whem_ota(self, whem_id: str) -> None:
        """Trigger OTA firmware update on a LWHEM hub.

        The device will download and install the latest available firmware.

        Args:
            whem_id: The WHEM ID.
        """
        self._ensure_authenticated()
        await self._request(
            "PUT",
            WHEM_ENDPOINT.format(whem_id=whem_id),
            json_data={"apply_ota": 2},
        )

    async def set_whem_bandwidth(self, whem_id: str, bandwidth: int) -> None:
        """Set the reporting bandwidth on a LWHEM hub.

        Args:
            whem_id: The WHEM ID.
            bandwidth: 0 (slow/off), 1 (fast), 2 (medium/default).
        """
        _LOGGER.debug("Setting WHEM %s bandwidth to %d", whem_id, bandwidth)
        self._ensure_authenticated()
        await self._request(
            "PUT",
            WHEM_ENDPOINT.format(whem_id=whem_id),
            json_data={"bandwidth": bandwidth},
        )
