# AGRILENS how-to and documentation index

This is the navigation guide for the AGRILENS repository. Each section gives the short answer and links to the one document that holds the details. The index at the end is generated from `tools/governance/governance_rules.json` and checked automatically (file exists, path, UTF-8, no BOM, no malformed characters).

## Project overview

AGRILENS is an offline touch kiosk that diagnoses leaf diseases of Apple, Mango, Potato and Tomato (24 classes) on a Raspberry Pi 5 with a Logitech C270 camera and a 7" 1024×600 touch display. Overview, classes and repository layout: [`README.md`](README.md).

## Current version

| Item | Value |
|---|---|
| Application | **<!-- agl:version -->5.4.0<!-- /agl:version -->** (authoritative: `APP_VERSION` in `application/main.py`) |
| On GitHub `main` / OTA | 5.0.0 since 2026-11-17 (`documentation/CHANGE_REGISTER.md`, `CR-0001`) |
| Model | AGRILENS-MULTICROP 1.1.0 (SHA-256 `0774ca4a…e0f08e`), since 5.2.0; 1.0.0 before |
| Validation status | Desktop only. Raspberry Pi 5, C270 and expert validation not yet performed. One release criterion (C2, Mango) failed and was accepted as a recorded deviation. |

Show every version value and where it comes from: `python tools/governance/agl_governance.py version`.

## Quick start

| Goal | Do this |
|---|---|
| Run on a PC | `pip install -r application/requirements.txt`, then `python AGRILENS_RaspberryPi/main.py` ([`documentation/technical/INSTALLATION.md`](documentation/technical/INSTALLATION.md), section C) |
| Set up a new Raspberry Pi 5 | [`documentation/technical/INSTALLATION.md`](documentation/technical/INSTALLATION.md), section B |
| Develop and commit | `python -m venv .venv`, install `requirements-dev.txt`, `python tools/governance/agl_governance.py install-git-hooks`; rules in [`documentation/governance/ENGINEERING_GOVERNANCE.md`](documentation/governance/ENGINEERING_GOVERNANCE.md) |

`application/main.py` started directly runs in DEMO mode (no model next to it). The runnable build is the generated folder `AGRILENS_RaspberryPi/`.

## Installation

[`documentation/technical/INSTALLATION.md`](documentation/technical/INSTALLATION.md): kiosks already on 4.9.4 (updated by OTA), new Raspberry Pi 5, PC, offline installation from a USB copy.

## Running AGRILENS

On the Pi: `cd ~/AGRILENS_RaspberryPi && ./run_agrilens.sh` (runs one OTA check, then starts the kiosk). The kiosk also starts at desktop login. Thonny, terminal and autostart: [`deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md`](deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md) (the device guide, also shipped to every kiosk).

## Camera setup

- Logitech C270 on USB. Since 5.1.0 the kiosk opens it with Video4Linux2 at 1280×720 (the C270 maximum, MJPG) and falls back to 640×480 if the camera delivers no frames in that mode. Set `cam_resolution` to `640x480` for the 5.0.0 behaviour ([`documentation/technical/CONFIGURATION.md`](documentation/technical/CONFIGURATION.md)).
- The user must be in the `video` group (`sudo usermod -a -G video $USER`). A camera plugged in after start-up: **ADMIN → DETECT WEBCAM**.
- Focus ring and cover for the C270: `documentation/hardware/C270_focus_ring.stl`, `documentation/hardware/C270_cover.stl`. Use **ADMIN → CAMERA CONTROL PANEL** (focus bar, focus peaking, exposure, white balance, zoom, flips) to set focus.
- Camera settings and their ranges: [`documentation/technical/CONFIGURATION.md`](documentation/technical/CONFIGURATION.md).

## Touchscreen usage

Top bar: crop selection (**ALL PLANTS (AUTO)** or one crop), input mode (**LIVE** / **FILE**), language (**हिंदी / EN**), **ADMIN**. Keyboard: `Space` capture or retake, `Escape` close a panel or exit. Details: device guide, section "Using the Kiosk".

## Diagnosis workflow

