"""Camera platform for ECOVACS Live View."""
from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

from aiohttp import web

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EcovacsLiveEntity

# Small valid JPEG used only to keep an idle MJPEG connection alive when no
# previous robot frame exists.  Keeping the HTTP stream open prevents clients
# from entering a rapid connect/EOF/reconnect loop while Live View is idle.
_IDLE_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAAJABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AJgAD//Z"
)

_IDLE_KEEPALIVE_SECONDS = 10.0
_IDLE_CHECK_SECONDS = 0.5
_LIVE_CHECK_SECONDS = 0.05


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
    _attr_should_poll = False

    def __init__(self, robot: dict[str, Any], manager: Any) -> None:
        Camera.__init__(self)
        EcovacsLiveEntity.__init__(self, robot, manager)
        self._attr_unique_id = f"{self.did}_live_view_camera"

    @property
    def is_streaming(self) -> bool:
        """Return whether the ECOVACS WebRTC session is active."""
        return self.manager.is_streaming(self.did)

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes:
        """Return a valid JPEG without starting Live View.

        Home Assistant exposes this method through /api/camera_proxy and uses
        that URL as the camera entity picture.  Returning None while idle makes
        the proxy request fail, which can cause frontends to retry the thumbnail
        repeatedly.  Return the latest robot frame when available, otherwise a
        tiny static JPEG.
        """
        return self.manager.get_latest_image(self.did) or _IDLE_JPEG

    @staticmethod
    async def _write_mjpeg_frame(
        response: web.StreamResponse,
        jpeg: bytes,
    ) -> None:
        """Write one complete MJPEG part."""
        header = (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
        )
        await response.write(header)
        await response.write(jpeg)
        await response.write(b"\r\n")

    async def handle_async_mjpeg_stream(
        self,
        request: web.Request,
    ) -> web.StreamResponse:
        """Serve robot frames while keeping the MJPEG connection stable when idle.

        The previous implementation ended the HTTP response immediately whenever
        the robot's WebRTC session was idle.  Camera clients can interpret that
        immediate EOF as a failed stream and reconnect repeatedly, creating a
        high-rate request loop even though Live View itself has never been started.

        This handler instead keeps each client connection open.  While idle it
        sleeps cheaply and sends only an occasional cached/placeholder JPEG to
        keep intermediaries from timing the stream out.  Once Live View starts,
        new robot frames are forwarded without requiring the client to reconnect.
        """
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
        last_keepalive = 0.0

        try:
            while True:
                transport = request.transport
                if transport is None or transport.is_closing():
                    break

                if self.manager.is_streaming(self.did):
                    sequence = self.manager.get_image_sequence(self.did)
                    if sequence != last_sequence:
                        jpeg = self.manager.get_latest_image(self.did)
                        if jpeg:
                            await self._write_mjpeg_frame(response, jpeg)
                            last_sequence = sequence
                            last_keepalive = time.monotonic()
                    await asyncio.sleep(_LIVE_CHECK_SECONDS)
                    continue

                # Idle: do not terminate the response.  Ending it immediately can
                # make dashboards reconnect continuously.  Send a very infrequent
                # frame only to keep the established HTTP stream healthy.
                now = time.monotonic()
                if now - last_keepalive >= _IDLE_KEEPALIVE_SECONDS:
                    jpeg = self.manager.get_latest_image(self.did) or _IDLE_JPEG
                    await self._write_mjpeg_frame(response, jpeg)
                    last_keepalive = now

                await asyncio.sleep(_IDLE_CHECK_SECONDS)

        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        except RuntimeError:
            # aiohttp may raise RuntimeError when a client closes during a write.
            pass
        finally:
            try:
                await response.write_eof()
            except (ConnectionResetError, BrokenPipeError, RuntimeError):
                pass

        return response
