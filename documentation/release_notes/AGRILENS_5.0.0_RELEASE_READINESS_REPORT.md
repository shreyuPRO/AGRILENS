# AGRILENS 5.0.0: execution and release-readiness report

Date 2026-11-17. Work location: release clone `D:\AGRILENS_Training\release_5.0.0\AGRILENS`, branch `release/agrilens-5.0.0` (push disabled). Nothing was pushed, published or deployed, and no Raspberry Pi was touched.

**Summary.** The software release candidate is complete and all 145 automated tests pass. The integrated model clearly beats 4.9.4 on images 4.9.4 was not trained on (accuracy 0.912 against 0.322) and passes 8 of the 9 pre-declared release criteria. It **fails C2**: Mango macro-F1 on known devices is 0.849 against a limit of 0.85, caused by Mango Die Back (recall 0.46). Raspberry Pi, C270 and expert validation are still pending. Publication therefore needs your decision on C2.

## Preservation checks (run at the end of this session)

| Check | Result |
|---|---|
| Original working tree | still 12 uncommitted entries, HEAD `585698f` on `restructure/v5`; all 106 files listed in `baseline_4.9.4\working_tree_SHA256SUMS.txt` match |
| Production 4.9.4 files | `main.py` `b600d71c…3deb`, `agrilens.onnx` `0b5bb7fb…2ff80`, labels `5087b575…d393` unchanged (original tree); byte copies in `models/production/agrilens-24class-4.9.4/` and `tests/regression/baseline/legacy_4.9.4/` |
| Mango candidate `mango5_exp001_B_partial_ft_s43_v1` | 48 of 48 files match `CANDIDATE_CHECKSUMS.sha256` |
| AGL-MULTICROP-MD 1.0.0 | 29,982 of 29,982 files match `FREEZE_CHECKSUMS.sha256`; no unlisted files |
| Full history backup | `baseline_4.9.4\AGRILENS_all_refs.bundle` |

## A. Repository

### Structure before and after

| 4.9.4 / Phase A (`585698f`) | 5.0.0 |
|---|---|
| `MobileV4/` (app copy 1, model, training scripts) | `application/` (single app source), `models/production/agrilens-24class-4.9.4/`, `training/legacy_4.9.4/` |
| `AGRILENS_RaspberryPi/` (app copy 2, hand-maintained) | `AGRILENS_RaspberryPi/` kept at the same path as a **generated** OTA folder (`deployment/packaging/build_device_package.py`) |
| `Documentation_and_References/`, `docs/` | `documentation/{history,hardware,technical,release_notes}/` |
| `scripts/` | `tools/{validation,migration,development}/` |
| `tests/` (flat) | `tests/{unit,integration,regression}/` |
| `logos/` (duplicate) | removed (identical to `application/logos/`) |
| `push_ota_update.bat` (`git add -A` + push) | archived; replaced by `deployment/ota/publish_ota_release.ps1` |
| none | `datasets/` (tools + master manifests), `training/` (scripts, configs, evaluation, experiments, reports), `deployment/` (ota, raspberry_pi, packaging, rollback, release_manifests), `models/manifests/MODEL_REGISTRY.json`, `archive/` |

### Change register

`documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv` is generated from git (`tools/migration/write_change_register.py`) and lists every changed path. `REPOSITORY_CHANGE_LOG_5.0.0.csv` records the reason for each action. Counts against `phase-A` (245 paths): 164 added, 68 moved, 3 archived, 9 modified, 1 deleted (the old Windows launcher; git sees it as deleted because the rewritten launcher is under 50% similar). Git classifies identical duplicates removed from `MobileV4/` and `logos/` as moves of the surviving copy. No file needed by the OTA mechanism was removed.

Fixed this session:

- The restructure step had copied the device guide and the default `kiosk_config.json` through a PowerShell pipe. The guide was mangled (mojibake) and both files gained a BOM; with the BOM, the app's `json.load` would have rejected the default config. Both are now byte-exact from git, the restructure script is corrected, and the rollback release was rebuilt.
- The Windows launcher pointed at a `main.py` that no longer existed next to it.
- The package manifest contained a generation time, so the publisher's "rebuild equals committed folder" check could never pass. The build is now byte-reproducible (verified).