1. Live mode: hold the leaf in the green box, tap **CAPTURE LEAF**. File mode: tap **PICK FROM FILE** (sample images in `diagnosis_samples/`).
2. Drag the 8 handles so the box contains only the leaf; double-tap for the full image.
3. Tap **DIAGNOSE NOW**. Possible results: a disease, **HEALTHY LEAF**, **LOW CONFIDENCE — PLEASE RETAKE**, or **UNKNOWN PLANT / OUT OF SCOPE**.
4. If a crop is selected, a leaf of another crop is rejected as unknown. Use **ALL PLANTS (AUTO)** when unsure.

Diagnoses are advisory. Known weak classes in 5.0.0: Mango Die Back (often reported as Powdery Mildew), Mango Gall Midge (provisional class); leaves of unsupported conditions such as Mango Turning Brown are often given a diagnosis instead of being rejected. Figures: [`documentation/release_notes/RELEASE_NOTES_5.0.0.md`](documentation/release_notes/RELEASE_NOTES_5.0.0.md).

## Diagnosis history

Since 5.3.0 every **DIAGNOSE NOW** is recorded on the kiosk in `~/AGRILENS_history/` (outside the application folder, so OTA updates and `rollback.sh` never touch it):

- `YYYY-MM-DD/YYYYMMDD_HHMMSS_mmm_<VERDICT>.jpg`: the diagnosed (cropped) leaf image, exactly what the model saw. `<VERDICT>` is `DISEASE`, `HEALTHY`, `LOW_CONFIDENCE` or `UNKNOWN`.
- `YYYY-MM-DD/YYYYMMDD_HHMMSS_mmm_<VERDICT>.json`: the full record: local and UTC time, status and result, crop and condition, confidence, margin, maximum logit, top-3 classes, input mode (LIVE/FILE) and source file, selected crop, crop box and frame size, image quality, camera, rejection thresholds and their source, app version, model id, version and SHA-256, latency, screen language.
- `diagnosis_log.csv`: one row per diagnosis with the same fields (opens in a spreadsheet).

Copy the folder to a USB stick or the PC to review diagnoses or to collect real C270 images. Settings: `history_enabled`, `history_max_images` in [`documentation/technical/CONFIGURATION.md`](documentation/technical/CONFIGURATION.md).

Since 5.4.0 the kiosk also uploads this folder to OneDrive every 30 minutes when the internet is available (`rclone copy`: new files only, nothing is deleted in OneDrive, so images the kiosk removes at its limit stay in OneDrive). One-time setup on the Pi (install rclone, sign in to OneDrive, set the destination folder): device guide, section "Diagnosis history upload to OneDrive". Upload log: `~/AGRILENS_history_sync.log`.

## Offline operation

Diagnosis runs fully on the device; no internet is needed. Internet is used only for OTA checks (at boot, at kiosk start and from the Admin button) and for Raspberry Pi Connect. Without a connection the updater reports GitHub as unreachable and the kiosk continues. To keep a 5.0.0 kiosk from updating when it is next online, create `~/.agrilens_ota_hold`; 4.9.x code ignores that file.

## Configuration

[`documentation/technical/CONFIGURATION.md`](documentation/technical/CONFIGURATION.md): files and precedence, all keys and ranges, how the rejection thresholds are chosen for the loaded model.

## Model information

AGRILENS-MULTICROP 1.1.0 (since 5.2.0; same architecture and classes as 1.0.0, trained with webcam-style augmentation), MobileNetV4-Conv-Small, single-file ONNX (~10 MB), input 224×224, 24 outputs in the order of `labels.txt`. Six-view logit ensemble and three rejection gates: [`documentation/technical/ARCHITECTURE.md`](documentation/technical/ARCHITECTURE.md). Model files and registry: `models/candidates/agrilens-multicrop-1.1.0/` (1.0.0: `models/candidates/agrilens-multicrop-1.0.0/`), `models/manifests/MODEL_REGISTRY.json`. Evaluation: release notes, `models/candidates/agrilens-multicrop-1.1.0/comparison/COMPARISON.md` and `training/reports/agrilens-multicrop-1.0.0/`.

## Training workflow

[`documentation/technical/TRAINING.md`](documentation/technical/TRAINING.md): configurations, training, ONNX export, selection rule, gate calibration and the run-once release evaluation. New training needs a separate approval; frozen datasets and test tiers are never used for tuning.

