"""Constants for ECOVACS Live View."""
from __future__ import annotations

DOMAIN = "ecovacs_live"

CONF_ACCOUNT = "account"
CONF_PASSWORD = "password"
CONF_COUNTRY = "country"
CONF_LIVE_VIEW_PIN = "live_view_pin"
CONF_CLIENT_ID = "client_id"
CONF_AUTO_STOP_MINUTES = "auto_stop_minutes"

DEFAULT_COUNTRY = "AU"
DEFAULT_AUTO_STOP_MINUTES = 10

PLATFORMS = ["button", "sensor", "camera"]
