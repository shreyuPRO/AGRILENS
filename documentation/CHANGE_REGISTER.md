# AGRILENS change register

Every significant change from 2026-11-17 onwards. Rules, fields and categories: `documentation/governance/ENGINEERING_GOVERNANCE.md`, section 4. Earlier changes: `documentation/history/REVISION_HISTORY_to_4.9.4.md` (up to 4.9.4) and the 5.0.0 restructure records `documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv` and `REPOSITORY_CHANGE_LOG_5.0.0.csv`.

New entries: `python tools/governance/agl_governance.py register new --title "..." --category "..."`. The commit id of the newest entry stays `pending` until `register sync` runs with the next change; the machine-recorded result of each commit is in `git notes --ref=agrilens show <commit>`.

### CR-0001 — Publication of AGRILENS 5.0.0 to GitHub main

| Field | Value |
|---|---|
| Date | 2026-11-17 |
| Application version | 5.0.0 (release; previous published version 4.9.4). Recorded after the fact on 2026-11-18. |
| Category | DevOps/OTA |
| Description | Branch `release/agrilens-5.0.0` was pushed to `https://github.com/faiyaze04/AGRILENS` branch `main` as a fast-forward (`01059f8` → `9017320`) by the Kiro agent, authenticated as the repository owner, after the owner's explicit approval. Kiosks download 5.0.0 on their next boot, kiosk start or Admin OTA tap. |
| Reason | Owner decision to deploy 5.0.0; on 2026-11-18 the owner decided to retain it (no rollback, no rollback release 5.0.1, no retraining, no change of release criteria). |
| Files affected | Whole branch, including the OTA folder `AGRILENS_RaspberryPi/` (38 files, `SHA256SUMS`); file list in `documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv`. |
| Tests executed | Before the push: OTA simulation on the desktop (4.9.4 files from GitHub as the starting state, the 5.0.0 `ota_update.sh` logic against a local HTTP server serving the 5.0.0 folder, kiosk restart step stubbed); checks of line endings, `main.py` compilation, `SHA256SUMS`, imports, model hash. After the push: raw GitHub URLs re-read until they served 5.0.0, model hash compared. On 2026-11-18 on the same commit: `pytest` (whole suite) and `agl_governance.py check --full`. |
| Test outcome | Simulation: all 10 updatable files replaced and identical to the release, model SHA-256 verified, second run "up to date", `rollback/v4.9.4/` created. Raw URLs served 5.0.0 about 4 to 5 minutes after the push (CDN cache), model hash matched. 2026-11-18: 149 passed; full gate on `9017320`: package byte-reproducible, all model, version and package checks pass. Not tested: the restart step on a real Pi, any Raspberry Pi 5, C270 or touch-display test. |
| Documentation updated | None at the time. Corrected in `CR-0002`: `README.md`, `INSTALLATION.md`, `ARCHITECTURE.md`, `RELEASE_NOTES_5.0.0.md`, `MODEL_REGISTRY.json`; the planned procedure was archived. |
| Known risks | Published without `deployment/ota/publish_ota_release.ps1` and without the tag `AGRILENS-5.0.0`. Release criterion C2 (Mango macro-F1 0.849) failed and is accepted only as a recorded deviation. No Raspberry Pi 5, C270 or expert validation. 4.9.4 kiosks keep no rollback copy for this first update. The exhibition kit procedures assume `main` serves 4.9.4. 2026-11-18 field report: a Mango leaf rejected as UNKNOWN PLANT on the exhibition hardware, cause not established. |
| Commit | 9017320 |

### CR-0002 — Engineering governance: versioning, hooks, quality gate, documentation audit

