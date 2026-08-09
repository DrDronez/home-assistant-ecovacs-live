"""Sensor platform for ECOVACS Live View."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    """Set up ECOVACS live-view status sensors."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    manager = runtime["manager"]
    robots = runtime["devices"]
    async_add_entities(
        [EcovacsLiveStatusSensor(robot, manager) for robot in robots],
        update_before_add=False,
    )


class EcovacsLiveStatusSensor(EcovacsLiveEntity, SensorEntity):
    """Expose the state of one ECOVACS Live View session."""

    _attr_name = "Live view status"
    _attr_icon = "mdi:cctv"
    _attr_should_poll = False

    def __init__(self, robot: dict[str, Any], manager: Any) -> None:
        super().__init__(robot, manager)
        self._attr_unique_id = f"{self.did}_live_view_status"

    @property
    def native_value(self) -> str:
        """Return the current Live View status."""
        return self.manager.status.get(self.did, "idle")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful non-sensitive runtime diagnostics."""
        return {
            "streaming": self.manager.is_streaming(self.did),
            "video_frames": self.manager.frames.get(self.did, 0),
            "session_elapsed_seconds": self.manager.get_session_elapsed(self.did),
            "auto_stop_remaining_seconds": self.manager.get_auto_stop_remaining(self.did),
            "last_error": self.manager.errors.get(self.did),
        }
