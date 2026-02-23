# aioleviton

Async Python client for the Leviton My Leviton cloud API.

Supports LWHEM and DAU/LDATA Smart Load Centers with WebSocket real-time push and REST API fallback.

## Features

- Pure `asyncio` with `aiohttp` -- no blocking calls
- Accepts an injected `aiohttp.ClientSession` for connection pooling
- WebSocket real-time push notifications with automatic subscription management
- Full REST API coverage: authentication, device discovery, breaker control, energy history
- Typed data models with PEP 561 `py.typed` marker
- Support for both hub types: LWHEM (`IotWhem`) and DAU/LDATA (`ResidentialBreakerPanel`)
- Two-factor authentication (2FA) support

## Installation

```bash
pip install aioleviton
```

## Quick Start

```python
import aiohttp
from aioleviton import LevitonClient

async def main():
    async with aiohttp.ClientSession() as session:
        # Authenticate
        client = LevitonClient(session)
        auth = await client.login("user@example.com", "password")

        # Discover devices
        permissions = await client.get_permissions()
        for perm in permissions:
            if perm.residential_account_id:
                residences = await client.get_residences(perm.residential_account_id)
                for residence in residences:
                    whems = await client.get_whems(residence.id)
                    panels = await client.get_panels(residence.id)

        # Get breakers for a LWHEM hub
        for whem in whems:
            breakers = await client.get_whem_breakers(whem.id)
            cts = await client.get_cts(whem.id)

        # Get breakers for a DAU panel
        for panel in panels:
            breakers = await client.get_panel_breakers(panel.id)

        # Connect WebSocket for real-time updates
        ws = client.create_websocket()
        await ws.connect()

        # Subscribe to a hub (delivers all child breaker/CT updates)
        await ws.subscribe("IotWhem", whem.id)

        # Handle notifications
        ws.on_notification(lambda data: print("Update:", data))

        # Clean up
        await ws.disconnect()
        await client.logout()
```

> **Note:** On LWHEM firmware 2.0.0+, hub subscriptions no longer deliver
> individual breaker updates. You must subscribe to each `ResidentialBreaker`
> separately. CT updates are still delivered via the hub subscription on all
> firmware versions.

## Supported Devices

| Device | API Model | Hub Type |
|--------|-----------|----------|
| LWHEM (Whole Home Energy Module) | `IotWhem` | Wi-Fi hub |
| DAU / LDATA (Data Acquisition Unit) | `ResidentialBreakerPanel` | Wi-Fi hub |
| Smart Breaker Gen 1 (trip only) | `ResidentialBreaker` | Child of LWHEM or DAU |
| Smart Breaker Gen 2 (on/off) | `ResidentialBreaker` | Child of LWHEM or DAU |
| Current Transformer (CT) | `IotCt` | Child of LWHEM only |
| LSBMA Add-on CT | `ResidentialBreaker` | Virtual composite |

## Authentication

```python
# Standard login
auth = await client.login("user@example.com", "password")

# Login with 2FA code
try:
    auth = await client.login("user@example.com", "password")
except LevitonTwoFactorRequired:
    code = input("Enter 2FA code: ")
    auth = await client.login("user@example.com", "password", code=code)

# Restore a previous session (skip login)
client.restore_session(token="saved_token", user_id="saved_user_id")

# Check auth state
client.authenticated  # True/False
client.token           # current token string or None
client.user_id         # current user ID or None

# Logout (invalidates token)
await client.logout()
```

## Device Discovery

```python
# Get all permissions for the authenticated user
permissions = await client.get_permissions()

# Get residences via account ID
residences = await client.get_residences(account_id)

# Get a residence via permission ID (when permission has residenceId but no account)
residence = await client.get_residence_from_permission(permission_id)

# List hubs in a residence
whems = await client.get_whems(residence_id)     # LWHEM hubs
panels = await client.get_panels(residence_id)   # DAU/LDATA panels

# Get a single hub by ID
whem = await client.get_whem(whem_id)
panel = await client.get_panel(panel_id)

# Get child devices
breakers = await client.get_whem_breakers(whem_id)    # LWHEM breakers
breakers = await client.get_panel_breakers(panel_id)  # DAU panel breakers
cts = await client.get_cts(whem_id)                   # LWHEM CTs
```

## Breaker Control

```python
# Trip a Gen 1 breaker (cannot turn back on remotely)
await client.trip_breaker(breaker_id)

# Turn on/off a Gen 2 breaker
await client.turn_on_breaker(breaker_id)
await client.turn_off_breaker(breaker_id)

# Blink LED on a breaker (toggle on/off)
await client.blink_led(breaker_id)
await client.stop_blink_led(breaker_id)

# Identify LED on a LWHEM hub (on only, no off)
await client.identify_whem(whem_id)
```

## Bandwidth Control

Bandwidth controls the energy reporting mode on hubs. This affects both REST API
responses and WebSocket push frequency.

