"""ECOVACS Live View integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .client import async_authenticate_and_discover
from .const import (
    CONF_AUTO_STOP_MINUTES,
    CONF_CLIENT_ID,
    CONF_COUNTRY,
    CONF_LIVE_VIEW_PIN,
    DEFAULT_AUTO_STOP_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .live_view import LiveViewManager

_LOGGER = logging.getLogger(__name__)


def _device_name(device: dict[str, Any]) -> str:
    return str(
        device.get("nick")
        or device.get("deviceName")
        or device.get("name")
        or "ECOVACS Robot"
    )


def _device_model(device: dict[str, Any]) -> str:
    return str(
        device.get("deviceName")
        or device.get("model")
        or device.get("class")
        or "ECOVACS Robot"
    )


def _serial(device: dict[str, Any]) -> str:
    """Return the stable ECOVACS serial/name field."""
    return str(device.get("name", "")).strip()


def _migrate_or_remove_stale_device(
    registry: dr.DeviceRegistry,
    entry: ConfigEntry,
    *,
    did: str,
    serial_number: str,
) -> None:
    """Migrate/remove stale device-registry records for one physical robot.

    The ECOVACS serial is used as the physical-device match.  We never dedupe
    based on the friendly display name.
    """
    if not serial_number:
        return

    current_identifier = (DOMAIN, did)
    matching = [
        item
        for item in dr.async_entries_for_config_entry(registry, entry.entry_id)
        if str(item.serial_number or "").strip() == serial_number
    ]

    target = next(
        (item for item in matching if current_identifier in item.identifiers),
        None,
    )

    # If the integration previously registered this physical robot under an
    # old identifier and there is only one candidate, migrate it in place.
    if target is None and len(matching) == 1:
        old = matching[0]
        new_identifiers = {
            identifier
            for identifier in old.identifiers
            if identifier[0] != DOMAIN
        }
        new_identifiers.add(current_identifier)
        try:
            registry.async_update_device(
                old.id,
                new_identifiers=new_identifiers,
                serial_number=serial_number,
            )
        except Exception:
            _LOGGER.exception(
                "Could not migrate stale ECOVACS device registry identifier"
            )
        else:
            _LOGGER.info(
                "Migrated stale ECOVACS registry device to the current DID"
            )
        return

    if target is None:
        return

    # A current-DID target already exists. Remove other records for the same
    # serial after copying useful user-owned metadata where practical.
    for stale in matching:
        if stale.id == target.id:
            continue

        try:
            update_kwargs: dict[str, Any] = {}
            if target.area_id is None and stale.area_id is not None:
                update_kwargs["area_id"] = stale.area_id
            if target.name_by_user is None and stale.name_by_user is not None:
                update_kwargs["name_by_user"] = stale.name_by_user
            merged_labels = set(target.labels) | set(stale.labels)
            if merged_labels != set(target.labels):
                update_kwargs["labels"] = merged_labels

            if update_kwargs:
                updated = registry.async_update_device(target.id, **update_kwargs)
                if updated is not None:
                    target = updated

            registry.async_remove_device(stale.id)
            _LOGGER.info(
                "Removed stale duplicate ECOVACS registry device"
            )
        except Exception:
            _LOGGER.exception(
                "Could not remove stale duplicate ECOVACS registry device"
            )


async def _async_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload when integration options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ECOVACS Live View from a config entry."""
    # Match the now-proven fresh Windows control exactly:
    # one dedicated aiohttp session, deebot-client 18.4.0 Authenticator,
    # and the exact credentials returned by that Authenticator passed directly
    # into start_watch. Do not perform a second custom/classic login.
    live_view_session = aiohttp.ClientSession()
    try:
        authenticator, credentials, rest_config, devices = (
            await async_authenticate_and_discover(
                hass,
                dict(entry.data),
                session=live_view_session,
            )
        )
    except Exception:
        await live_view_session.close()
        raise

    registry = dr.async_get(hass)
    registered: list[dict[str, Any]] = []

    for device in devices:
        did = str(device.get("did", "")).strip()
        if not did:
            continue

        serial_number = _serial(device)
        _migrate_or_remove_stale_device(
            registry,
            entry,
            did=did,
            serial_number=serial_number,
        )

        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, did)},
            manufacturer="ECOVACS",
            name=_device_name(device),
            model=_device_model(device),
            serial_number=serial_number or None,
        )

        service = device.get("service")
        registered.append(
            {
                "did": did,
                "class": str(device.get("class", "")),
                "resource": str(device.get("resource", "")),
                "name": str(device.get("name", "")),
                "device_name": str(device.get("deviceName", "")),
                "nick": str(device.get("nick", "")),
                "model": str(device.get("model", "")),
                "service": dict(service) if isinstance(service, dict) else {},
            }
        )

    manager = LiveViewManager(
        hass,
        aiohttp_session=live_view_session,
        rest_config=rest_config,
        credentials=credentials,
        login_client_id=str(entry.data[CONF_CLIENT_ID]),
        country=str(entry.data[CONF_COUNTRY]),
        pin=str(entry.data[CONF_LIVE_VIEW_PIN]),
        auto_stop_minutes=int(
            entry.options.get(
                CONF_AUTO_STOP_MINUTES,
                DEFAULT_AUTO_STOP_MINUTES,
            )
        ),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "authenticator": authenticator,
        "credentials": credentials,
        "rest_config": rest_config,
        "devices": registered,
        "manager": manager,
        "live_view_session": live_view_session,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "ECOVACS Live View loaded with %d discovered robot(s)",
        len(registered),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an ECOVACS Live View config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if not unloaded:
        return False

    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime:
        manager = runtime.get("manager")
        if manager is not None:
            await manager.stop_all()

        live_view_session = runtime.get("live_view_session")
        if live_view_session is not None and not live_view_session.closed:
            try:
                await live_view_session.close()
            except Exception:
                _LOGGER.exception("Error closing ECOVACS Live View HTTP session")

        authenticator = runtime.get("authenticator")
        if authenticator is not None:
            try:
                await authenticator.teardown()
            except Exception:
                _LOGGER.exception("Error closing ECOVACS authenticator")

    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)
    return True
