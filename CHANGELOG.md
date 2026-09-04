# Changelog

## 0.8.2

Compatibility fix.

- Updated `deebot-client` from 18.4.0 to 18.5.1.
- Fixes Home Assistant config-flow failure:
  `cannot import name 'DeviceVerificationRequiredError'`.
- Keeps all Live View behavior from 0.8.1 unchanged.

## 0.8.1

Privacy/security hardening release.

- Removed Opus audio payloads copied from development traffic.
- Replaced them with synthetic Opus silence.
- Removed robot DID values from ECOVACS Live View log messages.
- Re-audited the repository for hardcoded account/device/session data.
- No intended feature changes.

Tested successfully on an ECOVACS DEEBOT T90 OMNI.
