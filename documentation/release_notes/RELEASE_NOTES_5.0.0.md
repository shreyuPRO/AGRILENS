# AGRILENS 5.0.0 release notes (published 2026-11-17)

| Item | Value |
|---|---|
| OTA release id | `AGRILENS-5.0.0` |
| Application | 5.0.0 (`main.py` SHA-256 `8f6c0378f0d12e57b5d35a0804392011f3a594c63ed19d0c0c001988c1b8ffc8`) |
| Model | `AGRILENS-MULTICROP` 1.0.0, `agrilens.onnx` SHA-256 `776d08ac669d0ea8874a458bfb6ea2657c5d40525d30021c7c8c1204d520332b`, 10,067,999 bytes |
| Dataset | `AGL-MULTICROP-MD` 1.0.0 (freeze file SHA-256 `12449a5caf1bfc736a9be1a83fa71f603b29045b48eaa7db82b0bffd2e5f8c0a`) |
| Gates | confidence 0.40, margin 0.12, ood_logit 2.10 (calibrated on validation for this model) |
| Release record | `deployment/release_manifests/AGRILENS-5.0.0.json` |
| Status | Released software (accepted with a recorded deviation). **One pre-declared release criterion failed (C2, Mango).** Not validated on the Raspberry Pi, with the C270 camera, or by an agronomic expert. **Published to GitHub `main` on 2026-11-17 and delivered to kiosks by OTA** (change register `CR-0001`); retained as the active release by the project owner on 2026-11-18. |

## What changes for a kiosk

- New model trained on one consolidated four-crop dataset that adds 2,424 SAR-MLD1-2025 and 712 ABCGMP Mango images from phones the 4.9.4 model never saw. Same 24 classes in the same order, same architecture and input size, same file size.
- The rejection gates are now tied to the model file. Thresholds saved under 4.9.4 (for example `ood_logit` 6.0 on calibrated devices) are no longer applied to the new model; the model's own calibration is used until an operator saves new settings. Saved settings now record the model's SHA-256.
- If the model output width does not match `labels.txt`, the app runs in DEMO mode instead of showing wrong class names. An unrecognised model file is reported as such and gets generic thresholds.
- OTA: the downloaded `main.py` is compiled before anything is replaced (the model was previously replaced first); every replaced file is kept in `rollback/v<version>/`; new `rollback.sh`; `~/.agrilens_ota_hold` pauses automatic updates. Downgrade protection and SHA-256 model verification are unchanged.
- Version, model and dataset are shown in the brand-label tooltip and on the start-up console line.
- No change to the user interface flow, Hindi/English text, camera panel, crop box, Admin sliders or the file list fetched from GitHub.

## Evaluation (single run, frozen inputs, application's six-view path)

Desktop CPU only. Held-out-device = phones never seen in training.

| Measure | 5.0.0 model | 4.9.4 model, same path |
|---|---|---|
| Known-device test (3,595 images), accuracy / macro-F1 | 0.959 / 0.927 | 0.927 / 0.895 |
| Held-out-device test (325 SAR images), accuracy | 0.868 | 0.058 |
| SAR + ABCGMP images (690, not in 4.9.4 training), accuracy | 0.912 | 0.322 (difference +0.590, 95% CI 0.512 to 0.661) |
| Cross-crop confusions, known / held-out | 6 / 0 | 106 / 81 |
| False rejection of correct answers, known / held-out | 0.7% / 5.3% | 2.0% / 78.9% at the device setting 6.0 |
| Non-leaf images accepted (165) | 13.3% | |

The 4.9.4 model was most probably trained on the MangoLeafBD, PlantVillage and Plant Pathology 2020 images, so its known-device figures are favoured (it scores 1.000 on the MangoLeafBD and Plant Pathology test images). The SAR + ABCGMP row is the fair comparison.

| Criterion | Limit | Result | Verdict |
|---|---|---|---|
| C1 known-device macro-F1 | ≥ 0.90 | 0.927 | pass |
| C2 per-crop macro-F1 | ≥ 0.85 each | Apple 0.945, **Mango 0.849**, Potato 0.997, Tomato 0.966 | **FAIL** |
| C3 held-out Anthracnose recall | ≥ 0.80 | 0.869 | pass |
| C4 unseen-by-production accuracy difference | ≥ 0 | +0.590 | pass |
| C5 false rejection per crop, known-device | ≤ 5% | max 3.0% (Mango) | pass |
| C6 false rejection, held-out | ≤ 10% | 5.3% (95% CI 3.2 to 8.6%) | pass |
| C7 decision recall vs classification recall | within 0.10 | worst Die Back 0.365 vs 0.462 (0.096) | pass |
| C8 non-leaf accepted | ≤ 35% | 13.3% | pass |
| C9 ONNX parity | ≤ 1e-3, 100% | 1.2e-5, 100% | pass |

