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

        # Connect WebSocket for real-time updates
        ws = client.create_websocket()
        await ws.connect()

        # Subscribe to a hub (delivers all child breaker/CT updates)
        await ws.subscribe("IotWhem", whem.id)

        # Handle notifications
        ws.on_notification(lambda data: print("Update:", data))
```

> **Note:** On LWHEM firmware 2.0.0+, hub subscriptions no longer deliver
> individual breaker updates. You must subscribe to each `ResidentialBreaker`
> separately. CT updates are still delivered via the hub subscription on all
> firmware versions.

## Debug Logging

```python
from aioleviton import enable_debug_logging

enable_debug_logging()  # sets aioleviton logger to DEBUG
```

## Supported Devices

| Device | API Model | Hub Type |
|--------|-----------|----------|
| LWHEM (Whole Home Energy Module) | `IotWhem` | Wi-Fi hub |
| DAU / LDATA (Data Acquisition Unit) | `ResidentialBreakerPanel` | Wi-Fi hub |
| Smart Breaker Gen 1 (trip only) | `ResidentialBreaker` | Child of LWHEM or DAU |
| Smart Breaker Gen 2 (on/off) | `ResidentialBreaker` | Child of LWHEM or DAU |
| Current Transformer (CT) | `IotCt` | Child of LWHEM only |
| LSBMA Add-on CT | `ResidentialBreaker` | Virtual composite |

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

## Firmware Check

```python
# Check for available firmware updates
firmware = await client.check_firmware(
    app_id="LWHEM",
    model="AZ",
    serial="1000_XXXX_XXXX",
    model_type="IotWhem",
)
# Returns list of firmware objects with version, fileUrl, signature, hash, size, notes
for fw in firmware:
    print(f"v{fw['version']}: {fw['fileUrl']}")
```


## Roadmap

- Future compatibility with other Leviton product lines (Decora smart switches, dimmers, etc.)

## Disclaimer

This is a do-it-yourself project for Leviton Load Center product users and is not affiliated with, endorsed by, or sponsored by Leviton Manufacturing Co., Inc. "Leviton" and all related product names are trademarks of Leviton Manufacturing Co., Inc. This library interacts with Leviton's cloud services using your own account credentials. Use at your own risk.

## License

MIT