| Field | Value |
|---|---|
| Date | 2026-11-18 |
| Application version | 5.0.0 (unchanged: repository tooling, tests and documentation only; no shipped file changed, verified by the gate check "package matches source") |
| Category | Tooling; Documentation; DevOps/OTA |
| Description | Added `tools/governance/agl_governance.py` with rules `governance_rules.json`: version report and `bump`, change impact, documentation obligations, change register, HOW_TO index, pre-commit and pre-release quality gate, Kiro and git hook entry points. Kiro hooks A to C in `.kiro/hooks/`; git pre-commit and post-commit shims. New documents `HOW_TO.md`, `documentation/technical/CONFIGURATION.md`, `documentation/governance/ENGINEERING_GOVERNANCE.md`, `documentation/governance/DOCUMENTATION_AUDIT_2026-11-18.md`, this register. Documentation audit: outdated status statements corrected, stale paths fixed, superseded documents archived. Unit tests `tests/unit/test_governance.py`. |
| Reason | Owner directive of 2026-11-18 (engineering governance): versioning, documentation and quality controls must be automatic and traceable. |
| Files affected | `tools/governance/*`, `.kiro/hooks/*`, `tests/unit/test_governance.py`, `HOW_TO.md`, `README.md`, `.gitignore` (BOM removed), `documentation/CHANGE_REGISTER.md`, `documentation/governance/*`, `documentation/technical/{ARCHITECTURE,INSTALLATION,CONFIGURATION,field_validation_protocol_phase_A}.md`, `documentation/release_notes/RELEASE_NOTES_5.0.0.md`, `models/manifests/MODEL_REGISTRY.json`; moved to `documentation/history/`: `GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md`, the three Phase A reports |
| Tests executed | Main repository, 2026-11-18: `agl_governance.py check --full` (includes `ruff check .`, `bash -n` on 22 scripts, ONNX load and sanity inference, package build in a temporary copy, whole pytest suite); baseline `pytest` before any change. Throwaway clone in the user's temporary folder (never pushed): S1 unversioned change to `application/main.py` committed through the hooks; S2 `bump minor`; S3 staged `debug_probe.py` containing a token; S4 documentation-only change; S5 complete governance change committed through Kiro hook C and the git hooks, then `git notes --ref=agrilens show HEAD`. Kiro hooks observed live in this session: A (prompt after every file write) and C (intercepted shell commands containing a commit). Hook B (UserPromptSubmit) has not fired yet: no prompt was submitted after it was created. |
| Test outcome | Baseline: 149 passed. After the change: full gate PASS (46 pass, 0 fail, 1 warn = uncommitted tree, 1 skip = no type checker); pytest 183 passed (149 existing + 34 new); ruff clean; package rebuild byte-identical to the committed `AGRILENS_RaspberryPi/` (41 files). S1 blocked by the git pre-commit hook and by Kiro hook C: version not incremented, no register entry, no documentation; the existing test `test_device_package_is_generated_from_the_sources[main.py]` also failed, as expected. S2: APP_VERSION 5.0.0 → 5.1.0 propagated to `OTA_RELEASE_ID`, `BUILD_TIMESTAMP`, both markers and a release-notes stub; a second bump refused. S3: junk and secret checks FAIL. S4: PASS, tests skipped, register warning. S5: gate PASS (183 passed), commit created, git note with version, change id, files and test summary; no push. Defects found by these tests and fixed before this commit: hook C checked the session repository instead of the command's working directory, and missed commits written with `-c key=value` options; the first commit attempt of this change was blocked because the whitespace check treated the CRLF line endings of the byte-preserved `models/manifests/MODEL_REGISTRY.json` as trailing whitespace (now checked with `core.whitespace=cr-at-eol` for that invocation only). |
| Documentation updated | `HOW_TO.md`, `README.md`, `documentation/governance/ENGINEERING_GOVERNANCE.md`, `documentation/governance/DOCUMENTATION_AUDIT_2026-11-18.md`, `documentation/technical/CONFIGURATION.md`, `ARCHITECTURE.md`, `INSTALLATION.md`, `field_validation_protocol_phase_A.md`, `RELEASE_NOTES_5.0.0.md`, this register |
| Known risks | Kiro hook behaviour depends on the Kiro hook runtime (working directory = repository root, tool call as JSON on stdin); the git hooks enforce the gate independently. The gate runs the whole test suite (about 75 s) for every non-documentation commit; in S5 it ran in both the Kiro hook and the git hook (the skip of an already-passed tree was verified separately). Kiro shows hook output only when a hook blocks. Hook C matches command text, so a shell command that merely mentions a commit command in a quoted string is also checked (and blocked if the gate fails); write such text with the file tools. The device guide and exhibition kit still contain the outdated statements listed in the audit (open items 1 and 2). Proposed deletion of `archive/legacy_tools/push_ota_update_4.9.4.bat` awaits approval. |
| Commit | 492973e |

### CR-0003 — Relocate training paths to AGRILENS_5.0.0 workspace; verify kiosk and trainer

