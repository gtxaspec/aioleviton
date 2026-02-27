"""Data models for the Leviton API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuthToken:
    """Authentication token from the Leviton API."""

    token: str
    ttl: int
    created: str
    user_id: str
    user: dict[str, Any]


@dataclass(frozen=True)
class Permission:
    """Residential permission granting access to residences/accounts."""

    id: int
    access: str
    status: str
    person_id: str
    residence_id: int | None
    residential_account_id: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Permission:
        """Create from API response data."""
        return cls(
            id=data["id"],
            access=data["access"],
            status=data["status"],
            person_id=data["personId"],
            residence_id=data.get("residenceId"),
            residential_account_id=data.get("residentialAccountId"),
        )


@dataclass(frozen=True)
class Residence:
    """A physical residence containing devices."""

    id: int
    name: str
    status: str
    timezone_id: str | None
    residential_account_id: int | None
    energy_cost: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Residence:
        """Create from API response data."""
        tz = data.get("timezone")
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            status=data.get("status", ""),
            timezone_id=tz["id"] if isinstance(tz, dict) else None,
            residential_account_id=data.get("residentialAccountId"),
            energy_cost=data.get("energyCost"),
        )


@dataclass
class Whem:
    """IotWhem - Whole Home Energy Module (LWHEM hub)."""

    id: str
    name: str
    model: str
    serial: str
    manufacturer: str
    version: str | None
    version_ble: str | None
    connected: bool
    local_ip: str | None
    mac: str | None
    rssi: int | None
    residence_id: int | None
    rms_voltage_a: int | None
    rms_voltage_b: int | None
    frequency_a: int | None
    frequency_b: int | None
    panel_size: int | None
    breaker_count: int | None
    bandwidth: int | None
    identify: int | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Whem:
        """Create from API response data."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            model=data.get("model", "LWHEM"),
            serial=data.get("serial", data["id"]),
            manufacturer=data.get("manufacturer", "Leviton Manufacturing Co., Inc."),
            version=data.get("version"),
            version_ble=data.get("versionBLE"),
            connected=data.get("connected", False),
            local_ip=data.get("localIP"),
            mac=data.get("mac"),
            rssi=data.get("rssi"),
            residence_id=data.get("residenceId"),
            rms_voltage_a=data.get("rmsVoltageA"),
            rms_voltage_b=data.get("rmsVoltageB"),
            frequency_a=data.get("frequencyA"),
            frequency_b=data.get("frequencyB"),
            panel_size=data.get("panelSize"),
            breaker_count=data.get("breakerCount"),
            bandwidth=data.get("bandwidth"),
            identify=data.get("identify"),
            raw=dict(data),
        )

    def update(self, data: dict[str, Any]) -> None:
        """Update fields from a partial notification."""
        field_map: dict[str, str] = {
            "name": "name",
            "connected": "connected",
            "localIP": "local_ip",
            "mac": "mac",
            "rssi": "rssi",
            "rmsVoltageA": "rms_voltage_a",
            "rmsVoltageB": "rms_voltage_b",
            "frequencyA": "frequency_a",
            "frequencyB": "frequency_b",
            "bandwidth": "bandwidth",
            "version": "version",
            "versionBLE": "version_ble",
            "identify": "identify",
            "panelSize": "panel_size",
            "breakerCount": "breaker_count",
        }
        for api_key, attr_name in field_map.items():
            if api_key in data:
                setattr(self, attr_name, data[api_key])
        self.raw.update(data)


