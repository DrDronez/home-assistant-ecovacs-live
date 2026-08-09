"""Sensors for ECOVACS Live View."""
from __future__ import annotations

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
    runtime = hass.data[DOMAIN][entry.entry_id]
    manager = runtime["manager"]
    async_add_entities(
        EcovacsLiveViewStatusSensor(robot, manager)
        for robot in runtime["devices"]
    )


class EcovacsLiveViewStatusSensor(EcovacsLiveEntity, SensorEntity):
    _attr_name = "Live view status"
    _attr_icon = "mdi:video-wireless-outline"

    def __init__(self, robot, manager) -> None:
        super().__init__(robot, manager)
        self._attr_unique_id = f"{self.did}_live_view_status"

    @property
    def native_value(self):
        return self.manager.status.get(self.did, "idle")

    @property
    def extra_state_attributes(self):
        live = self.manager.sessions.get(self.did)
        frames = (
            live.video_frames
            if live is not None
            else self.manager.frames.get(self.did, 0)
        )
        return {
            "streaming": self.manager.is_streaming(self.did),
            "video_frames_received": frames,
            "session_elapsed_seconds": self.manager.get_session_elapsed(self.did),
            "auto_stop_minutes": self.manager.auto_stop_minutes,
            "auto_stop_remaining_seconds": self.manager.get_auto_stop_remaining(self.did),
            "last_error": self.manager.errors.get(self.did),
        }
