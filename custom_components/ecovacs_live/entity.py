"""Shared entities for ECOVACS Live View."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class EcovacsLiveEntity(Entity):
    """Base entity bound to one ECOVACS robot."""

    _attr_has_entity_name = True

    def __init__(self, robot: dict[str, Any], manager: Any) -> None:
        self.robot = robot
        self.manager = manager
        self.did = str(robot["did"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.did)},
            manufacturer="ECOVACS",
            name=str(
                robot.get("nick")
                or robot.get("device_name")
                or robot.get("name")
                or "ECOVACS Robot"
            ),
            model=str(
                robot.get("device_name")
                or robot.get("model")
                or robot.get("class")
                or "ECOVACS Robot"
            ),
            serial_number=str(robot.get("name", "")) or None,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.manager.subscribe(self.async_write_ha_state)
        )
