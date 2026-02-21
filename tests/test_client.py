"""Tests for aioleviton REST client."""

import re
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from aioleviton import (
    LevitonAuthError,
    LevitonClient,
    LevitonConnectionError,
    LevitonError,
    LevitonInvalidCode,
    LevitonTokenExpired,
    LevitonTwoFactorRequired,
)
from aioleviton.const import API_BASE_URL
from aioleviton.websocket import LevitonWebSocket

from .conftest import (
    BREAKER_RESPONSE,
    CT_RESPONSE,
    LOGIN_RESPONSE,
    PANEL_RESPONSE,
    PERMISSION_RESPONSE,
    RESIDENCE_RESPONSE,
    WHEM_RESPONSE,
)

BASE = API_BASE_URL

# Regex patterns for endpoints that pass query params (aioresponses needs
# exact URL match including query string; regex avoids fragile param ordering).
LOGIN_URL = re.compile(re.escape(f"{BASE}/Person/login"))
LOGOUT_URL = re.compile(re.escape(f"{BASE}/Person/logout"))
PERM_RESIDENCE_URL = re.compile(
    re.escape(f"{BASE}/ResidentialPermissions/") + r"\d+/residence"
)
FIRMWARE_URL = re.compile(re.escape(f"{BASE}/LcsApps/getFirmware"))
ENERGY_DAY_URL = re.compile(
    re.escape(f"{BASE}/Residences/getAllEnergyConsumptionForDay")
)
ENERGY_WEEK_URL = re.compile(
    re.escape(f"{BASE}/Residences/getAllEnergyConsumptionForWeek")
)
ENERGY_MONTH_URL = re.compile(
    re.escape(f"{BASE}/Residences/getAllEnergyConsumptionForMonth")
)
ENERGY_YEAR_URL = re.compile(
    re.escape(f"{BASE}/Residences/getAllEnergyConsumptionForYear")
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    async def test_login_success(self, client, mock_api):
        mock_api.post(LOGIN_URL, payload=LOGIN_RESPONSE)
        token = await client.login("test@example.com", "password")
        assert token.token == "tok_abc123"
        assert token.user_id == "user_001"
        assert client.authenticated is True
        assert client.token == "tok_abc123"
        assert client.user_id == "user_001"

    async def test_login_2fa_required(self, client, mock_api):
        mock_api.post(LOGIN_URL, status=406)
        with pytest.raises(LevitonTwoFactorRequired):
            await client.login("test@example.com", "password")

    async def test_login_invalid_code(self, client, mock_api):
        mock_api.post(LOGIN_URL, status=408)
        with pytest.raises(LevitonInvalidCode):
            await client.login("test@example.com", "password", code="000000")

    async def test_login_bad_credentials(self, client, mock_api):
        mock_api.post(
            LOGIN_URL,
            status=401,
            payload={"error": {"message": "login failed"}},
        )
        with pytest.raises(LevitonAuthError):
            await client.login("bad@example.com", "wrong")

    async def test_login_connection_error(self, client, mock_api):
        mock_api.post(LOGIN_URL, exception=aiohttp.ClientConnectionError())
        with pytest.raises(LevitonConnectionError):
            await client.login("test@example.com", "password")

    async def test_restore_session(self, client):
        assert client.authenticated is False
        client.restore_session("tok_restored", "user_002")
        assert client.authenticated is True
        assert client.token == "tok_restored"
        assert client.user_id == "user_002"

    async def test_logout(self, authenticated_client, mock_api):
        mock_api.post(LOGOUT_URL, payload={})
        await authenticated_client.logout()
        assert authenticated_client.authenticated is False
        assert authenticated_client.token is None
        assert authenticated_client.user_id is None

    async def test_logout_ignores_connection_error(
        self, authenticated_client, mock_api
    ):
        mock_api.post(
            LOGOUT_URL,
            exception=aiohttp.ClientConnectionError(),
        )
        await authenticated_client.logout()
        assert authenticated_client.authenticated is False

    async def test_logout_ignores_auth_error(self, authenticated_client, mock_api):
        """401 during logout (token already expired) should not propagate."""
        mock_api.post(
            LOGOUT_URL,
            status=401,
            payload={"error": {"message": "Token expired"}},
        )
        await authenticated_client.logout()
        assert authenticated_client.authenticated is False


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestAuthEnforcement:
    async def test_unauthenticated_raises(self, client):
        with pytest.raises(LevitonAuthError, match="Not authenticated"):
            await client.get_permissions()

    async def test_token_expired_on_authenticated_request(
        self, authenticated_client, mock_api
    ):
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            status=401,
            payload={"error": {"message": "Token expired"}},
        )
        with pytest.raises(LevitonTokenExpired):
            await authenticated_client.get_permissions()