## Known limitations

- **C2 failed.** Mango macro-F1 on known devices is 0.849. Causes: Mango Die Back recall 0.462 (24 of 52 MangoLeafBD/HUAWEI test images; 20 predicted as Powdery Mildew, 7 as Gall Midge) and Mango Gall Midge F1 0.381 (only 4 test images; 13 false positives). Validation Die Back recall was 0.827, so this weakness did not show before the test.
- Mango Gall Midge is a provisional class (MangoLeafBD labels only). Mango Turning Brown is not a model class; 81% of Turning Brown leaves are accepted and given a diagnosis.
- 33% of background-only windows receive a diagnosis.
- Apple, Potato and Tomato come from one source each (Plant Pathology 2020, PlantVillage), mostly laboratory photographs without device information. No field performance figures exist for those crops.
- No Raspberry Pi 5 benchmark, no C270 field data, no expert label review. Desktop latency (median 22.5 ms per diagnosis, same as 4.9.4) is not a Pi figure.
- Labels from public datasets have not been verified by an agronomist.
- Kiosks updating from 4.9.4 run the 4.9.4 updater for this first update; it does not keep a rollback copy (see `documentation/technical/ROLLBACK.md`).

## Exhibition acceptance (added 2026-11-17)

The project owner accepted this release for the EXPISCOR 2026 school exhibition with the C2 deviation recorded in `C2_DEVIATION_EXHIBITION_ACCEPTANCE.md`. The evaluation results and criteria above are unchanged. Exhibition installation is side by side with 4.9.4 using `deployment/exhibition/` (see `EXHIBITION_READINESS_REPORT_5.0.0.md`). At the time of that acceptance it was not published.

## Publication and retention (2026-11-17, 2026-11-18)

- 2026-11-17: `release/agrilens-5.0.0` (commit `9017320`) was pushed to GitHub `main` as a fast-forward from `01059f8` (4.9.4), with the owner's approval. The planned procedure (`documentation/history/release_5.0.0/GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md`, publisher script, tag `AGRILENS-5.0.0`) was not used; no tag exists. Details and checks: `documentation/CHANGE_REGISTER.md`, `CR-0001`.
- GitHub's raw-file cache served the 4.9.4 `main.py` for about 4 to 5 minutes after the push. A kiosk that checked in that window reported "up to date" and updates on its next check.
- Kiosks update on their next boot, kiosk start or Admin OTA tap; a kiosk that stays on does not update by itself.
- 2026-11-18: the project owner decided to retain 5.0.0 on `main`: no rollback to 4.9.4, no publication of the rollback release 5.0.1, no retraining, no change to the release criteria. Priority: Raspberry Pi 5 and Logitech C270 validation, monitoring of OTA installation and stability.
- **Exhibition kit procedures are affected.** `deployment/exhibition/README_KIT.md` and `pi_restore_previous.sh` were written while `main` served 4.9.4. Since 2026-11-17 a kiosk that is restored to 4.9.4 and has internet access updates itself to 5.0.0 on its next boot (the 4.9.4 updater ignores `~/.agrilens_ota_hold`). Keep such a kiosk offline if it must stay on 4.9.4.
- 2026-11-18: at the project owner's request the exhibition kit was discarded (CR-0005): `deployment/exhibition/`, `tests/integration/test_exhibition_kit.py`, `tools/validation/exhibition_desktop_check.py`, `documentation/exhibition/` and `EXHIBITION_READINESS_REPORT_5.0.0.md` were deleted. The paragraphs above that name them are historical; the files remain only in git history (release commit `9017320`). The C2 deviation record is kept.

## Field observations (not validated results)

- 2026-11-18, exhibition hardware: a Mango leaf with dried tips, captured with the C270 and cropped on the touchscreen, was rejected as **UNKNOWN PLANT / OUT OF SCOPE**. The cause has not been established. Not yet confirmed on that kiosk: installed version and model hash, the rejection thresholds it used, and the selected crop. On the desktop, the 8 Mango sample images (also placed on a wide light background) were classified correctly with maximum logits 4.1 to 5.7, above the 5.0.0 gate of 2.10 and below the 4.9.4 device setting of 6.0. This is a single report, not an accuracy figure.