| Field | Value |
|---|---|
| Date | 2026-11-18 |
| Application version | 5.0.0 (unchanged: only training configs, docs and a lock file changed; no shipped file) |
| Category | Dataset/training |
| Description | Training configs and scripts point at Model_Trainer_Program in the AGRILENS_5.0.0 workspace; TRAINING.md dataset and cache paths updated. Kiosk and trainer verified after the move. |
| Reason | The projects were moved from D:\AGRILENS_Training to the OneDrive AGRILENS_5.0.0 folder. |
| Files affected | documentation/technical/TRAINING.md, requirements-lock.txt, training/configurations/make_configs.py, training/configurations/multicrop1_R1_s42.yaml, training/configurations/multicrop1_R1_s43.yaml, training/configurations/multicrop1_R2_s42.yaml, training/configurations/multicrop1_R2_s43.yaml, training/experiments/mango5_exp001/configs/A_frozen_head_s42.yaml, training/experiments/mango5_exp001/configs/A_frozen_head_s42_repro.yaml, training/experiments/mango5_exp001/configs/A_frozen_head_s43.yaml, training/experiments/mango5_exp001/configs/A_frozen_head_s44.yaml, training/experiments/mango5_exp001/configs/B_partial_ft_s42.yaml ... |
| Tests executed | pytest -q (Kiosk .venv); train_integrated.py smoke run (64 samples, 1 epoch, temp output); verify_dataset; SHA256SUMS check of AGRILENS_RaspberryPi; 20 s launch of AGRILENS_RaspberryPi/main.py |
| Test outcome | 183 tests passed; smoke training completed with all outputs; dataset verified (24 classes); 38/38 checksums match; app stayed running 20 s without errors |
| Documentation updated | documentation/technical/TRAINING.md |
| Known risks | Dataset build tools under datasets/dataset_tools and several records still name D:\AGRILENS_Training (historical; the tools would fail if re-run). Model training downloads pretrained weights from Hugging Face unless cached. |
| Commit | f1af394 |

### CR-0004 — AGRILENS 5.1.0: C270 capture at 1280x720 (MJPG) with 640x480 fallback

| Field | Value |
|---|---|
| Date | 2026-11-18 |
| Application version | 5.1.0 (minor, from 5.0.0: new backward-compatible camera functionality and a new configuration key; model unchanged) |
| Category | Hardware |
| Description | `Camera.detect_webcam` requests `cam_resolution` (default `1280x720`, the C270 maximum) in MJPG and retries the same port at 640x480 if no frames arrive; the delivered size is shown in the status bar. New config key `cam_resolution` (`1280x720` or `640x480`, validated, saved with the other settings). Package rebuilt as AGRILENS-5.1.0; release record written. Tests that pinned 5.0.0 as the current package were made version-relative; the exhibition kit test now uses the published 5.0.0 package (commit 9017320), because the EXPISCOR kit is 5.0.0-specific. |
| Reason | Owner request (2026-11-18): configure the camera to the maximum possible resolution and publish the change by OTA. |
| Files affected | application/main.py, application/configuration/kiosk_config.default.json, deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md, AGRILENS_RaspberryPi/ (main.py, kiosk_config.json, HOW_TO_RUN_ON_RASPBERRY_PI.md, RELEASE_MANIFEST.json, SHA256SUMS), deployment/release_manifests/AGRILENS-5.1.0.json, tests/regression/test_camera.py, tests/regression/test_configuration.py, tests/integration/test_inapp_ota.py, tests/integration/test_ota_publication.py, tests/integration/test_exhibition_kit.py, tests/unit/test_release_5_0_0.py, README.md, HOW_TO.md, documentation/technical/CONFIGURATION.md, documentation/technical/ROLLBACK.md, documentation/release_notes/RELEASE_NOTES_5.1.0.md, tools/governance/governance_rules.json, this register |
| Tests executed | `python -m pytest -q` (Kiosk .venv, Windows, mocked OpenCV); `build_device_package.py --model-dir models/candidates/agrilens-multicrop-1.0.0` |
| Test outcome | 196 passed, 0 failed, 0 skipped. Package build: AGRILENS-5.1.0, 38 files, model SHA-256 unchanged. Not tested on a real C270 or Raspberry Pi 5. |
| Documentation updated | HOW_TO_RUN_ON_RASPBERRY_PI.md (version, camera-resolution troubleshooting), HOW_TO.md (camera setup), CONFIGURATION.md (`cam_resolution`), ROLLBACK.md (5.0.1 rollback is a downgrade for 5.1.0 kiosks), RELEASE_NOTES_5.1.0.md, HOW_TO index. Verified, no change needed: ARCHITECTURE.md, ENGINEERING_GOVERNANCE.md, MODEL_REGISTRY.json (model unchanged) |
| Known risks | Preview frame rate, CPU load and MJPG decoding on the Raspberry Pi 5 are unmeasured; diagnosis behaviour on live 1280x720 captures is unvalidated (model and gates validated on image files). Kiosks on 5.1.0 refuse AGRILENS-5.0.1-rollback; a fleet rollback needs a release above 5.1.0. Per-kiosk mitigation: `cam_resolution` = `640x480` in ~/.agrilens_kiosk_config.json. |
| Commit | f1af394 |