# ---------------------------------------------------------------------------
# GET methods
# ---------------------------------------------------------------------------


class TestGetMethods:
    """All GET methods are thin wrappers: call endpoint, return model(s)."""

    @pytest.mark.parametrize(
        ("method_name", "method_args", "mock_url", "payload", "is_list", "attr", "val"),
        [
            (
                "get_permissions",
                [],
                f"{BASE}/Person/user_001/residentialPermissions",
                [PERMISSION_RESPONSE],
                True,
                "id",
                1,
            ),
            (
                "get_residences",
                [200],
                f"{BASE}/ResidentialAccounts/200/residences",
                [RESIDENCE_RESPONSE],
                True,
                "name",
                "Test Home",
            ),
            (
                "get_whems",
                [100],
                f"{BASE}/Residences/100/iotWhems",
                [WHEM_RESPONSE],
                True,
                "id",
                "whem_001",
            ),
            (
                "get_whem",
                ["whem_001"],
                f"{BASE}/IotWhems/whem_001",
                WHEM_RESPONSE,
                False,
                "id",
                "whem_001",
            ),
            (
                "get_panels",
                [100],
                f"{BASE}/Residences/100/residentialBreakerPanels",
                [PANEL_RESPONSE],
                True,
                "id",
                "panel_001",
            ),
            (
                "get_panel",
                ["panel_001"],
                f"{BASE}/ResidentialBreakerPanels/panel_001",
                PANEL_RESPONSE,
                False,
                "id",
                "panel_001",
            ),
            (
                "get_whem_breakers",
                ["whem_001"],
                f"{BASE}/IotWhems/whem_001/residentialBreakers",
                [BREAKER_RESPONSE],
                True,
                "id",
                "brk_001",
            ),
            (
                "get_panel_breakers",
                ["panel_001"],
                f"{BASE}/ResidentialBreakerPanels/panel_001/residentialBreakers",
                [BREAKER_RESPONSE],
                True,
                "id",
                "brk_001",
            ),
            (
                "get_cts",
                ["whem_001"],
                f"{BASE}/IotWhems/whem_001/iotCts",
                [CT_RESPONSE],
                True,
                "name",
                "Solar",
            ),
            (
                "get_residence_from_permission",
                [1],
                PERM_RESIDENCE_URL,
                RESIDENCE_RESPONSE,
                False,
                "id",
                100,
            ),
        ],
        ids=[
            "permissions",
            "residences",
            "whems",
            "whem",
            "panels",
            "panel",
            "whem_breakers",
            "panel_breakers",
            "cts",
            "residence_from_permission",
        ],
    )
    async def test_get_method(
        self,
        authenticated_client,
        mock_api,
        method_name,
        method_args,
        mock_url,
        payload,
        is_list,
        attr,
        val,
    ):
        mock_api.get(mock_url, payload=payload)
        result = await getattr(authenticated_client, method_name)(*method_args)
        if is_list:
            assert len(result) == 1
            assert getattr(result[0], attr) == val
        else:
            assert getattr(result, attr) == val


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


class TestCommands:
    """Verify each command sends the correct HTTP method, endpoint, and body.

    Mocks ``_request`` directly — the HTTP plumbing is already tested in
    TestAuth / TestErrorHandling. What matters here is the payload.
    """

    @pytest.mark.parametrize(
        ("method_name", "method_args", "http_method", "endpoint", "json_body"),
        [
            (
                "trip_breaker",
                ["brk_001"],
                "PATCH",
                "/ResidentialBreakers/brk_001",
                {"remoteTrip": True},
            ),
            (
                "turn_on_breaker",
                ["brk_002"],
                "PATCH",
                "/ResidentialBreakers/brk_002",
                {"remoteOn": True},
            ),
            (
                "turn_off_breaker",
                ["brk_002"],
                "PATCH",
                "/ResidentialBreakers/brk_002",
                {"remoteTrip": True},
            ),
            (
                "blink_led",
                ["brk_001"],
                "PATCH",
                "/ResidentialBreakers/brk_001",
                {"blinkLED": True},
            ),
            (
                "stop_blink_led",
                ["brk_001"],
                "PATCH",
                "/ResidentialBreakers/brk_001",
                {"blinkLED": False},
            ),
            (
                "identify_whem",
                ["whem_001"],
                "PUT",
                "/IotWhems/whem_001",
                {"identify": 10},
            ),
            (
                "set_whem_bandwidth",
                ["whem_001", 1],
                "PUT",
                "/IotWhems/whem_001",
                {"bandwidth": 1},
            ),
            (
                "set_panel_bandwidth",
                ["panel_001", True],
                "PUT",
                "/ResidentialBreakerPanels/panel_001",
                {"bandwidth": 1},
            ),
            (
                "set_panel_bandwidth",
                ["panel_001", False],
                "PUT",
                "/ResidentialBreakerPanels/panel_001",
                {"bandwidth": 0},
            ),
            (
                "trigger_whem_ota",
                ["whem_001"],
                "PUT",
                "/IotWhems/whem_001",
                {"apply_ota": 2},
            ),
        ],
        ids=[
            "trip_breaker",
            "turn_on",
            "turn_off",
            "blink_led",
            "stop_blink_led",
            "identify_whem",
            "set_whem_bandwidth",
            "set_panel_bandwidth_on",
            "set_panel_bandwidth_off",
            "trigger_ota",
        ],
    )
    async def test_command_body(
        self,
        authenticated_client,
        method_name,
        method_args,
        http_method,
        endpoint,
        json_body,
    ):
        with patch.object(
            authenticated_client, "_request", new_callable=AsyncMock
        ) as mock_req:
            await getattr(authenticated_client, method_name)(*method_args)
            mock_req.assert_awaited_once_with(
                http_method, endpoint, json_data=json_body
            )