### Remaining technical debt

- `application/main.py` is still one 4,600-line file. Splitting it is blocked until every kiosk runs a 5.0.0+ updater (4.9.x updaters fetch only `main.py`).
- The release model sits in `models/candidates/` until approval; promotion to `models/production/` is a follow-up commit.
- Research and dataset-build scripts are in a compact style. Ruff waives only style and unused-import codes there, to keep them byte-identical to the code that produced the frozen data.
- Hardware CAD/STL files were deleted (uncommitted) in the original tree; they are kept in `documentation/hardware/` until you decide.
- The Read-only ACL protection of the dataset was blocked by tool policy. Protection is the freeze checksums plus a builder that refuses to write into a frozen release.

## B. Dataset: AGL-MULTICROP-MD 1.0.0

One master dataset at `D:\AGRILENS_Training\datasets\AGL-MULTICROP-MD\AGL-MULTICROP-MD-1.0.0`. Training reads it only through its versioned split and manifest files and checks them against the freeze file first. No training copy exists; the `.npy` cache is disposable. Full verification output: `training/reports/agrilens-multicrop-1.0.0/DATASET_VERIFICATION.json` (`datasets/dataset_tools/verify_agl_multicrop_md.py`, read-only).

**Missing Apple source path.** The extracted `AgriLens\datasets` folder used in earlier work no longer exists, so the first build failed on `apple dataset\rust\Train_10.jpg`. Apple, Potato and Tomato were re-extracted from the original `AgriLens\Datasets.zip` (SHA-256 `87a22c46…e977`) and every one of 19,893 files was verified against its recorded hash (0 mismatches). No image was substituted or invented.

| Status (44,612 records) | Records | Notes |
|---|---|---|
| accepted (in splits) | 26,917 | Apple 1,730, Mango 7,038, Potato 2,152, Tomato 15,997 |
| accepted, excluded from splits | 412 | Mango |
| supplementary | 430 | background-removed Mango originals, not used for training |
| quarantined | 2,205 | Turning Brown 1,000; SAR "Golmichi"→Gall Midge 921; label doubt, blur, small leaf 284 |
| rejected | 1,919 | 1,811 background-removed derivatives of MangoLeafBD originals, 16 no visible leaf, 14 Tomato and 76 Mango exact duplicates, 2 defocused |
| excluded augmented | 12,729 | augmented copies in the legacy Mango compilation |

Origin of accepted images: 24,206 original photographs, 1,696 likely original, 1,015 likely derivative (kept with their parent in the same copy group). Exact duplicates among kept images: 0.

Class counts (accepted images / leaf groups): APL001 Rust 622/616, APL002 Scab 592/592, APL003 healthy 516/504; MNG001 Anthracnose 1,357/1,223, MNG002 Bacterial Canker 884/580, MNG003 Cutting Weevil 500/202, MNG004 Die Back 448/321, MNG005 Gall Midge 500/393 (provisional), MNG006 Healthy 1,597/906, MNG007 Powdery Mildew 1,252/617, MNG008 Sooty Mould 500/376, MNG009 Turning Brown 0 (1,000 quarantined, not a model class); POT001 Early blight 1,000/248, POT002 Late blight 1,000/249, POT003 healthy 152/38; TOM001 Bacterial spot 2,127/505, TOM002 Early blight 1,000/251, TOM003 Late blight 1,901/1,188, TOM004 Leaf Mold 952/238, TOM005 Septoria 1,771/1,018, TOM006 Spider mites 1,676/401, TOM007 Target Spot 1,404/1,402, TOM008 YLCV 3,208/2,218, TOM009 mosaic 373/370, TOM010 healthy 1,585/819.

| Split | Images | Apple | Mango | Potato | Tomato |
|---|---|---|---|---|---|
| train | 19,153 | 1,211 | 5,244 | 1,504 | 11,194 |
| val | 3,844 | 260 | 852 | 328 | 2,404 |
| test_known_device | 3,595 | 259 | 617 | 320 | 2,399 |
| test_heldout_device | 325 | 0 | 325 (321 Anthracnose, 4 Powdery Mildew) | 0 | 0 |