@dataclass
class Panel:
    """ResidentialBreakerPanel - DAU/LDATA hub."""

    id: str
    name: str
    model: str
    manufacturer: str
    breaker_count: int | None
    panel_size: int | None
    status: str | None
    commissioned: bool
    residence_id: int | None
    bandwidth: int | None
    rms_voltage: int | None
    rms_voltage_2: int | None
    wifi_mode: str | None
    wifi_rssi: int | None
    wifi_ssid: str | None
    version_bcm: str | None
    version_bcm_radio: str | None
    version_bsm: str | None
    version_bsm_radio: str | None
    version_ncm: str | None
    package_ver: str | None
    online: str | None
    offline: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_online(self) -> bool:
        """Return True if the panel is online.

        Compares online/offline ISO 8601 timestamps. The panel is online
        if the online timestamp is more recent than the offline timestamp.
        """
        if self.online is None:
            return False
        if self.offline is None:
            return True
        try:
            online_dt = datetime.fromisoformat(self.online)
            offline_dt = datetime.fromisoformat(self.offline)
            return online_dt > offline_dt
        except (ValueError, AttributeError):
            return False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Panel:
        """Create from API response data."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            model=data.get("model", "DAU"),
            manufacturer=data.get("manufacturer", "Leviton"),
            breaker_count=data.get("breakerCount"),
            panel_size=data.get("panelSize"),
            status=data.get("status"),
            commissioned=data.get("commissioned", False),
            residence_id=data.get("residenceId"),
            bandwidth=data.get("bandwidth"),
            rms_voltage=data.get("rmsVoltage"),
            rms_voltage_2=data.get("rmsVoltage2"),
            wifi_mode=data.get("wifiMode"),
            wifi_rssi=data.get("wifiRSSI"),
            wifi_ssid=data.get("wifiSSID"),
            version_bcm=data.get("versionBCM"),
            version_bcm_radio=data.get("versionBCMRadio"),
            version_bsm=data.get("versionBSM"),
            version_bsm_radio=data.get("versionBSMRadio"),
            version_ncm=data.get("versionNCM"),
            package_ver=data.get("packageVer"),
            online=data.get("online"),
            offline=data.get("offline"),
            raw=dict(data),
        )

    def update(self, data: dict[str, Any]) -> None:
        """Update fields from a partial notification."""
        field_map: dict[str, str] = {
            "name": "name",
            "status": "status",
            "bandwidth": "bandwidth",
            "rmsVoltage": "rms_voltage",
            "rmsVoltage2": "rms_voltage_2",
            "wifiMode": "wifi_mode",
            "wifiRSSI": "wifi_rssi",
            "wifiSSID": "wifi_ssid",
            "online": "online",
            "offline": "offline",
            "packageVer": "package_ver",
            "versionBCM": "version_bcm",
            "versionBCMRadio": "version_bcm_radio",
            "versionBSM": "version_bsm",
            "versionBSMRadio": "version_bsm_radio",
            "versionNCM": "version_ncm",
            "commissioned": "commissioned",
        }
        for api_key, attr_name in field_map.items():
            if api_key in data:
                setattr(self, attr_name, data[api_key])
        self.raw.update(data)


@dataclass
class Breaker:
    """ResidentialBreaker - individual circuit breaker."""

    id: str
    name: str
    model: str
    branch_type: str | None
    position: int
    poles: int
    current_rating: int | None
    current_state: str | None
    current_state_2: str | None
    operational_state: str | None
    power: int | None
    power_2: int | None
    rms_current: int | None
    rms_current_2: int | None
    rms_voltage: int | None
    rms_voltage_2: int | None
    energy_consumption: float | None
    energy_consumption_2: float | None
    energy_import: float | None
    energy_import_2: float | None
    line_frequency: float | None
    line_frequency_2: float | None
    ble_rssi: int | None
    connected: bool
    remote_trip: bool
    remote_state: str | None
    remote_on: bool
    can_remote_on: bool
    firmware_version_ble: str | None
    firmware_version_meter: str | None
    firmware_version_silabs: str | None
    firmware_version_gfci: str | None
    firmware_version_afci: str | None
    hw_version: str | None
    serial_number: str | None
    locked: bool
    blink_led: bool
    lsbma_id: str | None
    lsbma_id_2: str | None
    lsbma_parent_id: str | None
    iot_whem_id: str | None
    residential_breaker_panel_id: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_smart(self) -> bool:
        """Return True if this is a real smart breaker (not placeholder)."""
        return self.model not in ("NONE", "NONE-1", "NONE-2", "LSBMA")

    @property
    def is_placeholder(self) -> bool:
        """Return True if this is a placeholder/dummy breaker."""
        return self.model in ("NONE", "NONE-1", "NONE-2")

    @property
    def is_lsbma(self) -> bool:
        """Return True if this is a physical LSBMA CT accessory."""
        return self.model == "LSBMA"

    @property
    def has_lsbma(self) -> bool:
        """Return True if this placeholder has LSBMA CTs attached."""
        return self.is_placeholder and bool(self.lsbma_id)

    @property
    def is_gen2(self) -> bool:
        """Return True if this is a Gen 2 breaker (supports remote on/off)."""
        return self.can_remote_on

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Breaker:
        """Create from API response data."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            model=data.get("model", ""),
            branch_type=data.get("branchType"),
            position=data.get("position", 0),
            poles=data.get("poles", 1),
            current_rating=data.get("currentRating"),
            current_state=data.get("currentState"),
            current_state_2=data.get("currentState2"),
            operational_state=data.get("operationalState"),
            power=data.get("power"),
            power_2=data.get("power2"),
            rms_current=data.get("rmsCurrent"),
            rms_current_2=data.get("rmsCurrent2"),
            rms_voltage=data.get("rmsVoltage"),
            rms_voltage_2=data.get("rmsVoltage2"),
            energy_consumption=data.get("energyConsumption"),
            energy_consumption_2=data.get("energyConsumption2"),
            energy_import=data.get("energyImport"),
            energy_import_2=data.get("energyImport2"),
            line_frequency=data.get("lineFrequency"),
            line_frequency_2=data.get("lineFrequency2"),
            ble_rssi=data.get("bleRSSI"),
            connected=data.get("connected", False),
            remote_trip=data.get("remoteTrip", False),
            remote_state=data.get("remoteState"),
            remote_on=data.get("remoteOn", False),
            can_remote_on=data.get("canRemoteOn", False),
            firmware_version_ble=data.get("firmwareVersionBLE") or None,
            firmware_version_meter=data.get("firmwareVersionMeter") or None,
            firmware_version_silabs=data.get("firmwareVersionSiLabs") or None,
            firmware_version_gfci=data.get("firmwareVersionGFCI") or None,
            firmware_version_afci=data.get("firmwareVersionAFCI") or None,
            hw_version=data.get("hwVersion") or None,
            serial_number=data.get("serialNumber") or None,
            locked=data.get("locked", False),
            blink_led=data.get("blinkLED", False),
            lsbma_id=data.get("lsbmaId") or None,
            lsbma_id_2=data.get("lsbmaId2") or None,
            lsbma_parent_id=data.get("lsbmaParentId"),
            iot_whem_id=data.get("iotWhemId"),
            residential_breaker_panel_id=data.get("residentialBreakerPanelId"),
            raw=dict(data),
        )

    def update(self, data: dict[str, Any]) -> None:
        """Update fields from a partial notification."""
        field_map: dict[str, str] = {
            "name": "name",
            "currentState": "current_state",
            "currentState2": "current_state_2",
            "operationalState": "operational_state",
            "power": "power",
            "power2": "power_2",
            "rmsCurrent": "rms_current",
            "rmsCurrent2": "rms_current_2",
            "rmsVoltage": "rms_voltage",
            "rmsVoltage2": "rms_voltage_2",
            "energyConsumption": "energy_consumption",
            "energyConsumption2": "energy_consumption_2",
            "energyImport": "energy_import",
            "energyImport2": "energy_import_2",
            "lineFrequency": "line_frequency",
            "lineFrequency2": "line_frequency_2",
            "bleRSSI": "ble_rssi",
            "connected": "connected",
            "remoteTrip": "remote_trip",
            "remoteState": "remote_state",
            "remoteOn": "remote_on",
            "locked": "locked",
            "blinkLED": "blink_led",
        }
        for api_key, attr_name in field_map.items():
            if api_key in data:
                setattr(self, attr_name, data[api_key])
        self.raw.update(data)