# ---------------------------------------------------------------------------
# Firmware
# ---------------------------------------------------------------------------


class TestFirmware:
    async def test_check_firmware(self, authenticated_client, mock_api):
        fw_data = [{"version": "2.1.0", "fileUrl": "https://example.com/fw.bin"}]
        mock_api.get(FIRMWARE_URL, payload=fw_data)
        result = await authenticated_client.check_firmware(
            "LWHEM", "AZ", "1000_AAAA_BBBB", "IotWhem"
        )
        assert len(result) == 1
        assert result[0]["version"] == "2.1.0"

    async def test_check_firmware_empty(self, authenticated_client, mock_api):
        mock_api.get(FIRMWARE_URL, payload=[])
        result = await authenticated_client.check_firmware(
            "LWHEM", "AZ", "1000_AAAA_BBBB", "IotWhem"
        )
        assert result == []


# ---------------------------------------------------------------------------
# Energy history
# ---------------------------------------------------------------------------


class TestEnergyHistory:
    ENERGY_DATA = {"whem_001": {"totals": [{"energyConsumption": 100}]}}

    async def test_get_energy_for_day(self, authenticated_client, mock_api):
        mock_api.get(ENERGY_DAY_URL, payload=self.ENERGY_DATA)
        result = await authenticated_client.get_energy_for_day(
            100, "2026-02-20", "America/New_York"
        )
        assert "whem_001" in result

    async def test_get_energy_for_week(self, authenticated_client, mock_api):
        mock_api.get(ENERGY_WEEK_URL, payload=self.ENERGY_DATA)
        result = await authenticated_client.get_energy_for_week(
            100, "2026-02-17", "America/New_York"
        )
        assert "whem_001" in result

    async def test_get_energy_for_month(self, authenticated_client, mock_api):
        mock_api.get(ENERGY_MONTH_URL, payload=self.ENERGY_DATA)
        result = await authenticated_client.get_energy_for_month(
            100, "2026-02-28", "America/New_York"
        )
        assert "whem_001" in result

    async def test_get_energy_for_year(self, authenticated_client, mock_api):
        mock_api.get(ENERGY_YEAR_URL, payload=self.ENERGY_DATA)
        result = await authenticated_client.get_energy_for_year(
            100, "2026-12-31", "America/New_York"
        )
        assert "whem_001" in result


# ---------------------------------------------------------------------------
# WebSocket factory
# ---------------------------------------------------------------------------


class TestWebSocketFactory:
    async def test_create_websocket(self, aiohttp_session, mock_api):
        client = LevitonClient(aiohttp_session)
        mock_api.post(LOGIN_URL, payload=LOGIN_RESPONSE)
        await client.login("test@example.com", "password")
        ws = client.create_websocket()
        assert isinstance(ws, LevitonWebSocket)

    async def test_create_websocket_unauthenticated(self, client):
        with pytest.raises(LevitonAuthError, match="Not authenticated"):
            client.create_websocket()


