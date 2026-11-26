# AGRILENS-MULTICROP 1.0.0: release evaluation criteria (fixed before calibration and before any test tier is read)

Written while the training runs were in progress, before any model was selected, calibrated or tested. Not to be changed after results are seen. A failed criterion is reported as a failure; the release recommendation states it. Thresholds, sampling and models are not tuned on test data.

## Inference path
Every test result is produced through the application's own six-view `Classifier.predict` and decision code (`application/main.py` of the release, imported read-only), with the frozen release gates. Single-view figures are reported alongside for reference.

## Tiers (never pooled)
| Tier | Data |
|---|---|
| Known-device test | `splits/test_known_device.csv`, all four crops |
| Held-out-device test | `splits/test_heldout_device.csv`, Mango Anthracnose only (five SAR phones never seen in training) |
| Unsupported images | evaluation half of the release OOD set (`training/evaluation/ood_v2`): synthetic, sample photographs, background-only windows, Mango Turning Brown (informational) |
| Comparison | the 4.9.4 production model through the same path and with its own gates, on the same images |

## Criteria
| ID | Criterion | Limit |
|---|---|---|
| C1 | Known-device classification macro-F1 (24 classes) | at least 0.90 |
| C2 | Known-device classification macro-F1 per crop | at least 0.85 for each crop |
| C3 | Held-out-device Anthracnose recall (classification) | at least 0.80 |
| C4 | Images the production model was not trained on (SAR and ABCGMP images of both test tiers): accuracy of the release model minus accuracy of the production model | at least 0 (95% interval of the paired difference reported) |
| C5 | False rejection (rejected although the argmax is correct), known-device, per crop | at most 5% for each crop |
| C6 | False rejection, held-out-device | at most 10% |
| C7 | For every class: decision-level recall at least classification recall minus 0.10 (known-device; held-out-device for Anthracnose) | all classes |
| C8 | Non-leaf images (synthetic, photographs, background-only) accepted | at most 35%; background-only reported separately |
| C9 | ONNX against PyTorch on 256 validation images | maximum absolute logit difference at most 1e-3, argmax agreement 100% |

Informational (no pass/fail): Turning Brown acceptance, per-device and per-source accuracy, confidence and margin of errors, cross-crop confusions, latency on the desktop (not the Pi).

## What the criteria cannot show
No C270 or field data exists; Apple, Potato and Tomato come from one source each with no device information; the production model was most probably trained on the MangoLeafBD and PlantVillage images, so comparisons on those images favour it and are reported but not used for C4.
