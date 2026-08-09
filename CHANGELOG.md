# Changelog

## 0.8.3

- Fix idle camera snapshot requests returning no image.
- Always return a valid tiny JPEG from `async_camera_image()` when Live View has not been started and no cached frame exists.
- Prevent Home Assistant camera proxy/entity-picture requests from failing while the camera is idle.
- Retain the 0.8.2 stable idle MJPEG connection and WebRTC performance/logging improvements.

## 0.8.2

- Fixed idle camera MJPEG request churn that could make Home Assistant slow while Live View was enabled but not started.
- Keep idle MJPEG connections open with inexpensive periodic keepalive frames.
- Moved active-frame JPEG encoding off the Home Assistant event loop.
- Reduced normal WebRTC negotiation/state logging from warning to debug level.
- Added explicit non-polling behavior for camera/status entities.