# ---------------------------------------------------------------------------
# Error handling edge cases
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_server_error(self, authenticated_client, mock_api):
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            status=500,
            payload={"error": {"message": "Internal Server Error"}},
        )
        with pytest.raises(LevitonConnectionError, match="Server error"):
            await authenticated_client.get_permissions()

    async def test_client_error_4xx(self, authenticated_client, mock_api):
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            status=404,
            payload={"error": {"message": "Not Found"}},
        )
        with pytest.raises(LevitonError, match="API error"):
            await authenticated_client.get_permissions()

    async def test_server_error_no_json(self, authenticated_client, mock_api):
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            status=500,
            body="Internal Server Error",
            content_type="text/plain",
        )
        with pytest.raises(LevitonConnectionError):
            await authenticated_client.get_permissions()

    async def test_401_no_json_login(self, client, mock_api):
        """401 with non-JSON body during login falls back to default message."""
        mock_api.post(
            LOGIN_URL,
            status=401,
            body="Unauthorized",
            content_type="text/plain",
        )
        with pytest.raises(LevitonAuthError, match="Authorization Required"):
            await client.login("test@example.com", "password")

    async def test_401_no_json_authenticated(self, authenticated_client, mock_api):
        """401 with non-JSON body on authenticated request → TokenExpired."""
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            status=401,
            body="Unauthorized",
            content_type="text/plain",
        )
        with pytest.raises(LevitonTokenExpired, match="Authorization Required"):
            await authenticated_client.get_permissions()

    async def test_4xx_no_json(self, authenticated_client, mock_api):
        """4xx with non-JSON body falls back to HTTP status code message."""
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            status=403,
            body="Forbidden",
            content_type="text/plain",
        )
        with pytest.raises(LevitonError, match="HTTP 403"):
            await authenticated_client.get_permissions()

    async def test_unexpected_exception(self, authenticated_client, mock_api):
        """Non-aiohttp exception during request → LevitonConnectionError."""
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            exception=RuntimeError("something very unexpected"),
        )
        with pytest.raises(LevitonConnectionError, match="Unexpected error"):
            await authenticated_client.get_permissions()


# ---------------------------------------------------------------------------
# Integration: full discovery flow
# ---------------------------------------------------------------------------


class TestIntegrationFlow:
    async def test_login_discover_devices(self, aiohttp_session, mock_api):
        """Full flow: login → permissions → residences → whems → breakers → CTs."""
        client = LevitonClient(aiohttp_session)

        # 1. Login
        mock_api.post(LOGIN_URL, payload=LOGIN_RESPONSE)
        await client.login("test@example.com", "password")
        assert client.authenticated

        # 2. Get permissions
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            payload=[PERMISSION_RESPONSE],
        )
        perms = await client.get_permissions()
        assert len(perms) == 1
        perm = perms[0]

        # 3. Get residences via account
        mock_api.get(
            f"{BASE}/ResidentialAccounts/{perm.residential_account_id}/residences",
            payload=[RESIDENCE_RESPONSE],
        )
        residences = await client.get_residences(perm.residential_account_id)
        assert len(residences) == 1
        residence = residences[0]

        # 4. Get WHEMs
        mock_api.get(
            f"{BASE}/Residences/{residence.id}/iotWhems",
            payload=[WHEM_RESPONSE],
        )
        whems = await client.get_whems(residence.id)
        assert len(whems) == 1
        whem = whems[0]

        # 5. Get breakers
        mock_api.get(
            f"{BASE}/IotWhems/{whem.id}/residentialBreakers",
            payload=[BREAKER_RESPONSE],
        )
        breakers = await client.get_whem_breakers(whem.id)
        assert len(breakers) == 1
        assert breakers[0].iot_whem_id == whem.id

        # 6. Get CTs
        mock_api.get(
            f"{BASE}/IotWhems/{whem.id}/iotCts",
            payload=[CT_RESPONSE],
        )
        cts = await client.get_cts(whem.id)
        assert len(cts) == 1
        assert cts[0].iot_whem_id == whem.id

        # 7. Create WebSocket
        ws = client.create_websocket()
        assert isinstance(ws, LevitonWebSocket)

        # 8. Logout
        mock_api.post(LOGOUT_URL, payload={})
        await client.logout()
        assert not client.authenticated

    async def test_residence_permission_flow(self, aiohttp_session, mock_api):
        """Flow for residence-level permission (no account ID)."""
        client = LevitonClient(aiohttp_session)
        mock_api.post(LOGIN_URL, payload=LOGIN_RESPONSE)
        await client.login("test@example.com", "password")

        # Permission with residenceId but no residentialAccountId
        perm_data = {
            "id": 5,
            "access": "admin",
            "status": "accepted",
            "personId": "user_001",
            "residenceId": 100,
        }
        mock_api.get(
            f"{BASE}/Person/user_001/residentialPermissions",
            payload=[perm_data],
        )
        perms = await client.get_permissions()
        perm = perms[0]
        assert perm.residential_account_id is None
        assert perm.residence_id == 100

        # Get residence directly via permission
        mock_api.get(PERM_RESIDENCE_URL, payload=RESIDENCE_RESPONSE)
        res = await client.get_residence_from_permission(perm.id)
        assert res.id == 100