| Integrity and isolation check | Result |
|---|---|
| Freeze file entries / missing or changed / unlisted | 29,982 / 0 / 0 |
| Manifest SHA-256 vs freeze file (29,964 images) | 0 mismatches |
| Split rows not in manifest, not accepted, in two splits, accepted but unsplit | 0 / 0 / 0 / 0 |
| Leaf groups (15,275) in more than one split | 0 |
| Copy (derivative / burst) groups (25,720) in more than one split | 0 |
| Split units (11,220) in more than one split | 0 |
| Identical SHA-256 across splits | 0 |
| Split images missing a provenance field | 0 |

For information: 74 of 518 capture sessions have images in both train and test. Sessions are not a split unit; leaf and copy groups are.

Provenance by source (accepted): PlantVillage 18,149 (CC BY-SA 3.0), MangoLeafBD 3,902 (CC BY-NC 3.0, non-commercial), SAR-MLD1-2025 2,424 (CC BY 4.0), Plant Pathology 2020 1,730 (terms not verified), ABCGMP 712 (CC BY 4.0 per v2 record). Source archives and their hashes: `datasets/master/AGL-MULTICROP-MD/source_archives.json`.

Correction to an earlier statement: the held-out-device tier is not Anthracnose-only. It also holds 4 Powdery Mildew images. The release criteria text repeats the earlier wording; C3 uses Anthracnose only, and C6 uses all 325 images.

## C. Model: AGRILENS-MULTICROP 1.0.0

Architecture: MobileNetV4-Conv-Small (`timm mobilenetv4_conv_small.e2400_r224_in1k`, ImageNet-1k start), 24-class head, 224×224. It was chosen because it is the production architecture: it runs on the Pi with onnxruntime, exports to a 10 MB single file, and the path is proven. One integrated model was trained; no weights were merged and no other architecture was tried. The configuration was the same for all runs: class → leaf group → image uniform sampling, 12,000 samples per epoch, AdamW (head 1e-3, backbone 3e-4), label smoothing 0.06, batch 32, at most 15 epochs, patience 3, CPU only. Dataset AGL-MULTICROP-MD 1.0.0, `splits/train.csv` `5a319ea1…`, `splits/val.csv` `87e31281…`.

### The four runs (validation only)

| Run | Trainable layers | Seed | Params | Epochs (best) | Minutes | Train loss | Val loss | Val acc | Val macro-F1 | ONNX bytes | ONNX max diff / argmax |
|---|---|---|---|---|---|---|---|---|---|---|---|
| multicrop1_R1_s42 | blocks.4 + head | 42 | 1,386,904 | 15 (14) | 20.3 | 0.515 | 0.188 | 0.9631 | 0.9627 | 10,067,999 | 1.9e-5 / 100% |
| **multicrop1_R2_s42** | blocks.3–4 + head | 42 | 2,206,200 | 7 (4) | 16.4 | 0.545 | 0.168 | 0.9659 | **0.9643** | 10,067,999 | 1.2e-5 / 100% |
| multicrop1_R1_s43 | blocks.4 + head | 43 | 1,386,904 | 11 (8) | 15.6 | 0.594 | 0.241 | 0.9527 | 0.9499 | 10,067,999 | 1.8e-5 / 100% |
| multicrop1_R2_s43 | blocks.3–4 + head | 43 | 2,206,200 | 8 (5) | 18.5 | 0.521 | 0.170 | 0.9636 | 0.9635 | 10,067,999 | 1.3e-5 / 100% |

Per-class validation precision, recall and F1 and the four confusion matrices are in `training/reports/agrilens-multicrop-1.0.0/EXPERIMENT_REGISTER.md` (data: `TRAINING_RUNS.json`). Each run was exported and passed the parity check on 256 validation images.

**Selection** (rule written before training): mean validation macro-F1 R1 0.9563, R2 0.9639 (+0.0075 ≥ 0.005), so R2 was chosen, and within R2 the better seed, **multicrop1_R2_s42** (`SELECTION.json`). No test data was used.

**Release model:** `models/candidates/agrilens-multicrop-1.0.0/agrilens.onnx`, SHA-256 `776d08ac669d0ea8874a458bfb6ea2657c5d40525d30021c7c8c1204d520332b`, 10,067,999 bytes, opset 17. Parity with PyTorch: max logit difference 1.2e-5, argmax agreement 100% (C9). The export is reproducible: re-exporting gives the same SHA-256. Class order is identical to 4.9.4 `labels.txt`.

