"""Buttons for ECOVACS Live View."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EcovacsLiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    manager = runtime["manager"]
    entities = []
    for robot in runtime["devices"]:
        entities.extend(
            [
                EcovacsStartLiveViewButton(robot, manager),
                EcovacsStopLiveViewButton(robot, manager),
            ]
        )
    async_add_entities(entities)


class EcovacsStartLiveViewButton(EcovacsLiveEntity, ButtonEntity):
    _attr_name = "Start live view"
    _attr_icon = "mdi:cctv"

    def __init__(self, robot, manager) -> None:
        super().__init__(robot, manager)
        self._attr_unique_id = f"{self.did}_start_live_view"

    async def async_press(self) -> None:
        await self.manager.start(self.robot)


class EcovacsStopLiveViewButton(EcovacsLiveEntity, ButtonEntity):
    _attr_name = "Stop live view"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, robot, manager) -> None:
        super().__init__(robot, manager)
        self._attr_unique_id = f"{self.did}_stop_live_view"

    async def async_press(self) -> None:
        await self.manager.stop(self.robot)