### CR-0005 — Exhibition kit discarded (owner request)

| Field | Value |
|---|---|
| Date | 2026-11-18 |
| Application version | 5.1.0 (unchanged: no shipped file changed; the kit was never part of the OTA package) |
| Category | Tooling |
| Description | Deleted the EXPISCOR 2026 exhibition kit and everything that existed only for it: deployment/exhibition/ (kit builder, launcher, Pi backup/install/benchmark/restore scripts, kit README, test checklist), tests/integration/test_exhibition_kit.py, tools/validation/exhibition_desktop_check.py, documentation/exhibition/ (desktop and GUI check results) and `EXHIBITION_READINESS_REPORT_5.0.0.md`. Removed the kit's governance area, index entries and lint exceptions. Outside the repository, deleted `Release_Evidence/exhibition/` (kit zip and unpacked kit), the exhibition logs and test outputs there, and leftover pytest temp copies. Dated note added to RELEASE_NOTES_5.0.0.md. `C2_DEVIATION_EXHIBITION_ACCEPTANCE.md` is kept: it records the C2 release decision. |
| Reason | Owner request (2026-11-18): the exhibition kit is not needed; delete it completely. |
| Files affected | deployment/exhibition/ (8 files, deleted), tests/integration/test_exhibition_kit.py (deleted), tools/validation/exhibition_desktop_check.py (deleted), documentation/exhibition/ (2 files, deleted), documentation/release_notes/EXHIBITION_READINESS_REPORT_5.0.0.md (deleted), documentation/release_notes/RELEASE_NOTES_5.0.0.md, tools/governance/governance_rules.json, pyproject.toml, HOW_TO.md (index), this register |
| Tests executed | `python -m pytest -q` (Kiosk .venv, Windows) |
| Test outcome | 192 passed, 0 failed (the 4 exhibition-kit tests were deleted with the kit). |
| Documentation updated | RELEASE_NOTES_5.0.0.md (dated note), HOW_TO.md index. Older records (DOCUMENTATION_AUDIT_2026-11-18.md, CR-0004, release readiness report) still mention the kit as history and are not edited. |
| Known risks | None for kiosks. The files remain in git history (commit 9017320) and on GitHub main until this commit is pushed. Any Raspberry Pi where the kit was installed keeps its own copy (for example ~/AGRILENS_5.0.0 and ~/.agrilens_ota_hold); remove those on the device. |
| Commit | 774cdd4 |

### CR-0006 — Model trainer separated into the standalone Model_Trainer_Program

