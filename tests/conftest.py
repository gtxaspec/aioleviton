"""Shared fixtures for aioleviton tests."""

import aiohttp
import pytest
from aioresponses import aioresponses

from aioleviton import LevitonClient

# ---------------------------------------------------------------------------
# Raw API response dicts (camelCase, matching real API)
#
# These include extra fields the real API returns that models don't parse
# directly — they end up in the `raw` dict and verify we handle unexpected
# keys gracefully.
# ---------------------------------------------------------------------------

LOGIN_RESPONSE = {
    "id": "tok_abc123",
    "ttl": 5184000,
    "created": "2026-01-01T00:00:00.000Z",
    "userId": "user_001",
    "user": {"email": "test@example.com", "firstName": "Test"},
}

PERMISSION_RESPONSE = {
    "id": 1,
    "access": "admin",
    "status": "accepted",
    "personId": "user_001",
    "residenceId": 100,
    "residentialAccountId": 200,
}

RESIDENCE_RESPONSE = {
    "id": 100,
    "name": "Test Home",
    "status": "active",
    "timezone": {"id": "America/New_York"},
    "residentialAccountId": 200,
    "energyCost": 0.12,
}

WHEM_RESPONSE = {
    "id": "whem_001",
    "name": "Main Panel LWHEM",
    "model": "LWHEM",
    "serial": "1000_AAAA_BBBB",
    "manufacturer": "Leviton Manufacturing Co., Inc.",
    "version": "2.0.13",
    "versionBLE": "1.2.3",
    "connected": True,
    "localIP": "192.168.1.10",
    "mac": "AA:BB:CC:DD:EE:FF",
    "rssi": -55,
    "residenceId": 100,
    "rmsVoltageA": 121,
    "rmsVoltageB": 122,
    "frequencyA": 60,
    "frequencyB": 60,
    "panelSize": 42,
    "breakerCount": 42,
    "bandwidth": 0,
    "identify": 0,
    # Extra fields from real API (FW 2.0.13) — should go into raw
    "thresholdCount": 0,
    "underVoltageCount": 0,
    "energyDelaySeconds": 5,
    "uploadFrequency": 60,
    "measureResolution": 1,
    "enableInstantPower": True,
    "enableInstantCurrent": True,
}

PANEL_RESPONSE = {
    "id": "panel_001",
    "name": "Sub Panel DAU",
    "model": "DAU",
    "manufacturer": "Leviton",
    "breakerCount": 20,
    "panelSize": 20,
    "status": "active",
    "commissioned": True,
    "residenceId": 100,
    "bandwidth": 0,
    "rmsVoltage": 120,
    "rmsVoltage2": 121,
    "wifiMode": "station",
    "wifiRSSI": -60,
    "wifiSSID": "TestNetwork",
    "versionBCM": "1.0.0",
    "versionBCMRadio": "1.0.1",
    "versionBSM": "2.0.0",
    "versionBSMRadio": "2.0.1",
    "versionNCM": "3.0.0",
    "packageVer": "4.0.0",
    "online": "2026-01-01T12:00:00.000Z",
    "offline": "2026-01-01T06:00:00.000Z",
    # Extra fields from real API — should go into raw
    "channel1Status": True,
    "channel2Status": True,
    "whemReplaced": False,
}

BREAKER_RESPONSE = {
    "id": "brk_001",
    "name": "Kitchen",
    "model": "L5120",
    "branchType": "branch",
    "position": 1,
    "poles": 1,
    "currentRating": 20,
    "currentState": "ON",
    "currentState2": None,
    "operationalState": "normal",
    "power": 500,
    "power2": None,
    "rmsCurrent": 4200,
    "rmsCurrent2": None,
    "rmsVoltage": 121,
    "rmsVoltage2": None,
    "energyConsumption": 12345.6,
    "energyConsumption2": None,
    "energyImport": 100.5,
    "lineFrequency": 60.0,
    "lineFrequency2": None,
    "bleRSSI": -45,
    "connected": True,
    "remoteTrip": False,
    "remoteState": None,
    "remoteOn": False,
    "canRemoteOn": False,
    "firmwareVersionBLE": "1.0.0",
    "firmwareVersionMeter": "2.0.0",
    "firmwareVersionSiLabs": "3.0.0",
    "firmwareVersionGFCI": None,
    "firmwareVersionAFCI": None,
    "hwVersion": "A1",
    "serialNumber": "SN12345",
    "locked": False,
    "blinkLED": False,
    "lsbmaId": None,
    "lsbmaId2": None,
    "lsbmaParentId": None,
    "iotWhemId": "whem_001",
    "residentialBreakerPanelId": None,
    # Extra fields from real API — should go into raw
    "powerThreshLow": 0,
    "powerThreshHigh": 10000,
    "estimatedWattage": 480,
}

BREAKER_GEN2_RESPONSE = {
    **BREAKER_RESPONSE,
    "id": "brk_002",
    "name": "Office",
    "canRemoteOn": True,
    "remoteOn": True,
    "remoteState": "RemoteON",
}

CT_RESPONSE = {
    "id": 1,
    "name": "Solar",
    "channel": 1,
    "iotWhemId": "whem_001",
    "activePower": 3500,
    "activePower2": None,
    "energyConsumption": 9876.5,
    "energyConsumption2": None,
    "energyImport": 50.0,
    "energyImport2": None,
    "rmsCurrent": 2900,
    "rmsCurrent2": None,
    "connected": True,
    "usageType": "solar",
    # Extra field from real API
    "ctType": "production",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def aiohttp_session():
    """Provide an aiohttp ClientSession."""
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
async def client(aiohttp_session):
    """Provide an unauthenticated LevitonClient."""
    return LevitonClient(aiohttp_session)


@pytest.fixture
async def authenticated_client(aiohttp_session):
    """Provide a LevitonClient with a restored session."""
    c = LevitonClient(aiohttp_session)
    c.restore_session("tok_abc123", "user_001")
    return c


@pytest.fixture
def mock_api():
    """Provide an aioresponses mock context."""
    with aioresponses() as m:
        yield m