```python
# LWHEM: 0 = off, 1 = fast (period deltas), 2 = medium (default)
await client.set_whem_bandwidth(whem_id, bandwidth=1)

# DAU panel: True = real-time, False = off
await client.set_panel_bandwidth(panel_id, enabled=True)
```

> **Warning:** With bandwidth=1, the LWHEM REST API returns `energyConsumption`
> as period deltas instead of lifetime totals. Reset to 0 before reading energy
> via REST to get correct lifetime values.

## Firmware Updates

```python
# Check for available firmware
firmware = await client.check_firmware(
    app_id="LWHEM",
    model="AZ",
    serial="1000_XXXX_XXXX",
    model_type="IotWhem",
)
for fw in firmware:
    print(f"v{fw['version']}: {fw['fileUrl']}")

# Trigger OTA update on a LWHEM hub
await client.trigger_whem_ota(whem_id)
```

## Energy History

Energy history endpoints return consumption data for all devices in a residence.
Data is keyed by hub ID, then by breaker position and CT channel.

```python
# Daily energy (hourly data points)
day = await client.get_energy_for_day(
    residence_id=123456,
    start_day="2026-02-16",
    timezone="America/Los_Angeles",
)

# Weekly energy (daily data points for 7 days)
week = await client.get_energy_for_week(
    residence_id=123456,
    start_day="2026-02-17",
    timezone="America/Los_Angeles",
)

# Monthly energy (daily data points for billing month)
month = await client.get_energy_for_month(
    residence_id=123456,
    billing_day_in_month="2026-02-28",
    timezone="America/Los_Angeles",
)

# Yearly energy (monthly data points for 12 months)
year = await client.get_energy_for_year(
    residence_id=123456,
    billing_day_in_end_month="2026-02-16",
    timezone="America/Los_Angeles",
)

# Response structure:
# {
#   "<hub_id>": {
#     "residentialBreakers": {"<position>": [{x, timestamp, energyConsumption, totalCost, ...}]},
#     "iotCts": {"<channel>": [...]},
#     "totals": [...]
#   },
#   "totals": [...]  # residence-level totals
# }
```

## WebSocket

The WebSocket client provides real-time push notifications for device state changes.

```python
# Create and connect
ws = client.create_websocket()
await ws.connect()

# Subscribe to hubs
await ws.subscribe("IotWhem", whem_id)
await ws.subscribe("ResidentialBreakerPanel", panel_id)
await ws.subscribe("ResidentialBreaker", breaker_id)  # FW 2.0.0+ only

# Register callbacks (returns unregister function)
remove_notify = ws.on_notification(lambda data: print(data))
remove_disconnect = ws.on_disconnect(lambda: print("disconnected"))

# Unsubscribe from a model
await ws.unsubscribe("IotWhem", whem_id)

# Check state
ws.connected       # True if connected and authenticated
ws.subscriptions   # set of (model_name, model_id) tuples

# Reconnect (preserves and re-subscribes all previous subscriptions)
await ws.reconnect()

# Calculate backoff delay for reconnection loops
delay = LevitonWebSocket.reconnect_delay(attempts=3)

# Disconnect (preserves subscriptions for later reconnect)
await ws.disconnect()

# Full teardown (clears subscriptions and callbacks)
await ws.reset()
```

## Model Properties

### Breaker

```python
breaker.is_smart        # True if real smart breaker (not placeholder/LSBMA)
breaker.is_placeholder  # True if placeholder/dummy (NONE, NONE-1, NONE-2)
breaker.is_lsbma        # True if physical LSBMA CT accessory
breaker.has_lsbma       # True if placeholder with LSBMA CTs attached
breaker.is_gen2         # True if Gen 2 (supports remote on/off, alias for can_remote_on)
```

### Panel

```python
panel.is_online  # True if online timestamp > offline timestamp
```

## Exceptions

| Exception | Meaning |
|-----------|---------|
| `LevitonError` | Base exception for all API errors |
| `LevitonAuthError` | Authentication failed (wrong credentials) |
| `LevitonTokenExpired` | Auth token has expired (subclass of `LevitonAuthError`) |
| `LevitonTwoFactorRequired` | 2FA code needed (HTTP 406) |
| `LevitonInvalidCode` | Invalid 2FA code (HTTP 408) |
| `LevitonConnectionError` | Network or API connection error |

## Debug Logging

```python
from aioleviton import enable_debug_logging

enable_debug_logging()  # sets aioleviton logger to DEBUG
```

## Roadmap

- Future compatibility with other Leviton product lines (Decora smart switches, dimmers, etc.)

## Disclaimer

This is a do-it-yourself project for Leviton Load Center product users and is not affiliated with, endorsed by, or sponsored by Leviton Manufacturing Co., Inc. "Leviton" and all related product names are trademarks of Leviton Manufacturing Co., Inc. This library interacts with Leviton's cloud services using your own account credentials. Use at your own risk.

## License

MIT
