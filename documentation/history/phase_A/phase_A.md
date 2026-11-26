# Phase A report: baseline and safeguards

Branch `restructure/v5`, based on `main` at `01059f8`. Tag: `phase-A`.
**No existing file was modified except `.gitignore` (six lines appended). The application, model, labels, thresholds and every file under `AGRILENS_RaspberryPi/` are untouched.**

## 1. What was added

| Area | Files |
|---|---|
| Test harness | `scripts/app_harness.py` (loads the app without editing it, runs its real decision code), `tests/conftest.py`, `pyproject.toml` (pytest and ruff settings), `requirements-dev.txt` |
| Tests (115) | `tests/test_label_mapping.py` (10), `test_configuration.py` (32), `test_classifier.py` (20), `test_decision_rules.py` (18), `test_camera.py` (14), `test_legacy_ota_surface.py` (14), `test_field_validation_tools.py` (7) |
| Baselines | `tests/baseline/golden_predictions.json`, `config_precedence_matrix.json`, `legacy_ota_surface.json`; generator `scripts/capture_baseline.py` (`--check` compares without writing) |
| Pi diagnostics | `scripts/collect_pi_environment.sh`, `scripts/benchmark_pi5.py` |
| Field validation | `scripts/capture_field_samples.py`, `scripts/evaluate_field_validation.py`, `docs/field_validation_protocol.md` |
| Safeguards | `scripts/git_integrity_report.py`; Stage 0 backup folder `AGRILENS_backup_20261116_175516` (outside the repo) |
| Results | `docs/phase_reports/phase_A_test_results.txt` (full run), this report |
| Modified | `.gitignore` (appended `.pytest_cache/`, `.ruff_cache/`, `dist/`, `field_validation/`, `training/datasets/`, `*.bak`) |

Differences from the plan: `pyproject.toml` replaces `pytest.ini`, because `.gitignore` already excludes `*.ini`. `scripts/app_harness.py` and `tests/test_field_validation_tools.py` are additions needed to share code and to test the field tools. `pytest` and `ruff` were installed into the git-ignored `.venv`.

## 2. Test results (simulated, on a Windows PC)

`python -m pytest`: **115 passed, 0 failed**, 18 s. `ruff check scripts tests` (correctness rules E, F, W, B): clean. `python -m compileall` clean. Python 3.13.14, onnxruntime 1.32.0, numpy 2.5.5, Pillow 13.0.0, OpenCV 5.0.0. These are not Raspberry Pi results.

Do the tests actually detect change? I applied eight one-line behaviour changes to a temporary copy of the app (outside the repo) and ran the suite against each:

| Change applied to a copy | Result |
|---|---|
| Normalisation std 0.225 to 0.230 | Detected (golden predictions) |
| Ensemble weights 0.45/0.35 to 0.50/0.30 | Detected (golden predictions) |
| Validation crop 256 to 240 | Detected (golden predictions) |
| Confidence default 0.40 to 0.45 | Detected (5 tests) |
| OOD logit default 1.40 to 1.50 | Detected (6 tests) |
| Legacy reset rule 0.48 to 0.50 | Detected (2 tests) |
| Config order swapped (user file before app file) | Detected (4 tests) |
| Camera drop threshold 30 to 60 | Detected (1 test) |

## 3. Behaviour captured (current application, v4.9.4)

**Configuration** (matches section 1 of the revised plan). Order, lowest to highest priority: code defaults, app-dir `kiosk_config.json`, `~/.agrilens_kiosk_config.json`. Values are then clamped, then the legacy reset runs: if `ood_logit >= 1.80` and `confidence_threshold >= 0.48`, all four thresholds (`confidence_threshold`, `ood_margin`, `ood_logit`, `sharpness_min`) return to code defaults; camera keys are untouched. Boundaries are pinned by tests (1.80 and 0.48 reset; 1.79 or 0.47 do not). The device calibration (`ood_logit 6.0`, confidence 0.40, auto exposure and white balance off) loads unchanged and is not reset.

**Model and labels.** 24 labels in sorted order, 24 model outputs, input `[N,3,224,224]` (NCHW). The SHA-256 constant in `main.py` equals the model file's hash. The built-in fallback label list equals `labels.txt`. Preprocessing is ImageNet normalisation, RGB, bilinear.

