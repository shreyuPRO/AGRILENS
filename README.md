# AGRILENS: plant health and disease diagnosis kiosk

| Item | Value |
|---|---|
| Application | AGRILENS **<!-- agl:version -->5.4.0<!-- /agl:version -->** (published to GitHub `main` on 2026-11-17 and delivered by OTA; Raspberry Pi 5 / Logitech C270 validation pending) |
| OTA release id | `AGRILENS-5.0.0` |
| Model | `AGRILENS-MULTICROP` **1.0.0**, MobileNetV4-Conv-Small, single-file ONNX (~10 MB), 24 classes |
| Dataset | `AGL-MULTICROP-MD` **1.0.0** (frozen master dataset, stored outside the repository) |
| Previous production release | 4.9.4 (model SHA-256 `0b5bb7fb…2ff80`, kept in `models/production/agrilens-24class-4.9.4/`) |
| Target hardware | Raspberry Pi 5 + Waveshare 7" touch display (1024×600) + USB webcam (Logitech C270); Windows/Linux PC for development |
| Partner | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |

AGRILENS is an offline Tkinter touch kiosk. A farmer photographs a leaf (or picks a file), adjusts the crop box and taps **DIAGNOSE NOW**. The ONNX model runs a six-view logit ensemble, and three rejection gates (confidence, top-2 margin, maximum logit) refuse images the model should not answer. The main screen is bilingual (English / Hindi). Release status, test results and known limitations are in [`documentation/release_notes/RELEASE_NOTES_5.0.0.md`](documentation/release_notes/RELEASE_NOTES_5.0.0.md); every significant change is listed in [`documentation/CHANGE_REGISTER.md`](documentation/CHANGE_REGISTER.md).

## Supported classes (24, unchanged from 4.9.4, same order as `labels.txt`)

| Crop | Classes |
|---|---|
| Apple | Rust, Scab, healthy |
| Mango | Anthracnose, Bacterial Canker, Cutting Weevil, Die Back, Gall Midge, Healthy, Powdery Mildew, Sooty Mould |
| Potato | Early blight, Late blight, healthy |
| Tomato | Bacterial spot, Early blight, Late blight, Leaf Mold, Septoria leaf spot, Spider mites, Target Spot, Yellow Leaf Curl Virus, mosaic virus, healthy |

Mango Turning Brown (taxonomy id MNG009) is in the dataset taxonomy but quarantined pending expert review and is not a model class.

## Repository layout

```text
application/            the ONE authoritative application source (main.py, requirements, logos, samples, default config)
models/                 production/ (4.9.4 model, preserved), candidates/ (release model 1.0.0, Mango candidate pointer), manifests/MODEL_REGISTRY.json
datasets/               master/AGL-MULTICROP-MD/ (manifests and card of the training set; images live with the trainer)
training/               evaluation/ (gate calibration, release evaluation), reports/ (release evidence of model 1.0.0)
                        The trainer itself is the separate Model Trainer Program (..\Model_Trainer_Program), never installed on a kiosk.
deployment/             ota/ (updater, publisher), raspberry_pi/ (setup, run, rollback, guide), packaging/ (package builders), rollback/ (prepared 5.0.1 rollback release)
documentation/          technical/, release_notes/, history/, hardware/
tests/                  unit/, integration/, regression/ (with the 4.9.4 baseline)
tools/                  governance/ (quality gate, hooks), migration/, validation/, development/
archive/                retired tools and the legacy MobileNetV2 experiment
AGRILENS_RaspberryPi/   GENERATED OTA publication folder read by deployed kiosks. Do not edit; build it with deployment/packaging/build_device_package.py
```

`AGRILENS_RaspberryPi/` stays at this path because every deployed kiosk downloads a fixed file list from `https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi/`. See [`documentation/technical/ARCHITECTURE.md`](documentation/technical/ARCHITECTURE.md).

## Quick start

Windows / Linux PC (development). The runnable build is the generated folder, which holds `main.py` together with its model and labels:

```bash
pip install -r application/requirements.txt
python deployment/packaging/build_device_package.py --model-dir models/candidates/agrilens-multicrop-1.0.0
python AGRILENS_RaspberryPi/main.py
```

On Windows with Python 3.13 you can double-click `tools/development/run_agrilens_windows_py313.bat`. Running `application/main.py` directly starts in DEMO mode because no model sits next to it.

Raspberry Pi 5: see [`documentation/technical/INSTALLATION.md`](documentation/technical/INSTALLATION.md) and `AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md`.

## Documentation

Start with [`HOW_TO.md`](HOW_TO.md): it is the navigation guide (installation, running, camera, diagnosis, configuration, model, training, OTA, rollback, troubleshooting) and holds the checked index of every document. Engineering rules (versioning, hooks, quality gate, change register): [`documentation/governance/ENGINEERING_GOVERNANCE.md`](documentation/governance/ENGINEERING_GOVERNANCE.md).

## Disclaimer

Diagnoses are advisory. The model has not been validated in the field, on the Raspberry Pi, or by an agronomic expert (see the release notes). Consult a local agricultural extension officer before applying any treatment.
