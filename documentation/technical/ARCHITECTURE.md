# AGRILENS 5.0.0 architecture

## Sources and generated output

| Role | Location | Notes |
|---|---|---|
| Application source (authoritative) | `application/main.py` | One self-contained file (Tkinter UI, camera, preprocessing, ONNX inference, gates, Admin, OTA). |
| Release model | `models/candidates/agrilens-multicrop-1.0.0/` | `agrilens.onnx`, `labels.txt`, `MODEL_MANIFEST.json`. Becomes `models/production/` only after release approval. |
| Release model since 5.2.0 | `models/candidates/agrilens-multicrop-1.1.0/` | AGRILENS-MULTICROP 1.1.0: same architecture and classes as 1.0.0, own gate calibration (ood_logit 2.90) and comparison with 1.0.0. The row above (1.0.0) is the model of 5.0.0 and 5.1.0. |
| Previous production model | `models/production/agrilens-24class-4.9.4/` | Byte-identical to the 4.9.4 kiosk model. |
| Model registry | `models/manifests/MODEL_REGISTRY.json` | All models with SHA-256, status and dataset. |
| Device scripts | `deployment/raspberry_pi/`, `deployment/ota/ota_update.sh` | Sources for the files on the kiosk. |
| Device package (generated) | `AGRILENS_RaspberryPi/` | Built by `deployment/packaging/build_device_package.py`; never edited by hand. |
| Model trainer (separate program) | `<AGRILENS_5.0.0>\Model_Trainer_Program\trainer\` | Not part of this repository and never on a kiosk. Trains, exports and checks models on a PC; a finished model is handed over by copying its export folder to `models/candidates/<model-id>/`. See `documentation/technical/TRAINING.md`. |
| Diagnosis history (on the kiosk) | `~/AGRILENS_history/` | Written by `DiagnosisHistory` in `main.py` (since 5.3.0) on a background thread after each diagnosis: leaf image + JSON record per diagnosis, `diagnosis_log.csv`. Outside `AGRILENS_RaspberryPi/`, so OTA and rollback never change it. |
| Diagnosis history upload | rclone remote `agrilens_onedrive` → OneDrive folder `history_sync_path` | `HistorySync` in `main.py` (since 5.4.0): background thread, every 30 minutes, internet probe first, `rclone copy` (never deletes in OneDrive). The OneDrive sign-in is rclone's (`~/.config/rclone/rclone.conf`), not the application's. |
| Master dataset | `<AGRILENS_5.0.0>\Model_Trainer_Program\datasets\AGL-MULTICROP-MD\AGL-MULTICROP-MD-1.0.0` | Outside git (images), with the trainer. Manifests and card mirrored in `datasets/master/AGL-MULTICROP-MD/`. |
| Model evaluation and release evidence | `training/evaluation/`, `training/reports/` | Stay in this repository: gate calibration and release evaluation run the kiosk's own `main.py`, and the release tooling reads the frozen results. |

### Why `AGRILENS_RaspberryPi/` and a single `main.py` remain

Deployed 4.9.4 kiosks update by downloading these exact URLs from `https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi/`:
`main.py`, `labels.txt`, `logos/agrilens_logo.jpg`, `logos/gundecha_logo.png`, `HOW_TO_RUN_ON_RASPBERRY_PI.md`, `setup_rpi.sh`, `run_agrilens.sh`, `ota_update.sh`, `setup_remote_ota.sh`, and `agrilens.onnx` when the `MODEL_SHA256` constant in the downloaded `main.py` differs from the local model.
Moving that folder, or splitting `main.py` into modules, would leave deployed kiosks unable to update or unable to start after an update (a 4.9.x updater fetches only `main.py`). 5.0.0 therefore keeps the path and the single file, and makes the folder a build output with `SHA256SUMS` and `RELEASE_MANIFEST.json`.

## Build

```bash
python deployment/packaging/build_device_package.py --model-dir models/candidates/agrilens-multicrop-1.0.0
```

The build refuses if: `MODEL_SHA256` in `main.py` differs from the packaged model; the model output width differs from the label count; `MODEL_NUM_CLASSES` differs; `BUILD_TIMESTAMP` is `UNSET`; `main.py` does not compile; or `APP_VERSION` is not newer than the version already in the folder. Text files are written with LF so that the committed bytes are what kiosks download (`.gitattributes`: `AGRILENS_RaspberryPi/** -text`).

## Version identifiers (constants in `main.py`)

`APP_VERSION` in `application/main.py` is the single authoritative version. It must stay a literal in `main.py` because every deployed updater reads it from the downloaded file. Everything else is derived from it: at run time (brand-label tooltip, status bar, start-up log line, OTA User-Agent, downgrade guard, rollback folder name), at build time (`RELEASE_MANIFEST.json`, release record), or by `tools/governance/agl_governance.py bump` (`OTA_RELEASE_ID`, `BUILD_TIMESTAMP`, version markers in `README.md` and `HOW_TO.md`, release-notes stub). The rules and checks are in `documentation/governance/ENGINEERING_GOVERNANCE.md`.

| Constant | 5.0.0 value | Meaning |
|---|---|---|
| `APP_VERSION` | `5.0.0` | Application version; the updaters compare it to block downgrades. |
| `OTA_RELEASE_ID` | `AGRILENS-5.0.0` | Release identity, also in `RELEASE_MANIFEST.json` and the git tag. |
| `MODEL_ID`, `MODEL_VERSION` | `AGRILENS-MULTICROP`, `1.0.0` | Model identity shown in the brand-label tooltip and the start-up console line. |
| `MODEL_SHA256` | SHA-256 of the release `agrilens.onnx` | Drives model delivery by OTA and gate-calibration selection. |
| `DATASET_VERSION` | `AGL-MULTICROP-MD 1.0.0` | Training dataset. |
| `MODEL_CALIBRATION_*` | confidence 0.40, margin 0.12, ood_logit (frozen by `training/evaluation/calibrate_gates.py`) | Gate thresholds calibrated for this model. |

## Inference path

1. Image from camera or file, manual crop box.
2. Six views: full resize, square fit and 256→224 centre crop, each as natural RGB and as "screen-restored" RGB; 224×224, ImageNet mean/std.
3. ONNX logits for each view; logit average; softmax.
4. Gates: top-1 probability ≥ confidence threshold, top-1 minus top-2 ≥ margin, maximum averaged logit ≥ ood_logit. Any failure gives a "not recognised / retake" result instead of a diagnosis.
5. Class index → `labels.txt` line (24 lines, same order as 4.9.4). `MODEL_NUM_CLASSES` and the model output width are checked at load; on mismatch the app runs in DEMO mode instead of mislabelling.

### Model-specific gate calibration (new in 5.0.0)

`resolve_gate_thresholds(cfg, model_sha256)` chooses the thresholds for the model that is actually loaded:

1. Saved Admin thresholds are used only when the config's `calibration_model_sha256` equals the loaded model's SHA-256.
2. Otherwise, if the loaded model is the release model, the embedded `MODEL_CALIBRATION_*` values are used.
3. Otherwise (unrecognised model file) the generic code defaults are used.

This removes a 4.9.4 defect: a device config saved with `ood_logit` 6.0 was applied to any model. Saving settings in the Admin Console now records `calibration_model_sha256`. The start-up console line names the threshold source.

## OTA

There are two update paths. Both use the same file list, version guard and checks.

| Path | Trigger | Code |
|---|---|---|
| Startup updater | systemd `agrilens-ota.service` at boot (installed by `setup_remote_ota.sh`), and `main.py` itself at start-up (`_trigger_ota_update(silent_boot=True)`) | `ota_update.sh` (embedded Python), `main.py` |
| In-app updater | Admin Console button **☁ OTA UPDATE (INTERNET)** | `main.py` `_trigger_ota_update(silent_boot=False)` |

Sequence (5.0.0 updaters):

1. Download `main.py`; read `APP_VERSION`; refuse a lower version ("Downgrade blocked").
2. Compile the downloaded `main.py` (`py_compile`) before replacing anything.
3. If the downloaded `MODEL_SHA256` differs from the local model, download `agrilens.onnx` and accept it only if its SHA-256 equals `MODEL_SHA256`.
4. Copy every file about to be replaced into `rollback/v<running version>/` (first copy wins), then replace files.
5. Restart the kiosk.

The hold file `~/.agrilens_ota_hold` (created by `rollback.sh`) stops automatic updates by the 5.0.0+ updaters; a manual Admin update or `ota_update.sh --force` still works.

A 4.9.4 kiosk receiving 5.0.0 runs the 4.9.4 updater. That updater downloads the files listed above (not `rollback.sh`; the 5.0.0 `ota_update.sh` it installs fetches `rollback.sh` on the next update), verifies the model hash, and keeps no rollback copy for this first hop. The repository keeps the 4.9.4 files in `tests/regression/baseline/legacy_4.9.4/`, `models/production/agrilens-24class-4.9.4/` and the prepared rollback release.

Publishing is done only with `deployment/ota/publish_ota_release.ps1` (verifies the build, hashes and tests, requires typing the release id, then merges to `main`, tags and pushes). It replaces the retired `push_ota_update.bat` (archived in `archive/legacy_tools/`), which ran `git add -A` and pushed without checks. Deviation on record: 5.0.0 itself was published on 2026-11-17 by a direct fast-forward push, without the publisher and without a tag (`documentation/CHANGE_REGISTER.md`, `CR-0001`).

Rollback: `documentation/technical/ROLLBACK.md`.