**Decision gate.** UNKNOWN if the top class is a negative class, `max raw logit < ood_logit` (strictly less), or a selected crop has under 12% total probability. Otherwise LOW CONFIDENCE if confidence `< 0.40` or the top-1/top-2 margin `< 0.12`. UNKNOWN takes precedence over LOW CONFIDENCE. With no raw logits the gate is disabled.

**Sample images (regression only, not accuracy).** 23 of 24 samples are top-1 correct. The Tomato spider-mite sample is classified as Tomato yellow-leaf-curl virus (87% probability). All 24 are accepted (20 DISEASE, 4 HEALTHY) under both the code defaults and the `ood_logit 6.0` profile. The lowest raw logit among the samples is 6.64, above 6.0. Real C270 captures may behave differently, which is what the field validation measures.

## 4. Issues found (recorded, not fixed, for later phases)

| # | Finding | Where handled |
|---|---|---|
| 1 | The in-app version parser reads `4.9.4-rc1` as 4.9.41 (suffix digits merged). The shell parser reads it as 4.9.4.1. Pre-release suffixes would be ordered wrongly. | Phase D replaces both |
| 2 | All-NaN model output returns `(None, ms, None)`, which would crash the diagnosis screen. Total inference failure raises an unhandled exception. | Phase C |
| 3 | The camera is dropped after 31 failed reads and nothing re-opens it. Only an explicit detect call recovers. | Phase C |
| 4 | `ood_logit` and `confidence_threshold` interact through the reset rule. Raising confidence to 0.48 or more with `ood_logit 6.0` silently resets `ood_logit` to 1.4 at the next start. | Documented, preserved. Admin documentation in Phase C |
| 5 | Shell and in-app OTA parsers disagree on suffixes and on 3 versus 4 version parts. | Phase D |

## 5. Pi environment report and benchmark: not yet run

I cannot run these. They need the Raspberry Pi 5 and I have no access to it. The tools are ready and tested for syntax and, for the benchmark, a smoke run on the PC. That PC run was discarded and the script marks any non-Pi result as invalid for Pi reporting.

On the Pi, without touching the install:

```bash
mkdir -p ~/agrilens_tools && cd ~/agrilens_tools      # copy this repo's scripts/ folder here
bash scripts/collect_pi_environment.sh | tee ~/agrilens_env_report.txt

export AGRILENS_APP_PATH=$HOME/AGRILENS_RaspberryPi/main.py
python3 scripts/benchmark_pi5.py \
  --app-path ~/AGRILENS_RaspberryPi/main.py --model ~/AGRILENS_RaspberryPi/agrilens.onnx \
  --labels ~/AGRILENS_RaspberryPi/labels.txt --samples-dir ~/AGRILENS_RaspberryPi/diagnosis_samples \
  --runs 100 --note "kiosk stopped"
# repeat once with the kiosk running, and once with --soak-seconds 1800
```

Please send back `agrilens_env_report.txt` and the `benchmark_*.json` files. The environment report also prints the Pi's two config files, which gives the effective device calibration.

## 6. Exit criteria

| Criterion | Status |
|---|---|
| Tests pass against unmodified legacy code | Done (115 passed) |
| Golden predictions saved | Done |
| `AGRILENS_RaspberryPi/` unchanged | Done (see integrity report) |
| Pi environment report | **Pending, needs the Pi** |
| Pi benchmark | **Pending, needs the Pi** |
| Field-validation tools ready | Done (tooling tested on synthetic data; the camera path is untested until Phase E hardware) |

## 7. Rollback point

- Tag `phase-A` on branch `restructure/v5`. `git switch main` returns to the original repository state at any time, because `main` was not modified.
- Stage 0 backup: `AGRILENS_backup_20261116_175516` holds the three dirty files, a full diff, the original `git status`, HEAD, and SHA-256 of all 82 working-tree files at the start.
- To undo Phase A completely: `git switch main`, then delete the branch and the untracked `.venv` additions if desired. Nothing else was changed.

## 8. Git integrity

See `phase_A_git_integrity.md` in this folder.