@dataclass
class Ct:
    """IotCt - Current Transformer clamp (LWHEM only)."""

    id: int
    name: str
    channel: int
    iot_whem_id: str
    active_power: int | None
    active_power_2: int | None
    energy_consumption: float | None
    energy_consumption_2: float | None
    energy_import: float | None
    energy_import_2: float | None
    rms_current: int | None
    rms_current_2: int | None
    connected: bool
    usage_type: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Ct:
        """Create from API response data."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            channel=data.get("channel", 0),
            iot_whem_id=data.get("iotWhemId", ""),
            active_power=data.get("activePower"),
            active_power_2=data.get("activePower2"),
            energy_consumption=data.get("energyConsumption"),
            energy_consumption_2=data.get("energyConsumption2"),
            energy_import=data.get("energyImport"),
            energy_import_2=data.get("energyImport2"),
            rms_current=data.get("rmsCurrent"),
            rms_current_2=data.get("rmsCurrent2"),
            connected=data.get("connected", False),
            usage_type=data.get("usageType"),
            raw=dict(data),
        )

    def update(self, data: dict[str, Any]) -> None:
        """Update fields from a partial notification."""
        field_map: dict[str, str] = {
            "activePower": "active_power",
            "activePower2": "active_power_2",
            "energyConsumption": "energy_consumption",
            "energyConsumption2": "energy_consumption_2",
            "energyImport": "energy_import",
            "energyImport2": "energy_import_2",
            "rmsCurrent": "rms_current",
            "rmsCurrent2": "rms_current_2",
            "connected": "connected",
        }
        for api_key, attr_name in field_map.items():
            if api_key in data:
                setattr(self, attr_name, data[api_key])
        self.raw.update(data)