## Dataset structure

AGL-MULTICROP-MD 1.0.0 (images outside git; manifests, splits and licences in `datasets/master/AGL-MULTICROP-MD/`): [`datasets/master/AGL-MULTICROP-MD/DATASET_CARD.md`](datasets/master/AGL-MULTICROP-MD/DATASET_CARD.md).

## OTA update

Kiosks download a fixed file list from `AGRILENS_RaspberryPi/` on GitHub `main` at boot, at kiosk start or when **ADMIN → ☁ OTA UPDATE (INTERNET)** is tapped. Lower versions are refused; the model is accepted only if its SHA-256 matches `MODEL_SHA256`. Design: [`documentation/technical/ARCHITECTURE.md`](documentation/technical/ARCHITECTURE.md), section OTA. Pushing to `main` updates every kiosk and needs explicit approval.

## Rollback

[`documentation/technical/ROLLBACK.md`](documentation/technical/ROLLBACK.md): one kiosk (`rollback.sh`), the whole fleet (prepared release `AGRILENS-5.0.1-rollback`), the repository. A kiosk restored to 4.9.4 that goes online updates itself to 5.0.0 again, because `main` serves 5.0.0.

## Troubleshooting

| Symptom | Check |
|---|---|
| Real leaves rejected as **UNKNOWN PLANT** | Selected crop (use AUTO). Installed version and thresholds: `grep -E '^(APP_VERSION\|MODEL_SHA256)' main.py`, `sha256sum agrilens.onnx`, and the start-up line `... rejection gates from ...: logit 2.10`. A kiosk still on 4.9.4 code often uses `ood_logit` 6.0. Thresholds: [`documentation/technical/CONFIGURATION.md`](documentation/technical/CONFIGURATION.md) |
| Status bar shows DEMO | Model file missing, unreadable, or its output width differs from `labels.txt` (reason on the console) |
| Webcam not found | `video` group, then **ADMIN → DETECT WEBCAM**; `v4l2-ctl --list-devices` |
| OTA reports "up to date" right after a push | GitHub's raw-file cache needs a few minutes; tap OTA again later |
| After an update the kiosk misbehaves | [`documentation/technical/ROLLBACK.md`](documentation/technical/ROLLBACK.md) |
| More device problems | Device guide, section "Troubleshooting" |

## Documentation index

<!-- agl:index:begin -->

**Current documentation**

| Document | Topic |
|---|---|
| [`README.md`](README.md) | Project overview, supported classes, repository layout |
| [`HOW_TO.md`](HOW_TO.md) | Central navigation guide (this file) |
| [`documentation/technical/INSTALLATION.md`](documentation/technical/INSTALLATION.md) | Installation: OTA, new Raspberry Pi 5, PC, offline |
| [`deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md`](deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md) | Device guide shipped to kiosks: running, touchscreen, camera panel, Admin, OTA, troubleshooting |
| [`documentation/technical/CONFIGURATION.md`](documentation/technical/CONFIGURATION.md) | Configuration files, keys, ranges and precedence; rejection thresholds |
| [`documentation/technical/ARCHITECTURE.md`](documentation/technical/ARCHITECTURE.md) | Architecture, version identifiers, inference path, OTA design, package build |
| [`documentation/technical/ROLLBACK.md`](documentation/technical/ROLLBACK.md) | Single-device and fleet rollback, repository rollback |
| [`documentation/technical/TRAINING.md`](documentation/technical/TRAINING.md) | Dataset, training, selection, calibration and release evaluation |
| [`documentation/technical/field_validation_protocol_phase_A.md`](documentation/technical/field_validation_protocol_phase_A.md) | Field (C270) accuracy validation protocol |
| [`datasets/master/AGL-MULTICROP-MD/DATASET_CARD.md`](datasets/master/AGL-MULTICROP-MD/DATASET_CARD.md) | Dataset card AGL-MULTICROP-MD 1.0.0 (structure, sources, licences) |
| [`documentation/release_notes/RELEASE_NOTES_5.4.0.md`](documentation/release_notes/RELEASE_NOTES_5.4.0.md) | Release notes 5.4.0: diagnosis history upload to OneDrive (rclone) |
| [`documentation/release_notes/RELEASE_NOTES_5.3.0.md`](documentation/release_notes/RELEASE_NOTES_5.3.0.md) | Release notes 5.3.0: diagnosis history (leaf images + log) |
| [`documentation/release_notes/RELEASE_NOTES_5.2.0.md`](documentation/release_notes/RELEASE_NOTES_5.2.0.md) | Release notes 5.2.0: model AGRILENS-MULTICROP 1.1.0 (webcam-robust), gate ood_logit 2.90 |
| [`documentation/release_notes/RELEASE_NOTES_5.1.0.md`](documentation/release_notes/RELEASE_NOTES_5.1.0.md) | Release notes 5.1.0: camera capture at 1280x720 with 640x480 fallback |
| [`documentation/release_notes/RELEASE_NOTES_5.0.0.md`](documentation/release_notes/RELEASE_NOTES_5.0.0.md) | Release notes 5.0.0: changes, evaluation, known limitations |
| [`documentation/CHANGE_REGISTER.md`](documentation/CHANGE_REGISTER.md) | Change register (all significant changes from 2026-11-17) |
| [`documentation/governance/ENGINEERING_GOVERNANCE.md`](documentation/governance/ENGINEERING_GOVERNANCE.md) | Versioning policy, hooks, quality checks, documentation rules |

