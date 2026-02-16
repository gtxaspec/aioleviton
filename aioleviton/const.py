"""Constants for the aioleviton library."""

API_BASE_URL = "https://my.leviton.com/api"
WEBSOCKET_URL = "wss://socket.cloud.leviton.com/"

LOGIN_ENDPOINT = "/Person/login"
LOGOUT_ENDPOINT = "/Person/logout"
PERMISSIONS_ENDPOINT = "/Person/{person_id}/residentialPermissions"
ACCOUNTS_ENDPOINT = "/ResidentialAccounts/{account_id}"
ACCOUNT_RESIDENCES_ENDPOINT = "/ResidentialAccounts/{account_id}/residences"
RESIDENCE_WHEMS_ENDPOINT = "/Residences/{residence_id}/iotWhems"
RESIDENCE_PANELS_ENDPOINT = "/Residences/{residence_id}/residentialBreakerPanels"
WHEM_ENDPOINT = "/IotWhems/{whem_id}"
WHEM_BREAKERS_ENDPOINT = "/IotWhems/{whem_id}/residentialBreakers"
WHEM_CTS_ENDPOINT = "/IotWhems/{whem_id}/iotCts"
PANEL_ENDPOINT = "/ResidentialBreakerPanels/{panel_id}"
PANEL_BREAKERS_ENDPOINT = "/ResidentialBreakerPanels/{panel_id}/residentialBreakers"
BREAKER_ENDPOINT = "/ResidentialBreakers/{breaker_id}"
PERMISSION_RESIDENCE_ENDPOINT = "/ResidentialPermissions/{permission_id}/residence"

# Energy history endpoints (traffic-verified 2026-02-16)
# These hit my.leviton.com which 307-redirects to AWS API Gateway:
#   https://1gjjrv8tx8.execute-api.us-east-1.amazonaws.com/prod/energy/...
# aiohttp follows redirects automatically.
ENERGY_DAY_ENDPOINT = "/Residences/getAllEnergyConsumptionForDay"
ENERGY_WEEK_ENDPOINT = "/Residences/getAllEnergyConsumptionForWeek"
ENERGY_MONTH_ENDPOINT = "/Residences/getAllEnergyConsumptionForMonth"
ENERGY_YEAR_ENDPOINT = "/Residences/getAllEnergyConsumptionForYear"

# Firmware check
FIRMWARE_CHECK_ENDPOINT = "/LcsApps/getFirmware"

TOKEN_TTL_DEFAULT = 5_184_000  # 60 days in seconds
TOKEN_REFRESH_BUFFER = 86_400  # Refresh 1 day before expiry

HTTP_STATUS_2FA_REQUIRED = 406
HTTP_STATUS_INVALID_CODE = 408
HTTP_STATUS_UNAUTHORIZED = 401
