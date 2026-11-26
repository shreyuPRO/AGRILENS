# Configuration (AGRILENS 5.0.0)

Source of truth: `load_kiosk_config()`, `save_kiosk_config()` and `resolve_gate_thresholds()` in `application/main.py`. This page describes that code; if they disagree, the code wins and this page must be corrected.

## Files and precedence

| Order | Source | Location on the kiosk |
|---|---|---|
| 1 | Built-in defaults (`DEFAULT_CONFIG`) | in `main.py` |
| 2 | Application-folder file `kiosk_config.json` | `~/AGRILENS_RaspberryPi/kiosk_config.json` (shipped from `application/configuration/kiosk_config.default.json`) |
| 3 | User file `.agrilens_kiosk_config.json` | `~/.agrilens_kiosk_config.json` |

Later sources override earlier ones key by key. Every value is then clamped to its allowed range; an unreadable file is reported on the console and skipped. Saving in the Admin Console writes the same settings to both files (user file first).

`kiosk_config.json` is not in the OTA file list, so an update never replaces a kiosk's settings.

## Keys

| Key | Default | Range | Meaning |
|---|---|---|---|
| `confidence_threshold` | 0.40 | 0.30 to 0.95 | Minimum top-1 probability |
| `ood_margin` | 0.12 | 0.10 to 0.60 | Minimum gap between the top two classes |
| `ood_logit` | 1.40 (generic) | 1.00 to 6.50 | Minimum maximum logit; below it the leaf is rejected as UNKNOWN PLANT |
| `sharpness_min` | 25.0 | 20 to 120 | Focus threshold used by the image-quality message |
| `calibration_model_sha256` | none | | Written by 5.0.0 when settings are saved: the model the three thresholds above were saved for |
| `cam_contrast`, `cam_saturation` | 100 | 50 to 200, 0 to 200 | Software image adjustment (percent) |
| `cam_brightness`, `cam_wb_temp` | 0 | -50 to 50 | Software brightness and white-balance tint |
| `cam_sharpness` | 100 | 50 to 250 | Software sharpening (percent) |
| `cam_zoom` | 100 | 100 to 200 | Digital centre zoom (percent) |
| `cam_flip_h`, `cam_flip_v` | false | | Mirror / 180° flip |
| `cam_auto_exp`, `cam_auto_wb` | true | | UVC auto exposure (with 50 Hz anti-flicker through `v4l2-ctl`) and auto white balance |
| `cam_resolution` | `1280x720` | `1280x720`, `640x480` | Capture resolution requested from the camera (since 5.1.0). `1280x720` is the Logitech C270 maximum and is requested in MJPG. If the camera delivers no frames in that mode, the kiosk retries the same port at 640×480; the status bar shows the size actually delivered. Any other value falls back to `1280x720`. Set `640x480` to get the 5.0.0 capture behaviour. Not editable in the Admin panel; edit the file and restart the kiosk (or tap **DETECT WEBCAM**). |
| `history_enabled` | true | true, false | Diagnosis history (since 5.3.0): every DIAGNOSE NOW stores the diagnosed (cropped) leaf image and a record in `~/AGRILENS_history/`. Set `false` to stop recording; existing history is kept. |
| `history_max_images` | 5000 | 0 to 100000 | Maximum number of stored leaf images; above it the oldest images and their records are deleted (`diagnosis_log.csv` is never trimmed). 0 keeps everything. No image is written while less than 300 MB of disk space is free (the record is still written, with `save_status` saying so). |
| `history_sync_enabled` | true | true, false | Upload of the diagnosis history to OneDrive (since 5.4.0) with `rclone copy`. Does nothing until rclone is installed and the remote below exists. |
| `history_sync_remote` | `agrilens_onedrive` | letters, digits, `_ - .` | Name of the rclone remote that holds the OneDrive sign-in (`rclone config`). The sign-in itself is stored by rclone in `~/.config/rclone/rclone.conf`, never in the kiosk settings. |
| `history_sync_path` | `AGRILENS_Kiosk_History` | folder path in OneDrive | Destination folder in OneDrive, `/`-separated, no `..`. For the project folder set it to the path shown by `rclone lsd`, for example `<your folders>/AGRILENS_5.0.0/Kiosk_History`. |
| `history_sync_minutes` | 30 | 5 to 1440 | Upload interval. The first attempt is about 2 minutes after the kiosk starts; offline attempts are skipped and the next one catches up. |
| `language` | `EN` | `EN`, `HI` | Main-screen language |

Legacy migration: if a loaded configuration has `ood_logit` ≥ 1.80 and `confidence_threshold` ≥ 0.48 at the same time, the three thresholds and `sharpness_min` are reset to the code defaults.

## Which rejection thresholds are used

`resolve_gate_thresholds()` picks the thresholds for the model that is actually loaded:

1. Saved thresholds, only if `calibration_model_sha256` equals the SHA-256 of the loaded `agrilens.onnx`.
2. Otherwise, if the loaded model is the release model (`MODEL_SHA256`), its calibration (`MODEL_CALIBRATION_*`). Since 5.2.0 (model 1.1.0): confidence 0.40, margin 0.12, ood_logit 2.90, from `models/candidates/agrilens-multicrop-1.1.0/calibration/FROZEN_GATE_CALIBRATION.json`. 5.0.0 and 5.1.0 (model 1.0.0): ood_logit 2.10, from `training/evaluation/calibration_1.0.0/FROZEN_GATE_CALIBRATION.json`. Thresholds saved on a kiosk for the previous model (field `calibration_model_sha256`) are ignored after the model changes, so a kiosk updated to 5.2.0 uses 2.90 even if its Admin slider had been moved; set the slider again if needed.
3. Otherwise (unrecognised model file) the generic defaults: 0.40, 0.12, 1.40.

So thresholds saved under 4.9.4, for example `ood_logit` 6.0, are not applied to the 5.0.0 model. The start-up console line shows the result, for example `AGRILENS 5.2.0: model ONNX AGRILENS-MULTICROP 1.1.0; rejection gates from calibration of AGRILENS-MULTICROP 1.1.0: confidence 0.40, margin 0.12, logit 2.9`.

Changing thresholds is a release decision. Do not tune them on test data or on single field reports (`documentation/governance/ENGINEERING_GOVERNANCE.md`, engineering rules).

## Other files and switches

| Path | Effect |
|---|---|
| `~/.agrilens_ota_hold` | Stops automatic updates by the 5.0.0+ updaters (boot service and start-up check). Manual Admin update and `ota_update.sh --force` still work. 4.9.x code ignores it. |
| `~/.config/autostart/agrilens.desktop` | Created by `main.py` on first start on Linux; starts the kiosk at desktop login |
| `rollback/v<version>/` in the application folder | Copies kept by the 5.0.0+ updaters before they replace a file (`documentation/technical/ROLLBACK.md`) |
