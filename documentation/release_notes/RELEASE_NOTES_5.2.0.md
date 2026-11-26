# AGRILENS 5.2.0 release notes

| Item | Value |
|---|---|
| OTA release id | `AGRILENS-5.2.0` |
| Previous version | 5.1.0 |
| Increment | minor: Model AGRILENS-MULTICROP 1.1.0 (webcam-robust training; same 24 classes) with its own calibrated rejection gate ood_logit 2.90 |
| Model | AGRILENS-MULTICROP 1.1.0, SHA-256 `0774ca4aadab930086ade370234919a69cf35c8a22844355f78a20a194e0f08e` (10,067,999 bytes); previous: 1.0.0 `776d08ac…0332b` |
| Status | Published to GitHub `main` on 2026-11-19 at the owner's request (CR-0008). Not validated on a Raspberry Pi 5 with a Logitech C270 before publication. |

## What changes for a kiosk

- The kiosk downloads the new model file `agrilens.onnx` (about 10 MB) once, because `MODEL_SHA256` changed. The old model is kept in `rollback/v5.1.0/`.
- **Model AGRILENS-MULTICROP 1.1.0**: same MobileNetV4-Conv-Small architecture, same 24 classes in the same order, same dataset (AGL-MULTICROP-MD 1.0.0) as 1.0.0. Trained with webcam-style augmentation (colour cast, exposure, wash-out towards a bright background, sensor noise, low detail, motion blur, strong JPEG) so that live Logitech C270 captures look more like its training images. Diagnosis speed on the Raspberry Pi 5 is unchanged (same model size).
- **Rejection gate**: `ood_logit` 2.90 (1.0.0: 2.10), calibrated with the same rule on validation data (largest value with at most 3% false rejection of correct validation images in every crop and Mango source). Confidence 0.40 and margin 0.12 are unchanged.
- Rejection thresholds that were saved on a kiosk for model 1.0.0 (Admin sliders) are ignored after the update, because they were saved for another model; the kiosk uses the 1.1.0 calibration until the sliders are set again.
- No change to the user interface, camera handling (1280×720 with 640×480 fallback from 5.1.0), configuration keys or OTA.

## Tests

Comparison of 1.0.0 and 1.1.0 through the application's own six-view path, each with its own gates (`models/candidates/agrilens-multicrop-1.1.0/comparison/COMPARISON.md`):

| Set | Measure | 1.0.0 | 1.1.0 |
|---|---|---|---|
| test_known_device (3,595 images, all crops) | top-1 accuracy | 95.9% | 97.4% |
| | wrong diagnosis accepted | 3.2% | 1.9% |
| test_heldout_device (325 Mango images, unseen phones) | top-1 accuracy | 86.8% | 96.9% |
| | wrong diagnosis accepted | 12.0% | 1.9% |
| simulated C270 captures (3,844, derived from validation) | correct and accepted | 81.3% | 95.1% |
| | rejected as unknown | 9.6% | 2.1% |
| ood_v2 evaluation half (245 unsupported images) | accepted (lower is better) | 35.5% | 33.5% |

Mango per-class recall (test_known_device): Die Back 0.46 → 0.90, Anthracnose 0.96 → 1.00, Healthy 0.92 → 0.83; the others unchanged or within 0.03.
The 24 diagnosis samples: 24 of 24 top-1 correct (new golden baseline `tests/regression/baseline_5.2.0/`). Automated test suite and package checks: see `deployment/release_manifests/AGRILENS-5.2.0.json`.

## Known limitations

- **Not validated on the kiosk hardware.** Real Logitech C270 captures and the Raspberry Pi 5 were not tested before publication. The "simulated C270" figures come from degraded validation images that are related to the training augmentation, so they favour 1.1.0.
- No run-once release evaluation against criteria C1–C9 was made for 1.1.0; the figures above are a comparison with 1.0.0 on the same frozen test tiers.
- Mango Healthy recall dropped (0.92 → 0.83): some healthy Mango leaves may be given a disease.
- Unsupported inputs are still often accepted (33.5% of the unsupported-image set; Mango Turning Brown about 78%).
- Labels are source labels; none has been verified by an expert.
- **Rollback**: a single kiosk returns to 5.1.0 with `rollback.sh`. The prepared fleet rollback `AGRILENS-5.0.1-rollback` does not reach kiosks on 5.1.0 or later (downgrade); a fleet rollback needs a release above 5.2.0, for example 5.2.1 with model 1.0.0 and `MODEL_CALIBRATION_OOD_LOGIT = 2.10`.
- If GitHub's file cache still serves the 1.0.0 model for a few minutes after publication, a kiosk that updates in that window keeps the old model with generic thresholds until its next boot or Admin OTA; restart kiosks after about 5 minutes.
