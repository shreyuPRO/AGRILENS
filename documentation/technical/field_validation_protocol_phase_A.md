# Field validation protocol (pilot)

Status: current procedure for Logitech C270 accuracy validation (written in Phase A; paths updated 2026-11-18 for the 5.0.0 layout, where the tools live in `tools/validation/`). Not yet carried out on the exhibition hardware.

Purpose: measure how the **unchanged** AGRILENS model and decision logic behave on real Logitech C270 captures taken inside the AGRILENS enclosure. This is **accuracy validation**. It is separate from the Raspberry Pi performance benchmark (`tools/validation/benchmark_pi5.py`), which measures speed, CPU, memory and temperature and says nothing about accuracy.

Rules for this exercise:

- The model, labels, preprocessing and thresholds are not changed. Results are reported, not tuned.
- Real-leaf, phone-screen and printed-image results are always reported separately and never pooled.
- Every capture keeps the original frame and the exact crop used for inference.
- The 24 images in `application/diagnosis_samples/` (shipped as `AGRILENS_RaspberryPi/diagnosis_samples/`) are regression fixtures. One image per class cannot support an accuracy claim.

## 1. Pilot scope

Start small, then expand once capture quality and ground-truth availability are known.

| Item | Pilot target | Expansion |
|---|---|---|
| Classes | as many of the 24 as you can source with confirmed ground truth | all 24 |
| Images per class and source | 5 to 10 | 30 or more per class for useful intervals |
| Out-of-scope images (`Out_of_scope`) | 20 to 30: other leaves, hands, soil, background, blank enclosure | 100 |
| Sources | `real_leaf` first; `phone_screen` and `printed` as available | all three |

With 5 to 10 images per class the 95% intervals are very wide. The report prints them and flags pilot-size data. Do not quote a single accuracy number from the pilot.

## 2. Ground truth

- The true class is decided before capture and by someone able to confirm it (agronomist, labelled plant, or the label of the source image for phone/print).
- Use exactly the 24 label names from `AGRILENS_RaspberryPi/labels.txt` (the labels of the installed model), or `Out_of_scope`.
- A leaf that is uncertain or shows two conditions is not captured as in-scope. Record it as a note or leave it out.

## 3. Capture conditions

Keep these constant within a session and record what changes between sessions.

- Same Pi, same C270, same enclosure, same camera settings (the tool copies the effective device configuration into `session_<id>_device_config.json`).
- Lighting: record it (`--lighting daylight|enclosure_led|dim`).
- Phone-screen images: record the phone and brightness in `--note`. Print images: record paper type.
- Do not retouch images. Do not delete captures that look bad; mark them in the notes instead, so failures are visible.

## 4. How to capture (on the Pi)

1. Until the new runtime is installed, the tools run beside the existing install without touching it. Copy only the `tools/validation/` folder to the Pi (for example to `~/agrilens_tools/scripts`) and point the tools at the installed app:

```bash
export AGRILENS_APP_PATH=$HOME/AGRILENS_RaspberryPi/main.py
export AGRILENS_SAMPLES_DIR=$HOME/AGRILENS_RaspberryPi/diagnosis_samples   # only needed by the benchmark/test tools
cd ~/agrilens_tools
```

2. Stop the kiosk (only one program can use the camera): close AGRILENS from Admin, or `pkill -f main.py`.
3. For each class and source, one session:

```bash
python3 scripts/capture_field_samples.py --session s01 --source real_leaf \
    --true-class Tomato_Late_blight --lighting enclosure_led --note "plant A, leaf 3"
# SPACE = capture, then drag a crop box (ENTER accepts, ESC uses the default 14% inset), Q = quit
```

Out-of-scope examples: `--true-class Out_of_scope`. Unattended batch: add `--no-preview --count 10 --interval 2` (default inset crop).

Output goes to `field_validation/` (git-ignored, so images are not committed):

```
field_validation/
  frames/<id>.png                  original frame, lossless
  crops/<id>.png                   exact crop passed to the classifier
  field_samples.csv                id, class, source, lighting, crop box, camera, app version, note
  session_<id>_device_config.json  effective thresholds and camera settings used
```

The kiosk's own touchscreen crop handles cannot be recorded without changing the application. The tool reproduces the same step (a drag box, or the kiosk's default 14% inset) and stores the box. If you want the touchscreen crop recorded exactly, that is a change request for a later phase.

## 5. Evaluate

```bash
python3 scripts/evaluate_field_validation.py --dir field_validation
```

Writes `field_validation_report.md` and `field_validation_results.csv`. The evaluation re-applies each stored crop box to the stored frame, checks it matches the stored crop, runs `Classifier.predict`, and applies the application's own decision code with the thresholds recorded in each session (so a unit calibrated with `ood_logit = 6.0` is evaluated with 6.0).

Measures per source: top-1 correct before rejection; accepted by the decision gate; accepted and correct; accepted but wrong; rejected as low confidence; rejected as unknown (out-of-distribution gate); out-of-scope rejection and false acceptance; per-class table; Wilson 95% intervals.

The `ood_logit` sensitivity table shows what other settings would have done on the same images. It is information for a later, separately approved decision. This work does not change any threshold.

## 6. What the pilot can and cannot tell us

It can show: whether real C270 frames in the enclosure clear the rejection gates of the installed version (5.0.0: `ood_logit` 2.10 from the model calibration; 4.9.4 units were often calibrated to 6.0), which classes are confused, whether phone-screen images behave differently from real leaves, and whether capture quality is good enough to expand.

It cannot show: population accuracy, performance on leaves from other regions or seasons, or a threshold recommendation. Those need the expanded dataset.
