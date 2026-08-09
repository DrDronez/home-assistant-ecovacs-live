"""ECOVACS account and raw robot discovery helpers."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

import aiohttp

from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.util import md5

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCOUNT,
    CONF_CLIENT_ID,
    CONF_COUNTRY,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)

_APP_ID = "ecovacs"
_APP_VERSION = "3.15.0"
_APP_CHANNEL = "google_play"
_REALM = "ecouser.net"


def _jwt_resource(token: str) -> str:
    """Extract the ECOVACS login resource from the JWT payload without verifying it.

    The token itself has already been returned by the authenticated ECOVACS login.
    ECOVACS HOME uses the JWT's ``r`` claim as auth.resource for
    GetGlobalDeviceList.
    """
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return ""
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        if isinstance(data, dict):
            return str(data.get("r") or "")
    except Exception:
        _LOGGER.debug("Unable to decode ECOVACS JWT resource claim", exc_info=True)
    return ""


async def async_get_global_device_list(
    session: aiohttp.ClientSession,
    *,
    rest_config: Any,
    credentials: Any,
    login_client_id: str,
) -> list[dict[str, Any]]:
    """Return the raw ECOVACS robot list using the app's proven API call.

    This reproduces ECOVACS HOME 3.15.0:
      POST /api/appsvr/app.do
      todo = GetGlobalDeviceList

    Unlike deebot-client's model parsing, this returns the server's raw device
    dictionaries, so unsupported robots such as the T90 retain the real DID,
    class and resource values.
    """
    user_id = str(credentials.user_id)
    token = str(credentials.token)
    auth_resource = (
        str(getattr(credentials, "resource", "") or "")
        or _jwt_resource(token)
        or login_client_id
    )

    auth = {
        "resource": auth_resource,
        "token": token,
        "realm": _REALM,
        "userid": user_id,
        "with": "users",
    }

    body = {
        "userid": user_id,
        "lang": "EN",
        "platform": "android",
        "appVer": _APP_VERSION,
        "channel": _APP_CHANNEL,
        "aliliving": True,
        "share": True,
        "software": "robotui_config",
        "auth": auth,
        "todo": "GetGlobalDeviceList",
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "appid": _APP_ID,
        "token": token,
        "userid": user_id,
        "Authorization": f"Bearer {token}",
    }

    url = f"{str(rest_config.portal_url).rstrip('/')}/api/appsvr/app.do"

    async with session.post(url, json=body, headers=headers, timeout=60) as response:
        raw = await response.text()
        status = response.status

    if status >= 400:
        raise RuntimeError(
            f"ECOVACS GetGlobalDeviceList failed with HTTP {status}"
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "ECOVACS GetGlobalDeviceList returned invalid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "ECOVACS GetGlobalDeviceList returned a non-object response"
        )

    if str(payload.get("ret", "")).lower() != "ok":
        raise RuntimeError(
            "ECOVACS GetGlobalDeviceList failed "
            f"(code={payload.get('code')!r}, ret={payload.get('ret')!r}, "
            f"message={(payload.get('message') or payload.get('msg'))!r})"
        )

    raw_devices = payload.get("devices")
    if not isinstance(raw_devices, list):
        raise RuntimeError(
            "ECOVACS GetGlobalDeviceList response did not contain devices[]"
        )

    devices: list[dict[str, Any]] = []
    for value in raw_devices:
        if not isinstance(value, dict):
            continue
        device = dict(value)
        did = str(device.get("did", "")).strip()
        device_class = str(device.get("class", "")).strip()
        resource = str(device.get("resource", "")).strip()
        if not (did and device_class and resource):
            _LOGGER.warning(
                "Ignoring incomplete ECOVACS device record from GetGlobalDeviceList"
            )
            continue
        devices.append(device)

    _LOGGER.info(
        "ECOVACS GetGlobalDeviceList returned %d usable robot(s)",
        len(devices),
    )
    return devices



async def async_authenticate_and_discover(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    *,
    session: aiohttp.ClientSession | None = None,
) -> tuple[Authenticator, Any, Any, list[dict[str, Any]]]:
    """Authenticate and discover robots using ECOVACS HOME's raw device-list call."""
    if session is None:
        session = async_get_clientsession(hass)

    login_client_id = str(entry_data[CONF_CLIENT_ID])
    rest_config = create_rest_config(
        session,
        device_id=login_client_id,
        alpha_2_country=str(entry_data[CONF_COUNTRY]),
    )
    authenticator = Authenticator(
        rest_config,
        str(entry_data[CONF_ACCOUNT]),
        md5(str(entry_data[CONF_PASSWORD])),
    )

    credentials = await authenticator.authenticate()
    devices = await async_get_global_device_list(
        session,
        rest_config=rest_config,
        credentials=credentials,
        login_client_id=login_client_id,
    )

    return authenticator, credentials, rest_config, devices
