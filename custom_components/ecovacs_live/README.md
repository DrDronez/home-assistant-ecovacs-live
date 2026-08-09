# ECOVACS Live View 0.8.3

Custom Home Assistant integration providing ECOVACS robot Live View using the ECOVACS/Kinesis WebRTC path.

## 0.8.3 performance fix

This release fixes a Home Assistant performance problem that could occur when the **Live view camera entity was enabled but the ECOVACS video session was idle**.

The previous MJPEG handler ended the HTTP response immediately whenever Live View was not running. Camera clients could interpret the immediate end-of-stream as a failure and reconnect repeatedly. Version 0.8.3 keeps the MJPEG client connection stable while idle and only performs low-frequency keepalive work until Live View starts.

Additional changes:

- Routine WebRTC/ICE/signalling telemetry is logged at `DEBUG` rather than `WARNING`.
- JPEG encoding for active Live View is moved to Home Assistant's executor so image encoding does not block the HA event loop.
- Camera and status entities explicitly do not poll.
- Integration version bumped to `0.8.3`.

## Installation

Copy:

```text
custom_components/ecovacs_live/
```

into:

```text
/config/custom_components/ecovacs_live/
```

Then restart Home Assistant or reload the custom integration after replacing the files.

For an existing installation, the config entry and entity IDs are retained.

## Testing 0.8.3

1. Enable the `Live view` camera entity.
2. Leave the Live View status at `idle`; do **not** press Start.
3. Confirm Home Assistant remains responsive.
4. Press `Start live view` and confirm video starts.
5. Press `Stop live view` and confirm the camera returns to idle without slowing Home Assistant.
