"""Camera platform for ECOVACS Live View."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import web

from homeassistant.components.camera import Camera
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
    """Set up ECOVACS live-view camera entities."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    manager = runtime["manager"]
    robots = runtime["devices"]
    async_add_entities(
        [EcovacsLiveCamera(robot, manager) for robot in robots],
        update_before_add=False,
    )


class EcovacsLiveCamera(EcovacsLiveEntity, Camera):
    """Live camera backed by the robot Kinesis/WebRTC video track."""

    _attr_name = "Live view"
    _attr_content_type = "image/jpeg"

    def __init__(self, robot: dict[str, Any], manager: Any) -> None:
        Camera.__init__(self)
        EcovacsLiveEntity.__init__(self, robot, manager)
        self._attr_unique_id = f"{self.did}_live_view_camera"

    @property
    def is_streaming(self) -> bool:
        return self.manager.is_streaming(self.did)

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the newest frame as JPEG.

        Start Live View explicitly with the integration button first.
        """
        return self.manager.get_latest_image(self.did)

    async def handle_async_mjpeg_stream(
        self,
        request: web.Request,
    ) -> web.StreamResponse:
        """Serve the received robot frames as an MJPEG stream."""
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            },
        )
        await response.prepare(request)

        last_sequence = -1
        try:
            while self.manager.is_streaming(self.did):
                sequence = self.manager.get_image_sequence(self.did)
                if sequence != last_sequence:
                    jpeg = self.manager.get_latest_image(self.did)
                    if jpeg:
                        header = (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                        )
                        await response.write(header)
                        await response.write(jpeg)
                        await response.write(b"\r\n")
                        last_sequence = sequence
                await asyncio.sleep(0.05)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            try:
                await response.write_eof()
            except (ConnectionResetError, RuntimeError):
                pass

        return response
