# Home Assistant 2026.10 / PyAV 19 test build

This branch is an experimental Live View compatibility build for Home Assistant
2026.10.0.

## Install for testing

1. Back up the Home Assistant configuration, including the existing
   `custom_components/ecovacs_live` directory.
2. Copy **the entire** `custom_components/ecovacs_live` directory from this
   branch over the existing directory in the Home Assistant configuration.
   Include `_vendor` and its subdirectories.
3. Restart Home Assistant. Confirm ECOVACS Live View loads and starts a Live
   View session. Check the logs for dependency installation, import, codec, or
   connection errors.
4. To roll back, restore the previous integration directory and Home Assistant
   backup.

HACS may replace these files when it updates the integration. This test build
pins `av==19.0.0` and targets Home Assistant 2026.10; it is not intended for
older Home Assistant releases that pin a different PyAV version.

## What changed

`aiortc` 1.15.0 is a pure Python package, but its published metadata requires
`av<18`. This branch carries the 1.15.0 package under `_vendor/aiortc` and
declares its other runtime dependencies in `manifest.json` alongside Home
Assistant 2026.10's `av==19.0.0`. Two absolute imports inside the package were
made relative so it can load from `_vendor`. The license is included in
`_vendor/aiortc/LICENSE`.

Source: https://pypi.org/project/aiortc/1.15.0/ (wheel SHA-256
`4e1e54bff31a9c2cb654c7b7edc068085a7df53365e5df24a5cb24168e3f95f7`).

Local smoke checks on Python 3.14 with PyAV 19.0.0 passed package import,
peer connection construction, and VP8/H.264 frame encoding.

On October 8, 2026, the branch was installed through HACS on Home Assistant
2026.10.0 and tested with a GOAT O1000 LiDAR Pro. The integration loaded, the
session reached `video_received`, and the camera preview displayed a frame.
The stream was then stopped and returned to idle. The test was performed at
night, so image quality in daylight and longer sessions remain unverified.

## Current test state and later return to main

- The local checkout and fork's test build are on
  `codex/av19-live-view-test`. Keep this branch selected until the test is over.
- Home Assistant's HACS entry for the fork has
  `codex/av19-live-view-test` installed. The original upstream HACS entry is
  still registered separately. The Live View session was stopped after the
  successful test.
- HACS may offer to update the fork to its default `main` commit. Do not take
  that update while testing: the current `main` still has the aiortc/PyAV
  conflict on Home Assistant 2026.10.
- Checking out `main` in the local Git repository does not change the files
  installed in Home Assistant. When an updated `main` supports PyAV 19, use
  HACS to install that version, restart Home Assistant, and verify the
  integration before removing the fork's custom repository entry.
- To return this checkout to the fork's main branch later, fetch `origin/main`
  and switch to it. Preserve this test branch as a recovery point until the
  replacement has passed the same Live View test.