| Field | Value |
|---|---|
| Date | 2026-11-18 |
| Application version | 5.1.0 (unchanged: nothing shipped to kiosks changed; training code was never part of the OTA package) |
| Category | Dataset/training |
| Description | The model trainer is now a standalone program outside this repository: training/scripts, training/configurations, training/experiments, training/legacy_4.9.4 and datasets/dataset_tools moved to `<AGRILENS_5.0.0>\Model_Trainer_Program\trainer\` (65 files, copied from HEAD, then removed here). In the trainer: configuration paths are relative to Model_Trainer_Program (`agl_common.resolve`); scripts locate their own folders from `__file__` instead of absolute `D:\...` paths; `export_onnx.py` defaults to `exports\<run_id>` and to its own copy of the kiosk class order (`configurations\kiosk_labels_24class.txt`) and takes `--model-id`/`--model-version` instead of a hard-coded 1.0.0; new `Model_Trainer_Program\README.md` and `trainer\requirements-train-lock.txt`. Kept here: `training/evaluation/` (runs the kiosk `main.py`; frozen calibration and release evaluation read by the release tooling) and `training/reports/` (release evidence). |
| Reason | Owner request (2026-11-18): separate the kiosk program from the trainer; the trainer must work on its own and does not belong on a Raspberry Pi (a new Pi installed by `git clone` received all training code). |
| Files affected | training/scripts/, training/configurations/, training/experiments/, training/legacy_4.9.4/, datasets/dataset_tools/ (removed; now in Model_Trainer_Program\trainer\), documentation/technical/TRAINING.md (rewritten: trainer location, hand-over, evaluation), documentation/technical/ARCHITECTURE.md, documentation/technical/ROLLBACK.md (4.9.4 bundle path), documentation/governance/ENGINEERING_GOVERNANCE.md (rule 6), README.md (layout), HOW_TO.md (index), tools/governance/governance_rules.json, pyproject.toml, requirements-lock.txt (pins of the kiosk test environment, written when .venv was rebuilt after the move; previously untracked), this register |
| Tests executed | Trainer (outside the repository): all 37 trainer scripts compile; config paths resolve; dataset freeze check; standalone smoke run started from an unrelated folder (train_integrated.py 64 samples / 1 epoch, then export_onnx.py with default class order and --model-version). Kiosk: `python -m pytest -q`. |
| Test outcome | Trainer: training and export exit 0; export parity max logit difference 8.9e-7, argmax agreement 1.0; manifest carries the given version. Kiosk: 192 passed, 0 failed. |
| Documentation updated | TRAINING.md, ARCHITECTURE.md, ROLLBACK.md, ENGINEERING_GOVERNANCE.md, README.md, HOW_TO index; new Model_Trainer_Program\README.md. Not edited: release records and manifests that cite the old training/ paths (MODEL_MANIFEST.json, MODEL_REGISTRY.json training_run text, release readiness report, 5.0.0 change logs) and the frozen dataset-card mirror. |
| Known risks | Model_Trainer_Program is now its own local git repository (allow-list .gitignore: code, configurations, records and run metrics only; 113 files, 0.56 MB); its GitHub repository is not yet created. The pre-move history is in this repository's git history. Four dataset-builder scripts still name the original AgriLens source folders (needed only to rebuild a dataset from sources). On GitHub the moved folders remain until this commit is pushed. |
| Commit | 774cdd4 |

### CR-0007 — Candidate model AGRILENS-MULTICROP 1.1.0 handed over (not released)

| Field | Value |
|---|---|
| Date | 2026-11-19 |
| Application version | 5.1.0 (unchanged: the candidate is not used by the application; no shipped file changed) |
| Category | AI/model |
| Description | Candidate model AGRILENS-MULTICROP 1.1.0 added to models/candidates/agrilens-multicrop-1.1.0/ (SHA-256 0774ca4aadab930086ade370234919a69cf35c8a22844355f78a20a194e0f08e, 24 classes, class order identical to 1.0.0) with its gate calibration (confidence 0.40, margin 0.12, ood_logit 2.90, same rule as 1.0.0), selection record and comparison report; MODEL_REGISTRY entry. Trained overnight by the Model Trainer Program with webcam-style augmentation; three runs, selected on validation: multicrop11_R2w_s42 (validation macro-F1 0.9768 vs 0.9643; full fine-tuning runs 0.9705 and 0.9605). New read-only tool training/evaluation/compare_models.py compares two models through the application's six-view path, each with its own gates. |
| Reason | Owner request (2026-11-18): a better-trained model for the Raspberry Pi 5 kiosk, trained overnight on the laptop with webcam-style augmentation and full fine-tuning; no new classes. |
| Files affected | models/candidates/agrilens-multicrop-1.1.0/ (new: agrilens.onnx, labels.txt, MODEL_MANIFEST.json, SELECTION.json, calibration/, comparison/), models/manifests/MODEL_REGISTRY.json, training/evaluation/compare_models.py (new), documentation/technical/TRAINING.md, documentation/technical/ARCHITECTURE.md, this register |
| Tests executed | compare_models.py on val, a simulated C270 set, test_known_device, test_heldout_device and the ood_v2 evaluation half (application six-view path); hand-over checks (copied model SHA-256 equals its manifest; labels identical to the kiosk labels.txt); python -m pytest -q (pre-commit gate) |
| Test outcome | 1.0.0 vs 1.1.0: test_known_device top-1 95.9% vs 97.4%, wrong-but-accepted 3.2% vs 1.9%; test_heldout_device top-1 86.8% vs 96.9%, wrong-but-accepted 12.0% vs 1.9%; simulated C270 correct-and-accepted 81.3% vs 95.1%, rejected-unknown 9.6% vs 2.1%; ood_v2 accepted 35.5% vs 33.5%. Mango Die Back recall 0.46 vs 0.90, Mango Healthy 0.92 vs 0.83. Hand-over checks passed. pytest: see the commit gate result. |
| Documentation updated | TRAINING.md (candidate 1.1.0 section), ARCHITECTURE.md (candidate row). Release notes not changed: nothing is released. |
| Known risks | Not checked on real Logitech C270 captures or on the Raspberry Pi 5. The simulated C270 set is related to the candidate's training augmentation and favours it. Mango Healthy recall dropped. The frozen 1.0.0 release evaluation (run-once) was not re-run; 1.1.0 has no formal release evaluation yet. A release needs MODEL_SHA256 and MODEL_CALIBRATION_OOD_LOGIT = 2.90 in main.py and owner approval. |
| Commit | pending |

### CR-0008 — AGRILENS 5.2.0: model AGRILENS-MULTICROP 1.1.0 (webcam-robust), gate ood_logit 2.90

| Field | Value |
|---|---|
| Date | 2026-11-19 |
| Application version | 5.2.0 (minor, from 5.1.0: new release model with its own calibrated rejection gate; same classes, interfaces and OTA) |
| Category | AI/model |
| Description | Release model changed from AGRILENS-MULTICROP 1.0.0 to 1.1.0 (CR-0007): MODEL_SHA256 0774ca4a...e0f08e, MODEL_VERSION 1.1.0 and MODEL_CALIBRATION_OOD_LOGIT 2.90 in application/main.py (confidence 0.40 and margin 0.12 unchanged); AGRILENS_RaspberryPi/ rebuilt from models/candidates/agrilens-multicrop-1.1.0 (new agrilens.onnx, main.py, device guide, RELEASE_MANIFEST.json, SHA256SUMS); release record deployment/release_manifests/AGRILENS-5.2.0.json. Tests: new golden baseline tests/regression/baseline_5.2.0/ (24 of 24 samples correct), model-identity and package-source tests made model-relative. write_release_record.py takes --model-dir, --calibration and --comparison (defaults unchanged). Kiosks download the 10 MB model once on their next OTA. |
| Reason | Owner request (2026-11-19): push and publish the better-trained model 1.1.0 to the kiosks. |
| Files affected | application/main.py, AGRILENS_RaspberryPi/ (main.py, agrilens.onnx, HOW_TO_RUN_ON_RASPBERRY_PI.md, RELEASE_MANIFEST.json, SHA256SUMS), deployment/release_manifests/AGRILENS-5.2.0.json, deployment/packaging/write_release_record.py, deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md, models/manifests/MODEL_REGISTRY.json, tests/regression/baseline_5.2.0/golden_predictions.json, tests/regression/test_classifier.py, tests/unit/test_release_5_0_0.py, README.md, HOW_TO.md, documentation/release_notes/RELEASE_NOTES_5.2.0.md, documentation/technical/ (ARCHITECTURE, CONFIGURATION, INSTALLATION, TRAINING), tools/governance/governance_rules.json, this register |
| Tests executed | build_device_package.py --model-dir models/candidates/agrilens-multicrop-1.1.0; python -m pytest -q (Windows, kiosk .venv); capture_baseline.py --only predictions for the new model; model comparison of CR-0007 |
| Test outcome | Package build passed its checks (MODEL_SHA256 = packaged model, 24 outputs = 24 labels, label order = release labels, main.py compiles, version newer). pytest: 192 passed, 0 failed. Sample images 24 of 24 top-1 correct. Model comparison: see CR-0007 and RELEASE_NOTES_5.2.0.md. |
| Documentation updated | RELEASE_NOTES_5.2.0.md, HOW_TO.md (version, model), README.md, device guide (version, model), CONFIGURATION.md (gate 2.90, saved thresholds ignored after a model change), INSTALLATION.md (example lines), ARCHITECTURE.md, TRAINING.md, MODEL_REGISTRY.json, HOW_TO index |
| Known risks | Published without Raspberry Pi 5 / Logitech C270 validation (owner decision). No run-once release evaluation (C1-C9) for 1.1.0. Mango Healthy recall lower than 1.0.0 (0.83 vs 0.92). Kiosk-saved slider thresholds for 1.0.0 are ignored after the update. CDN delay may leave a kiosk on the old model with generic gates until its next boot. Fleet rollback needs a release above 5.2.0 (5.0.1 rollback is a downgrade); single kiosks can use rollback.sh. |
| Commit | pending |

### CR-0009 — Release_Evidence folder deleted (owner request)

| Field | Value |
|---|---|
| Date | 2026-11-19 |
| Application version | 5.2.0 (unchanged: documentation only; nothing shipped changed) |
| Category | Documentation |
| Description | Deleted the folder <AGRILENS_5.0.0>\Release_Evidence (57 files outside git: the 4.9.4 git bundle and working-tree zip, dataset build/extract logs, a release-evaluation smoke run, logs and helper scripts of the 5.0.0 work and the folder move). Before deletion, git bundle verify passed and all 6 refs of the bundle (main 01059f8, restructure/v5 and tag phase-A 585698f) were found in GitHub main. ROLLBACK.md now points to the git history instead of the bundle; the folder was removed from AGRILENS_5.0.0.code-workspace. |
| Reason | Owner request (2026-11-19): the folder is of no further use. |
| Files affected | documentation/technical/ROLLBACK.md, this register (outside git: Release_Evidence deleted, AGRILENS_5.0.0.code-workspace) |
| Tests executed | git bundle verify; per-ref containment check against github/main; pre-commit gate |
| Test outcome | Bundle valid; 6 of 6 refs contained in GitHub main; folder absent after deletion. |
| Documentation updated | ROLLBACK.md. Older register entries and release records that mention Release_Evidence are historical and not edited. |
| Known risks | The 4.9.4 working-tree-as-found zip (uncommitted state from before 5.0.0) and the 5.0.0 work logs no longer exist outside OneDrive's recycle bin (kept there for about 30 days). |
| Commit | pending |

### CR-0010 — AGRILENS 5.3.0: diagnosis history (leaf image + record per diagnosis)

| Field | Value |
|---|---|
| Date | 2026-11-19 |
| Application version | 5.3.0 (minor, from 5.2.0: new backward-compatible kiosk functionality and two new configuration keys; model unchanged) |
| Category | Feature |
| Description | New DiagnosisHistory in application/main.py: after every DIAGNOSE NOW the diagnosed (cropped) leaf image is stored as ~/AGRILENS_history/YYYY-MM-DD/YYYYMMDD_HHMMSS_mmm_VERDICT.jpg with a JSON record next to it and one row in ~/AGRILENS_history/diagnosis_log.csv (time local/UTC, status, verdict code, result, crop, condition, confidence, top-1, margin, max logit, top-3, input mode and source file, selected crop, crop box, frame size, quality, camera, gates and their source, app/release, model id/version/SHA-256, engine, latency, language, host, save status). _render_diagnosis records a language-independent last_verdict; handle_diagnose writes the history (not the language re-render). Background thread, errors never interrupt the kiosk, max images (oldest deleted, CSV kept), no image below 300 MB free disk. New config keys history_enabled (default true) and history_max_images (default 5000, 0-100000), validated and saved. History lives outside AGRILENS_RaspberryPi/, so OTA and rollback.sh never touch it. Package rebuilt as AGRILENS-5.3.0 (model unchanged); release record written. |
| Reason | Owner request (2026-11-19): store each captured leaf image with a date-time stamp in a history folder, with a historical log of the diagnosis, its metadata and status. |
| Files affected | application/main.py, application/configuration/kiosk_config.default.json, AGRILENS_RaspberryPi/ (main.py, kiosk_config.json, HOW_TO_RUN_ON_RASPBERRY_PI.md, RELEASE_MANIFEST.json, SHA256SUMS), deployment/release_manifests/AGRILENS-5.3.0.json, tests/unit/test_history.py (new), tests/regression/test_configuration.py, tools/validation/app_harness.py (decide() also returns last_verdict), deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md, README.md, HOW_TO.md, documentation/technical/CONFIGURATION.md, ARCHITECTURE.md, ROLLBACK.md, documentation/release_notes/RELEASE_NOTES_5.3.0.md, tools/governance/governance_rules.json, this register |
| Tests executed | python -m pytest -q (Windows, kiosk .venv, AGRILENS_HISTORY_DIR set to a temporary folder); end-to-end on the PC: two sample images through the application's classifier, decision code and _record_history; build_device_package.py |
| Test outcome | 207 passed, 0 failed (15 new history tests). End-to-end: DISEASE and HEALTHY images, JSON records and two CSV rows written with the expected values. Package build passed. Not tested on the Raspberry Pi 5. |
| Documentation updated | RELEASE_NOTES_5.3.0.md, HOW_TO.md (new section Diagnosis history), device guide (history location, copying, switching off), CONFIGURATION.md (history_enabled, history_max_images), ARCHITECTURE.md, ROLLBACK.md, HOW_TO index. Verified, no change needed: field_validation_protocol_phase_A.md, MODEL_REGISTRY.json (model unchanged). |
| Known risks | SD-card write speed and folder permissions on the Pi 5 not tested. Images are stored without a size limit per image (crop of up to 1280x720). The kiosk has no screen to browse or delete the history. |
| Commit | pending |

### CR-0011 — AGRILENS 5.4.0: diagnosis history upload to OneDrive (rclone copy)

| Field | Value |
|---|---|
| Date | 2026-11-19 |
| Application version | 5.4.0 (minor, from 5.3.0: new backward-compatible kiosk functionality and four new configuration keys; model unchanged) |
| Category | Feature |
| Description | New HistorySync in application/main.py: background thread that uploads ~/AGRILENS_history to OneDrive with rclone copy (new and changed files only; never deletes in OneDrive; files younger than 20 s wait for the next run), first attempt 120 s after kiosk start, then every history_sync_minutes (default 30). Each attempt checks rclone is installed, the remote exists (rclone listremotes) and graph.microsoft.com:443 is reachable; offline attempts are skipped. One status line per attempt in ~/AGRILENS_history_sync.log (last 1000 lines). New validated and saved config keys history_sync_enabled (true), history_sync_remote (agrilens_onedrive), history_sync_path (AGRILENS_Kiosk_History; the owner's project path is set on the Pi, not in the code), history_sync_minutes (30, 5-1440). The OneDrive sign-in stays in rclone's own configuration on the Pi; the application stores no credentials. Built into main.py (not a separate script) so it arrives with a single OTA run. Package rebuilt as AGRILENS-5.4.0 (model unchanged); release record written. |
| Reason | Owner request (2026-11-19): when the Raspberry Pi has internet, send the diagnosis history to OneDrive. Owner decisions: copy (not mirror), destination AGRILENS_5.0.0\Kiosk_History, owner's Microsoft 365 work/school account, every 30 minutes, publish 5.3.0 first and the upload as 5.4.0. |
| Files affected | application/main.py, application/configuration/kiosk_config.default.json, AGRILENS_RaspberryPi/ (main.py, kiosk_config.json, HOW_TO_RUN_ON_RASPBERRY_PI.md, RELEASE_MANIFEST.json, SHA256SUMS), deployment/release_manifests/AGRILENS-5.4.0.json, tests/unit/test_history_sync.py (new), tests/regression/test_configuration.py, deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md (setup section), README.md, HOW_TO.md, documentation/technical/CONFIGURATION.md, ARCHITECTURE.md, INSTALLATION.md, ROLLBACK.md, documentation/release_notes/RELEASE_NOTES_5.4.0.md, tools/governance/governance_rules.json, this register |
| Tests executed | python -m pytest -q (Windows, kiosk .venv); end-to-end with the real rclone v1.76 (portable, temporary) and an environment-defined local remote named agrilens_onedrive standing in for OneDrive; build_device_package.py |
| Test outcome | 219 passed, 0 failed (12 new sync tests). End-to-end: first run uploaded 2 images, 2 records and the CSV; a file younger than 20 s was skipped and uploaded by the next run; a locally deleted image stayed in the destination; an unconfigured remote did nothing. Package build passed. Real OneDrive sign-in and the Raspberry Pi 5 not tested. |
| Documentation updated | RELEASE_NOTES_5.4.0.md, device guide (new section with the one-time rclone setup and checks), HOW_TO.md, CONFIGURATION.md (four keys), ARCHITECTURE.md, INSTALLATION.md (optional rclone step), ROLLBACK.md (uploads after a rollback), HOW_TO index. Verified, no change needed: ENGINEERING_GOVERNANCE.md (no credentials in the repository still holds). |
| Known risks | The rclone OneDrive token on the Pi can read and write the whole OneDrive (revoke in the Microsoft account if the Pi is lost). The organisation may require admin consent for rclone. Not tested against the real OneDrive or on the Pi. No on-screen upload status. |
| Commit | pending |