**Release, evaluation and decision records (do not edit)**

| Document | Topic |
|---|---|
| [`training/evaluation/RELEASE_EVALUATION_CRITERIA.md`](training/evaluation/RELEASE_EVALUATION_CRITERIA.md) | Pre-declared release criteria C1-C9 |
| [`training/reports/agrilens-multicrop-1.0.0/EXPERIMENT_REGISTER.md`](training/reports/agrilens-multicrop-1.0.0/EXPERIMENT_REGISTER.md) | Training experiment register, AGRILENS-MULTICROP 1.0.0 |
| [`documentation/release_notes/AGRILENS_5.0.0_RELEASE_READINESS_REPORT.md`](documentation/release_notes/AGRILENS_5.0.0_RELEASE_READINESS_REPORT.md) | 5.0.0 release-readiness report (2026-11-17) |
| [`documentation/release_notes/C2_DEVIATION_EXHIBITION_ACCEPTANCE.md`](documentation/release_notes/C2_DEVIATION_EXHIBITION_ACCEPTANCE.md) | Recorded C2 (Mango) deviation acceptance |
| [`documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv`](documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv) | File-level change register of the 5.0.0 restructure |
| [`documentation/release_notes/REPOSITORY_CHANGE_LOG_5.0.0.csv`](documentation/release_notes/REPOSITORY_CHANGE_LOG_5.0.0.csv) | Repository change log of the 5.0.0 restructure |
| [`documentation/governance/DOCUMENTATION_AUDIT_2026-11-18.md`](documentation/governance/DOCUMENTATION_AUDIT_2026-11-18.md) | Documentation audit and KEEP/MERGE/ARCHIVE/DELETE register |

**History (superseded, kept for traceability)**

| Document | Topic |
|---|---|
| [`documentation/history/release_5.0.0/GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md`](documentation/history/release_5.0.0/GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md) | Planned 5.0.0 publication procedure (superseded; see the change register) |
| [`documentation/history/phase_A/phase_A.md`](documentation/history/phase_A/phase_A.md) | Phase A report: baseline and safeguards |
| [`documentation/history/phase_A/phase_A_git_integrity.md`](documentation/history/phase_A/phase_A_git_integrity.md) | Phase A git integrity report |
| [`documentation/history/phase_A/phase_A_test_results.txt`](documentation/history/phase_A/phase_A_test_results.txt) | Phase A test results |
| [`documentation/history/README_4.9.x.md`](documentation/history/README_4.9.x.md) | Project README of 4.9.x |
| [`documentation/history/REVISION_HISTORY_to_4.9.4.md`](documentation/history/REVISION_HISTORY_to_4.9.4.md) | Version history up to 4.9.4 |

**Generated**

| Document | Topic |
|---|---|
| [`AGRILENS_RaspberryPi/README_GENERATED.md`](AGRILENS_RaspberryPi/README_GENERATED.md) | Marker of the generated OTA publication folder |
<!-- agl:index:end -->
