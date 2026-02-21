"""Tests for aioleviton data models."""

import dataclasses

import pytest

from aioleviton.models import (
    AuthToken,
    Breaker,
    Ct,
    Panel,
    Permission,
    Residence,
    Whem,
)

from .conftest import (
    BREAKER_GEN2_RESPONSE,
    BREAKER_RESPONSE,
    CT_RESPONSE,
    PANEL_RESPONSE,
    PERMISSION_RESPONSE,
    RESIDENCE_RESPONSE,
    WHEM_RESPONSE,
)

# ---------------------------------------------------------------------------
# AuthToken
# ---------------------------------------------------------------------------


class TestAuthToken:
    def test_creation(self):
        token = AuthToken(
            token="tok_1",
            ttl=3600,
            created="2026-01-01T00:00:00Z",
            user_id="u1",
            user={"email": "a@b.com"},
        )
        assert token.token == "tok_1"
        assert token.ttl == 3600
        assert token.user_id == "u1"
        assert token.user == {"email": "a@b.com"}

    def test_immutability(self):
        token = AuthToken(token="tok_1", ttl=3600, created="", user_id="u1", user={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            token.token = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------


class TestPermission:
    def test_from_api(self):
        p = Permission.from_api(PERMISSION_RESPONSE)
        assert p.id == 1
        assert p.access == "admin"
        assert p.status == "accepted"
        assert p.person_id == "user_001"
        assert p.residence_id == 100
        assert p.residential_account_id == 200

    def test_optional_fields_none(self):
        data = {
            "id": 2,
            "access": "viewer",
            "status": "pending",
            "personId": "user_002",
        }
        p = Permission.from_api(data)
        assert p.residence_id is None
        assert p.residential_account_id is None

    def test_immutability(self):
        p = Permission.from_api(PERMISSION_RESPONSE)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.access = "viewer"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Residence
# ---------------------------------------------------------------------------


class TestResidence:
    def test_from_api(self):
        r = Residence.from_api(RESIDENCE_RESPONSE)
        assert r.id == 100
        assert r.name == "Test Home"
        assert r.status == "active"
        assert r.timezone_id == "America/New_York"
        assert r.residential_account_id == 200
        assert r.energy_cost == 0.12

    def test_timezone_none_when_missing(self):
        data = {"id": 101, "name": "No TZ"}
        r = Residence.from_api(data)
        assert r.timezone_id is None

    def test_timezone_none_when_not_dict(self):
        data = {"id": 102, "name": "Bad TZ", "timezone": "America/Chicago"}
        r = Residence.from_api(data)
        assert r.timezone_id is None

    def test_timezone_none_value(self):
        """timezone field present but explicitly None."""
        data = {"id": 103, "timezone": None}
        r = Residence.from_api(data)
        assert r.timezone_id is None

    def test_defaults(self):
        data = {"id": 103}
        r = Residence.from_api(data)
        assert r.name == ""
        assert r.status == ""
        assert r.energy_cost is None
        assert r.residential_account_id is None


# ---------------------------------------------------------------------------
# Whem
# ---------------------------------------------------------------------------


class TestWhem:
    def test_from_api(self):
        w = Whem.from_api(WHEM_RESPONSE)
        assert w.id == "whem_001"
        assert w.name == "Main Panel LWHEM"
        assert w.model == "LWHEM"
        assert w.serial == "1000_AAAA_BBBB"
        assert w.connected is True
        assert w.rms_voltage_a == 121
        assert w.rms_voltage_b == 122
        assert w.frequency_a == 60
        assert w.bandwidth == 0
        assert w.raw == WHEM_RESPONSE

    def test_defaults(self):
        data = {"id": "whem_002"}
        w = Whem.from_api(data)
        assert w.name == ""
        assert w.model == "LWHEM"
        assert w.serial == "whem_002"  # defaults to id
        assert w.manufacturer == "Leviton Manufacturing Co., Inc."
        assert w.connected is False
        assert w.version is None
        assert w.local_ip is None

    def test_update_partial(self):
        w = Whem.from_api(dict(WHEM_RESPONSE))
        w.update({"rmsVoltageA": 119, "connected": False})
        assert w.rms_voltage_a == 119
        assert w.connected is False
        # unchanged fields
        assert w.rms_voltage_b == 122

    def test_update_raw_merge(self):
        w = Whem.from_api(dict(WHEM_RESPONSE))
        w.update({"newField": "value", "bandwidth": 1})
        assert w.bandwidth == 1
        assert w.raw["newField"] == "value"

    def test_update_ignores_unknown_keys(self):
        w = Whem.from_api(dict(WHEM_RESPONSE))
        original_name = w.name
        w.update({"unknownApiField": 42})
        assert w.name == original_name
        assert w.raw["unknownApiField"] == 42

    def test_none_values_for_optional_fields(self):
        """API sometimes sends explicit None for optional fields."""
        data = {
            "id": "whem_003",
            "version": None,
            "versionBLE": None,
            "localIP": None,
            "mac": None,
            "rssi": None,
            "rmsVoltageA": None,
            "rmsVoltageB": None,
            "frequencyA": None,
            "frequencyB": None,
            "panelSize": None,
            "breakerCount": None,
            "bandwidth": None,
        }
        w = Whem.from_api(data)
        assert w.version is None
        assert w.rms_voltage_a is None
        assert w.bandwidth is None


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class TestPanel:
    def test_from_api(self):
        p = Panel.from_api(PANEL_RESPONSE)
        assert p.id == "panel_001"
        assert p.name == "Sub Panel DAU"
        assert p.model == "DAU"
        assert p.commissioned is True
        assert p.rms_voltage == 120
        assert p.wifi_ssid == "TestNetwork"
        assert p.version_bcm == "1.0.0"
        assert p.package_ver == "4.0.0"

    def test_is_online_true(self):
        """online > offline means is_online=True."""
        p = Panel.from_api(PANEL_RESPONSE)
        assert p.is_online is True

    def test_is_online_false_when_offline_newer(self):
        data = {
            **PANEL_RESPONSE,
            "online": "2026-01-01T06:00:00.000Z",
            "offline": "2026-01-01T12:00:00.000Z",
        }
        p = Panel.from_api(data)
        assert p.is_online is False

    def test_is_online_false_when_no_online(self):
        data = {**PANEL_RESPONSE, "online": None}
        p = Panel.from_api(data)
        assert p.is_online is False

    def test_is_online_true_when_no_offline(self):
        data = {**PANEL_RESPONSE, "offline": None}
        p = Panel.from_api(data)
        assert p.is_online is True

    def test_is_online_false_on_invalid_timestamps(self):
        data = {**PANEL_RESPONSE, "online": "not-a-date", "offline": "also-bad"}
        p = Panel.from_api(data)
        assert p.is_online is False

    def test_is_online_equal_timestamps(self):
        """Same online and offline timestamp → not online (online > offline)."""
        ts = "2026-01-01T12:00:00.000Z"
        data = {**PANEL_RESPONSE, "online": ts, "offline": ts}
        p = Panel.from_api(data)
        assert p.is_online is False

    def test_update(self):
        p = Panel.from_api(dict(PANEL_RESPONSE))
        p.update({"bandwidth": 1, "rmsVoltage": 119})
        assert p.bandwidth == 1
        assert p.rms_voltage == 119
        assert p.name == "Sub Panel DAU"  # unchanged

    def test_defaults(self):
        data = {"id": "panel_002"}
        p = Panel.from_api(data)
        assert p.name == ""
        assert p.model == "DAU"
        assert p.manufacturer == "Leviton"
        assert p.commissioned is False
        assert p.online is None
        assert p.offline is None

    def test_none_values_for_optional_fields(self):
        """API sometimes sends explicit None for optional fields."""
        data = {
            "id": "panel_003",
            "rmsVoltage": None,
            "rmsVoltage2": None,
            "wifiMode": None,
            "wifiRSSI": None,
            "wifiSSID": None,
            "versionBCM": None,
            "packageVer": None,
        }
        p = Panel.from_api(data)
        assert p.rms_voltage is None
        assert p.wifi_mode is None
        assert p.package_ver is None


# ---------------------------------------------------------------------------
# Breaker
# ---------------------------------------------------------------------------


class TestBreaker:
    def test_from_api(self):
        b = Breaker.from_api(BREAKER_RESPONSE)
        assert b.id == "brk_001"
        assert b.name == "Kitchen"
        assert b.model == "L5120"
        assert b.position == 1
        assert b.poles == 1
        assert b.current_rating == 20
        assert b.current_state == "ON"
        assert b.power == 500
        assert b.energy_consumption == 12345.6
        assert b.connected is True
        assert b.can_remote_on is False
        assert b.firmware_version_ble == "1.0.0"
        assert b.hw_version == "A1"
        assert b.serial_number == "SN12345"

    def test_is_smart(self):
        b = Breaker.from_api(BREAKER_RESPONSE)
        assert b.is_smart is True

    def test_is_smart_false_for_placeholder(self):
        data = {**BREAKER_RESPONSE, "model": "NONE"}
        b = Breaker.from_api(data)
        assert b.is_smart is False

    def test_is_placeholder(self):
        for model in ("NONE", "NONE-1", "NONE-2"):
            data = {**BREAKER_RESPONSE, "model": model}
            b = Breaker.from_api(data)
            assert b.is_placeholder is True

    def test_is_placeholder_false_for_smart(self):
        b = Breaker.from_api(BREAKER_RESPONSE)
        assert b.is_placeholder is False

    def test_is_lsbma(self):
        data = {**BREAKER_RESPONSE, "model": "LSBMA"}
        b = Breaker.from_api(data)
        assert b.is_lsbma is True
        assert b.is_smart is False

    def test_is_lsbma_false(self):
        b = Breaker.from_api(BREAKER_RESPONSE)
        assert b.is_lsbma is False

    def test_has_lsbma(self):
        data = {**BREAKER_RESPONSE, "model": "NONE", "lsbmaId": "lsbma_1"}
        b = Breaker.from_api(data)
        assert b.has_lsbma is True

    def test_has_lsbma_false_not_placeholder(self):
        data = {**BREAKER_RESPONSE, "lsbmaId": "lsbma_1"}
        b = Breaker.from_api(data)
        assert b.has_lsbma is False  # is_placeholder is False

    def test_has_lsbma_false_no_lsbma_id(self):
        data = {**BREAKER_RESPONSE, "model": "NONE"}
        b = Breaker.from_api(data)
        assert b.has_lsbma is False

    def test_is_gen2(self):
        b = Breaker.from_api(BREAKER_GEN2_RESPONSE)
        assert b.is_gen2 is True

    def test_is_gen2_false(self):
        b = Breaker.from_api(BREAKER_RESPONSE)
        assert b.is_gen2 is False

    def test_update(self):
        b = Breaker.from_api(dict(BREAKER_RESPONSE))
        b.update({"power": 600, "currentState": "OFF", "connected": False})
        assert b.power == 600
        assert b.current_state == "OFF"
        assert b.connected is False
        assert b.name == "Kitchen"  # unchanged

    def test_update_raw_merge(self):
        b = Breaker.from_api(dict(BREAKER_RESPONSE))
        b.update({"extraField": 99})
        assert b.raw["extraField"] == 99

    def test_firmware_none_for_empty_string(self):
        data = {
            **BREAKER_RESPONSE,
            "firmwareVersionBLE": "",
            "firmwareVersionMeter": "",
            "hwVersion": "",
            "serialNumber": "",
        }
        b = Breaker.from_api(data)
        assert b.firmware_version_ble is None
        assert b.firmware_version_meter is None
        assert b.hw_version is None
        assert b.serial_number is None

    def test_defaults(self):
        data = {"id": "brk_min"}
        b = Breaker.from_api(data)
        assert b.name == ""
        assert b.model == ""
        assert b.position == 0
        assert b.poles == 1
        assert b.connected is False
        assert b.remote_trip is False
        assert b.can_remote_on is False
        assert b.locked is False
        assert b.blink_led is False

    def test_none_values_for_measurement_fields(self):
        """Measurement fields can be None when breaker reports no data."""
        data = {
            "id": "brk_none",
            "power": None,
            "rmsCurrent": None,
            "rmsVoltage": None,
            "energyConsumption": None,
            "energyImport": None,
            "lineFrequency": None,
            "currentRating": None,
            "bleRSSI": None,
        }
        b = Breaker.from_api(data)
        assert b.power is None
        assert b.rms_current is None
        assert b.energy_consumption is None
        assert b.current_rating is None


# ---------------------------------------------------------------------------
# Ct
# ---------------------------------------------------------------------------


class TestCt:
    def test_from_api(self):
        ct = Ct.from_api(CT_RESPONSE)
        assert ct.id == 1
        assert ct.name == "Solar"
        assert ct.channel == 1
        assert ct.iot_whem_id == "whem_001"
        assert ct.active_power == 3500
        assert ct.energy_consumption == 9876.5
        assert ct.connected is True
        assert ct.usage_type == "solar"

    def test_update(self):
        ct = Ct.from_api(dict(CT_RESPONSE))
        ct.update({"activePower": 4000, "connected": False})
        assert ct.active_power == 4000
        assert ct.connected is False
        assert ct.name == "Solar"  # unchanged

    def test_update_raw_merge(self):
        ct = Ct.from_api(dict(CT_RESPONSE))
        ct.update({"newKey": "newVal"})
        assert ct.raw["newKey"] == "newVal"

    def test_defaults(self):
        data = {"id": 2}
        ct = Ct.from_api(data)
        assert ct.name == ""
        assert ct.channel == 0
        assert ct.iot_whem_id == ""
        assert ct.connected is False
        assert ct.active_power is None
        assert ct.usage_type is None
