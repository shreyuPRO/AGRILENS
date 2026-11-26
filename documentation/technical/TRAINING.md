# Model training, hand-over and evaluation (AGRILENS-MULTICROP 1.0.0)

## The trainer is a separate program

Model training is not part of this repository and never runs on a kiosk. Since 2026-11-18 (CR-0006) the trainer, its run configurations,
the dataset tools and the training experiments live in the separate **Model Trainer Program**:

`<AGRILENS_5.0.0>\Model_Trainer_Program\` (guide: `Model_Trainer_Program\README.md`)

| There | Content |
|---|---|
| `trainer\scripts\` | `train_integrated.py`, `agl_common.py`, `prepare_cache.py`, `export_onnx.py`, `report_runs.py` |
| `trainer\configurations\` | `multicrop1_*.yaml` (paths relative to `Model_Trainer_Program`), `make_configs.py`, `SELECTION_RULE.md`, `kiosk_labels_24class.txt` |
| `trainer\dataset_tools\` | Builders and freeze/verify tools of AGL-MANGO-MD and AGL-MULTICROP-MD |
| `trainer\experiments\`, `trainer\legacy_4.9.4\` | Earlier experiments and the 4.9.4 training code (history) |
| `datasets\`, `training_cache\`, `training_runs\`, `exports\` | Frozen datasets, image cache, training output, ONNX exports |

The trainer has its own Python environment (`Model_Trainer_Program\.venv_train`, pinned in
`trainer\requirements-train-lock.txt`) and needs nothing from this repository. It is its own git repository (code, configurations and records only; datasets, images, caches, checkpoints and environments are excluded by its `.gitignore`); on GitHub it is the private repository https://github.com/faiyaze04/AGRILENS-Model-Trainer. The history of these files up to the move is in this
repository's git history (former folders training/scripts, training/configurations, training/experiments, training/legacy_4.9.4 and
datasets/dataset_tools, removed in CR-0006).

## Master dataset

`AGL-MULTICROP-MD 1.0.0` is the training set of the kiosk model, stored with the trainer at
`<AGRILENS_5.0.0>\Model_Trainer_Program\datasets\AGL-MULTICROP-MD\AGL-MULTICROP-MD-1.0.0` (29,982 files listed in `FREEZE_CHECKSUMS.sha256`,
freeze-file SHA-256 `12449a5c…5f8c0a`). Its manifests and card are mirrored in `datasets/master/AGL-MULTICROP-MD/` here. Splits are by leaf
group, copy group and split unit, with no group in two splits. `test_heldout_device` holds Mango Anthracnose images from phones that do not
appear in train or val.

## Hand-over of a trained model to the kiosk

1. In the trainer: export with a new model version (`export_onnx.py --model-version 1.1.0`). The export checks that the class order equals the
   kiosk's `labels.txt` and that ONNX and PyTorch agree on 256 validation images.
2. Copy the export folder (`agrilens.onnx`, `labels.txt`, `MODEL_MANIFEST.json`) to `models/candidates/<model-id>/` and add an entry to
   `models/manifests/MODEL_REGISTRY.json`. Released model files are never overwritten.
3. Calibrate the rejection gates and run the release evaluation below with the candidate, then decide on a kiosk release. A kiosk only gets
   a new model through a published release (`MODEL_SHA256` in `main.py` and a rebuilt `AGRILENS_RaspberryPi/`).

## AGRILENS-MULTICROP 1.1.0 (2026-11-19, CR-0007; released in AGRILENS 5.2.0, CR-0008)

Trained overnight on the laptop CPU by the Model Trainer Program (`trainer\run_candidate_1_1_0.ps1`). Same architecture, dataset, 24 classes
and class order as 1.0.0, so Raspberry Pi speed is unchanged. Three runs: webcam-style augmentation (colour cast, exposure, wash-out, noise,
low detail, motion blur, stronger JPEG) with full fine-tuning (seeds 42, 43) and with the 1.0.0 recipe R2 (seed 42). Selected on validation:
`multicrop11_R2w_s42` (validation macro-F1 0.9768 vs 0.9643 for 1.0.0); full fine-tuning scored lower (0.9705, 0.9605).

Files: `models/candidates/agrilens-multicrop-1.1.0/` (SHA-256 `0774ca4a…e0f08e`), with `calibration/FROZEN_GATE_CALIBRATION.json`
(confidence 0.40, margin 0.12, **ood_logit 2.90**, same rule as 1.0.0) and `comparison/COMPARISON.md`.

Comparison with 1.0.0 through the application's six-view path (`training/evaluation/compare_models.py`, each model with its own gates):

| Set | Measure | 1.0.0 | 1.1.0 |
|---|---|---|---|
| test_known_device (3,595) | top-1 accuracy / wrong but accepted | 95.9% / 3.2% | 97.4% / 1.9% |
| test_heldout_device (325, Mango) | top-1 accuracy / wrong but accepted | 86.8% / 12.0% | 96.9% / 1.9% |
| simulated C270 captures (3,844) | correct and accepted / rejected unknown | 81.3% / 9.6% | 95.1% / 2.1% |
| ood_v2 evaluation half (245) | accepted (lower is better) | 35.5% | 33.5% |

Mango Die Back recall (test_known_device) 0.46 → 0.90; Mango Healthy 0.92 → 0.83. The simulated C270 set is related to the candidate's
training augmentation and favours it. The frozen 1.0.0 release evaluation (run-once lock) was not re-run. Not yet checked: real C270 captures
and the Raspberry Pi 5. AGRILENS 5.2.0 ships it (`MODEL_SHA256`, `MODEL_CALIBRATION_OOD_LOGIT = 2.90`).

## Selection and calibration (pre-declared)

`SELECTION_RULE.md` (now in `Model_Trainer_Program\trainer\configurations\`) was written before training; selection uses validation only.
Gate calibration (`training/evaluation/calibrate_gates.py`, in this repository) uses validation images and the calibration half of the
unsupported-image set `ood_v2`, through the application's own six-view path, and freezes the thresholds before any test tier is read.

## Release evaluation

`training/evaluation/RELEASE_EVALUATION_CRITERIA.md` (criteria C1–C9) was written before the test tiers were read.
`training/evaluation/evaluate_release.py` runs once (lock file `RELEASE_EVALUATION_RUN_ONCE.json`) on `test_known_device`,
`test_heldout_device` and the `ood_v2` evaluation half, for the release model and the 4.9.4 model through the release application's code.
Tiers are reported separately and never pooled. `--smoke` exercises the code on a few validation images without reading any test tier.
These scripts stay in this repository because they run the kiosk's `main.py` and because the release tooling reads their frozen results.

Results: `training/reports/agrilens-multicrop-1.0.0/` and `training/evaluation/release_eval_1.0.0/`.
