# AGRILENS 5.1.0 release notes (built, not published)
| Item | Value |
|---|---|
| OTA release id | `AGRILENS-5.1.0` |
| Previous version | 5.0.0 |
| Increment | minor: Camera captures at the Logitech C270 maximum 1280x720 (MJPG) with automatic fallback to 640x480; configurable via cam_resolution |
| Model | AGRILENS-MULTICROP 1.0.0, unchanged (SHA-256 `776d08ac…0332b`); kiosks do not download the model again |
| Status | Built into `AGRILENS_RaspberryPi/` on branch `release/agrilens-5.1.0`. Not published, not deployed. |
## What changes for a kiosk
- The camera is requested at 1280×720 in MJPG instead of 640×480. MJPG is requested because the C270 streams 1280×720 YUYV at only about 7.5 frames per second over USB 2.0.
- If the camera delivers no frames at 1280×720, the kiosk retries the same port at 640×480. The status bar shows the size actually delivered (for example `USB Camera (Port 0, V4L2, 1280x720)`).
- New setting `cam_resolution` (`1280x720` default, or `640x480`) in `kiosk_config.json` / `~/.agrilens_kiosk_config.json`. Kiosks updating from 5.0.0 have no such key and therefore use 1280×720. Invalid values fall back to `1280x720`.
- Preview, crop handles, digital zoom, focus metric and diagnosis work on the full-size frame. Diagnosis still uses the same 224×224 input, so the model and gate thresholds are unchanged.
## Tests
- Desktop, Windows, mocked OpenCV: `pytest -q`, 196 passed, 0 failed (2026-11-18). New tests cover the default 1280×720 request with MJPG, the fallback to 640×480 when HD delivers no frames, a camera that silently stays at 640×480, a configured `640x480`, and validation and precedence of `cam_resolution`.
- Not tested: a real Logitech C270, the Raspberry Pi 5 (preview frame rate and CPU load at 1280×720, MJPG decoding), and diagnosis accuracy on live 1280×720 captures.
## Known limitations
- The model and gate calibration were validated on image files, not on live C270 captures at either resolution. Results on 1280×720 captures may differ from 5.0.0 captures; check on the exhibition hardware.
- Each preview frame has about 3 times as many pixels as at 640×480; on the Raspberry Pi 5 the preview may be slower. If so, set `cam_resolution` to `640x480`.
- Fleet rollback: kiosks on 5.1.0 refuse the prepared `AGRILENS-5.0.1-rollback` as a downgrade (see `documentation/technical/ROLLBACK.md`).
- All 5.0.0 limitations remain (Mango Die Back recall, Gall Midge, unknown inputs often accepted): [`RELEASE_NOTES_5.0.0.md`](RELEASE_NOTES_5.0.0.md).