**Gate calibration** (validation and the ood_v2 calibration half only, through the app's six-view path; rule written before training): the largest `ood_logit` with false rejection ≤ 3% in every crop and in every Mango source with ≥ 50 validation images is **2.10**. The worst group is MangoLeafBD at 2.8%; the pooled figure is 0.5%. Confidence stays 0.40 and margin 0.12. The 4.9.4 values (6.0 on devices, 1.40 in code) and the Mango candidate's 1.5 were not reused. The result was frozen in `training/evaluation/calibration_1.0.0/FROZEN_GATE_CALIBRATION.json` (`d8df659c…`) before any test tier was read.

### Release evaluation (run once, lock `RELEASE_EVALUATION_RUN_ONCE.json`)

Inputs were hash-checked; a smoke run on validation data checked the code first. The application's own decision code agreed with the evaluation's on 300 of 300 images. Tiers are not pooled. Results: `training/evaluation/release_eval_1.0.0/`.

| Criterion | Limit | Result | Verdict |
|---|---|---|---|
| C1 known-device macro-F1 | ≥ 0.90 | 0.927 | pass |
| C2 per-crop macro-F1 | ≥ 0.85 each | Apple 0.945, **Mango 0.849**, Potato 0.997, Tomato 0.966 | **FAIL** |
| C3 held-out Anthracnose recall | ≥ 0.80 | 0.869 | pass |
| C4 accuracy minus 4.9.4 on images 4.9.4 did not train on (690) | ≥ 0 | +0.590 (95% CI 0.512 to 0.661) | pass |
| C5 false rejection per crop, known-device | ≤ 5% | Apple 0%, Mango 3.0%, Potato 0%, Tomato 0.3% | pass |
| C6 false rejection, held-out-device | ≤ 10% | 5.3% (3.2 to 8.6%) | pass |
| C7 decision recall ≥ classification recall − 0.10 | every class | worst: Die Back 0.365 against 0.462 (gap 0.096) | pass |
| C8 non-leaf accepted | ≤ 35% | 13.3% (22 of 165) | pass |
| C9 ONNX parity | ≤ 1e-3, 100% | 1.2e-5, 100% | pass |

### Comparison with AGRILENS 4.9.4 (same images, same six-view path)

| | 5.0.0 | 4.9.4 |
|---|---|---|
| Known-device accuracy / macro-F1 | 0.959 / 0.927 | 0.927 / 0.895 |
| Held-out-device accuracy | 0.868 | 0.058 |
| SAR25 known-device accuracy (337) | 0.947 | 0.519 |
| MangoLeafBD / Plant Pathology / PlantVillage known-device accuracy | 0.865 / 0.946 / 0.969 | 1.000 / 1.000 / 0.964 |
| Cross-crop confusions, known / held-out | 6 / 0 | 106 / 81 |
| Accuracy among accepted answers, known / held-out | 0.967 / 0.873 | not computed |
| False rejection, known / held-out | 0.7% / 5.3% | 2.0% / 78.9% at device setting 6.0; 0.3% / 21.1% at code default 1.4 |
| Unsupported images accepted: background / photos / synthetic / Turning Brown | 33% / 8% / 3% / 81% | 0% / 2% / 2% / 26% at 6.0; 4% / 42% / 33% / 96% at 1.4 |
| Desktop latency, median per diagnosis (24 samples × 50) | 22.5 ms | 21.6 ms |

The 4.9.4 model scores 1.000 on the MangoLeafBD and Plant Pathology test images and was most probably trained on them. Its figures on those sources are inflated, which is why C4 uses only SAR and ABCGMP images.

Per-class known-device test results, release model (P / R / F1), with the 4.9.4 F1 in brackets:

| Class | n | P / R / F1 (4.9.4 F1) | Class | n | P / R / F1 (4.9.4 F1) |
|---|---|---|---|---|---|
| Apple Rust | 93 | 0.978 / 0.978 / 0.978 (0.954) | Potato Early blight | 148 | 1.000 / 0.980 / 0.990 (1.000) |
| Apple Scab | 89 | 0.963 / 0.888 / 0.924 (0.983) | Potato Late blight | 148 | 1.000 / 1.000 / 1.000 (0.990) |
| Apple healthy | 77 | 0.862 / 0.974 / 0.915 (0.987) | Potato healthy | 24 | 1.000 / 1.000 / 1.000 (1.000) |
| Mango Anthracnose | 145 | 0.927 / 0.959 / 0.942 (0.626) | Tomato Bacterial spot | 319 | 0.948 / 0.966 / 0.957 (0.968) |
| Mango Bacterial Canker | 29 | 1.000 / 1.000 / 1.000 (0.690) | Tomato Early blight | 149 | 0.964 / 0.886 / 0.923 (0.914) |
| Mango Cutting Weevil | 36 | 1.000 / 1.000 / 1.000 (1.000) | Tomato Late blight | 285 | 0.976 / 0.986 / 0.981 (0.877) |
| **Mango Die Back** | 52 | 1.000 / **0.462** / 0.632 (1.000) | Tomato Leaf Mold | 144 | 1.000 / 0.944 / 0.971 (0.965) |
| **Mango Gall Midge** | 4 | 0.235 / 1.000 / **0.381** (0.348) | Tomato Septoria | 265 | 0.942 / 0.981 / 0.961 (0.910) |
| Mango Healthy | 137 | 0.992 / 0.920 / 0.955 (0.601) | Tomato Spider mites | 252 | 0.987 / 0.929 / 0.957 (0.937) |
| Mango Powdery Mildew | 169 | 0.871 / 0.959 / 0.913 (0.964) | Tomato Target Spot | 210 | 0.899 / 0.976 / 0.936 (0.884) |
| Mango Sooty Mould | 45 | 0.938 / 1.000 / 0.968 (0.918) | Tomato YLCV | 481 | 0.992 / 0.977 / 0.984 (0.985) |
| | | | Tomato mosaic virus | 56 | 0.982 / 1.000 / 0.991 (0.974) |
| | | | Tomato healthy | 238 | 0.983 / 0.996 / 0.990 (0.996) |

Held-out-device: Anthracnose recall 0.869 (4.9.4: 0.047), Powdery Mildew 3 of 4. By held-out phone: SM-A525F 0.873, vivo V2204 0.849. On known devices the HUAWEI RNE-L22 (MangoLeafBD) images score lowest at 0.780.

**Why C2 failed.** All 52 known-device Die Back test images and all 4 Gall Midge test images are MangoLeafBD photographs from one phone (HUAWEI RNE-L22). The model recognised 24 of 52 Die Back images, calling 20 Powdery Mildew and 7 Gall Midge, and predicted Gall Midge for 13 images of other classes. Validation Die Back recall had been 0.83. The Gall Midge F1 rests on 4 images.

### Comparison with the Mango candidate (mango5_exp001 B_partial_ft_s43)

A direct comparison is not possible. The candidate has 5 Mango classes (no Cutting Weevil, Die Back or Sooty Mould, and none of the other crops). It was evaluated on AGL-MANGO-MD v1.1.0-rc1 tiers (574 known / 597 held-out images, including SAR Golmichi images as Gall Midge, which are now quarantined) with `ood_logit` 1.5. Its kiosk-path evaluation was executed once and **failed P2** (false rejection 6.0% known / 12.4% held-out) **and P3** (decision-recall drops: Healthy 0.138, Anthracnose 0.103). That result stands and was not repeated.

What 5.0.0 changed in response, measured on its own frozen tiers under its own pre-declared protocol (C1–C9), not as a re-run of P2/P3:

- Thresholds are calibrated per worst group (each crop and each Mango source) instead of pooled validation. P2 showed pooled validation under-states the false rejection under device shift.
- The gate sits below almost all in-distribution answers: on validation, 99% of images have a maximum logit above 2.21, and the frozen gate is 2.10.
- The app now uses thresholds that belong to the loaded model, so the 4.9.4 device value 6.0 can no longer reject most new-phone images.
- Results: false rejection 3.0% Mango known-device, 5.3% held-out; largest decision-recall gap 0.096 (Die Back) and 0.047 for held-out Anthracnose. On the classes both models share, held-out Anthracnose recall is 0.869 (5.0.0) against 0.866 (candidate), on different test sets.

## D. Application 5.0.0

| Item | Status |
|---|---|
| Identity | `APP_VERSION 5.0.0`, `OTA_RELEASE_ID AGRILENS-5.0.0`, `MODEL_ID AGRILENS-MULTICROP`, `MODEL_VERSION 1.0.0`, `DATASET_VERSION AGL-MULTICROP-MD 1.0.0`, `MODEL_SHA256 776d08ac…`, build `2026-11-17 18:00 IST (release candidate)` |
| Model loading | ONNX loads; output width and `MODEL_NUM_CLASSES` checked against `labels.txt`. On mismatch the app runs in DEMO mode; an unknown model file is flagged (tests) |
| Class mapping | 24 labels, identical order and bytes to 4.9.4; the export refuses any other order |
| Preprocessing / six views / logit ensemble | unchanged from 4.9.4. Goldens for the new model: 24 of 24 sample images top-1 correct (4.9.4: 23 of 24); ONNX parity 1.2e-5 |
| Confidence and OOD | `resolve_gate_thresholds`: saved settings only if saved for this model's SHA-256, else the model's calibration (0.40 / 0.12 / 2.10), else generic defaults. Admin save records `calibration_model_sha256`; reset restores the model calibration |
| Camera, touchscreen, Hindi/English, file and live diagnosis, Admin | code unchanged from 4.9.4 apart from the gate and OTA changes. Covered by regression tests with fakes (camera 14, configuration incl. language 32, decision rules 18). **Not exercised on a real screen, camera or Pi** |
| Configuration precedence | 4.9.4 precedence matrix still reproduced (tests) |
| Startup and error handling | headless load, inference error handling and DEMO fallback tested; the Tk start-up itself was not run in this session |

### Automated tests (desktop, Windows, Python 3.13, onnxruntime 1.32)

| Suite | Tests |
|---|---|
| tests/unit/test_release_5_0_0.py | 15 |
| tests/integration/test_ota_publication.py | 11 |
| tests/integration/test_inapp_ota.py (new) | 7 |
| tests/regression (camera 14, classifier 20, configuration 32, decision rules 18, field-validation tools 7, label mapping 10, legacy OTA surface 11) | 112 |
| **Total** | **145 run, 145 passed, 0 failed, 0 skipped** |

`ruff check .` passes. The waivers are listed in `pyproject.toml`.

## E. OTA

| Path | Tested against the 5.0.0 package (local HTTP server, real updater code) |
|---|---|
| Start-up `ota_update.sh`, 4.9.4 version → 5.0.0 (first hop) | all 10 fetched files including the model arrive byte-identical; the updated app loads the new model and ignores the stale `ood_logit` 6.0 |
| In-app `_trigger_ota_update`, 4.9.4 code → 5.0.0 | same result (new test) |
| 5.0.0 → synthetic 5.0.1, both paths | update applied; previous files kept in `rollback/v5.0.0/`; model not downloaded again when the SHA-256 is unchanged |
| OTA hold | `~/.agrilens_ota_hold` stops the 5.0.0 start-up updater and the boot-time in-app update |
| Downgrade | blocked on both paths |
| Uncompilable `main.py` | rejected before anything, including the model, is replaced (in-app path) |
| `rollback.sh` | restores `rollback/v4.9.4`, compiles first, sets the hold, prints the 4.9.x warning (Git Bash on Windows) |

Fixed repository paths are unchanged: `https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi/`. Both updaters fetch the same 10 files: `main.py`, `labels.txt`, the 2 logos, `HOW_TO_RUN_ON_RASPBERRY_PI.md`, `setup_rpi.sh`, `run_agrilens.sh`, `ota_update.sh`, `setup_remote_ota.sh`, `rollback.sh`. They also fetch `agrilens.onnx` when `MODEL_SHA256` differs. 4.9.4 updaters skip `rollback.sh`; the 5.0.0 updater they install fetches it on the next update.

**Package** `AGRILENS_RaspberryPi/` has 38 files and is reproducible. Key checksums:

| File | SHA-256 |
|---|---|
| `main.py` | `8f6c0378f0d12e57b5d35a0804392011f3a594c63ed19d0c0c001988c1b8ffc8` |
| `agrilens.onnx` | `776d08ac669d0ea8874a458bfb6ea2657c5d40525d30021c7c8c1204d520332b` |
| `labels.txt` | `5087b575db52af07cf8efe82b033ea2715b7dd6b20106f3554ae7945e7aed393` (same as 4.9.4) |
| `ota_update.sh` | `4e46d42ecaeae28e2b285f7c092a48bb50a8f886103b5e998feabb11521257ba` |
| `rollback.sh` | `1ac2d6688954881b8fe544fa82e35e7b3f790685a0bd475147e08193588ff1ec` |
| `kiosk_config.json` | `ea78640c32797adf131c9958631537ec120d7914b52de1b83346a4617d6b71b6` (committed 4.9.4 default) |
| `SHA256SUMS` | `37fb89c6805e4130cb2e790b9c35b878011ee9029479d2319122fa19bda8229c` |
| `RELEASE_MANIFEST.json` | `ba3a0826c47613bcaec1b8365b7bdf744938c3174511886256a0ebda01fbb20f` |
| Rollback release `AGRILENS-5.0.1-rollback/SHA256SUMS` | `8d7cf8c32206574693da8ef5e9c0a538e3c52444887820eb149f2974058319ff` |

All 38 file hashes are in `AGRILENS_RaspberryPi/SHA256SUMS`. The release record is `deployment/release_manifests/AGRILENS-5.0.0.json`.

Installation: `documentation/technical/INSTALLATION.md`. Kiosks on 4.9.4 update themselves after publication; new Pis need clone, `sha256sum -c SHA256SUMS`, `setup_rpi.sh`, `run_agrilens.sh`. Rollback: `documentation/technical/ROLLBACK.md`. A single kiosk uses `rollback.sh`; the whole fleet uses the prepared release `AGRILENS-5.0.1-rollback` (4.9.4 code and model at version 5.0.1, because updaters block downgrades). The first hop from 4.9.4 keeps no rollback copy on the device, and a kiosk rolled back to 4.9.4 re-updates while `main` serves 5.0.0 unless it is kept offline.

## F. Release decision

| # | Area | Status | Basis |
|---|---|---|---|
| 1 | Repository consolidation | **Complete** | single app source, generated OTA folder, registers, preservation checks |
| 2 | Dataset consolidation | **Complete** | AGL-MULTICROP-MD 1.0.0 frozen and verified; 0 leakage. Gall Midge and Turning Brown remain provisional pending expert review |
| 3 | Integrated model training | **Complete** | 4 runs, rule-based selection, export with parity |
| | Release criteria for the model (C1–C9) | **Failed** | C2: Mango macro-F1 0.849 < 0.85. The other 8 pass |
| 4 | Application integration | **Complete** | 5.0.0 with model-specific gates; tested headless |
| 5 | Automated testing | **Complete** | 145 / 145 passed, 0 skipped |
| 6 | Raspberry Pi validation | **Pending** | no Pi benchmark run; desktop figures only |
| 7 | C270 field validation | **Pending** | no C270 data |
| 8 | Expert review | **Pending** | 235-item package not reviewed |
| 9 | OTA package readiness | **Complete** | package built, reproducible, checksummed, both update paths and rollback tested |
| 10 | GitHub publication readiness | **Failed** | blocked by C2 until you decide; procedure prepared in `GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md`; nothing published |

**Decision needed from you.** Options:

1. **Waive C2** and record the waiver. The miss is 0.001 on one crop, Die Back is the known weak class, and against 4.9.4 the release is far better on unseen phones (held-out accuracy 0.868 against 0.058). Then decide whether to publish before the Pi, C270 and expert checks.
2. **Do not release 1.0.0.** Plan a 1.1.0 with more Die Back data under a new pre-declared protocol. The current test tiers have now been seen, so 1.1.0 needs fresh test images to keep its evaluation unbiased.
3. Publish only to selected kiosks, after a Pi benchmark, by updating them manually from this folder while `main` stays on 4.9.4.

I recommend option 1 or 3 only together with a Raspberry Pi benchmark first. A fleet-wide OTA should wait for that measurement.

## Exact commit (local only)

The release clone has one local commit on `release/agrilens-5.0.0` with all the changes above. `git log -1` there shows its id. It has not been pushed.
