# AGL-MULTICROP-MD 1.0.0

The authoritative four-crop master dataset for AGRILENS (Apple, Mango, Potato, Tomato). Created 2026-11-17. Frozen: every file is listed in `FREEZE_CHECKSUMS.sha256`. Never modify a released version; changes produce a new version through `datasets/dataset_tools/` in the AGRILENS repository.

## Contents
| Folder | Content |
|---|---|
| `images/<Crop>/<CLASS>/` | accepted images (26,917 in splits, 412 accepted but kept out of every split) |
| `quarantine/<Crop>/<CLASS>/` | 2,205 images with uncertain labels, provisional classes or mappings, or quality holds; never in a split |
| `supplementary/` | 430 background-removed legacy Mango images; never in a split by default |
| `manifests/` | `image_manifest.csv` (one row per source record, 44,612 rows, including 1,919 rejected and 12,729 augmented records that are not copied), `class_taxonomy.csv/.json`, `quarantine_manifest.csv`, `rejected_manifest.csv` |
| `splits/` | `split_assignment.csv`, `train.csv`, `val.csv`, `test_known_device.csv`, `test_heldout_device.csv` |
| `metadata/` | `statistics.json`, `bias_class_source_device.csv`, `source_archives.json`, `licences.json` |

## Classes (model_index = order of the production labels.txt; train / val / test_known_device / test_heldout_device)
| Class ID | Model index | Name | Sources | Accepted | Leaf groups | Quarantined | Splits | Label confidence |
|---|---|---|---|---|---|---|---|---|
| APL001 | 0 | Apple Rust | PP2020 | 622 | 616 | 0 | 436 / 93 / 93 / 0 | source label, unverified by an expert |
| APL002 | 1 | Apple Scab | PP2020 | 592 | 592 | 0 | 414 / 89 / 89 / 0 | source label, unverified by an expert |
| APL003 | 2 | Apple Healthy | PP2020 | 516 | 504 | 0 | 361 / 78 / 77 / 0 | source label, unverified by an expert |
| MNG001 | 3 | Mango Anthracnose | MANGOLEAFBD;SAR25 | 1357 | 1223 | 102 | 745 / 146 / 145 / 321 | source label, unverified by an expert |
| MNG002 | 4 | Mango Bacterial Canker | ABCGMP;MANGOLEAFBD | 884 | 580 | 41 | 797 / 58 / 29 / 0 | source label; ABCGMP overlaps MangoLeafBD (effectively one session) |
| MNG003 | 5 | Mango Cutting Weevil | MANGOLEAFBD | 500 | 202 | 18 | 426 / 38 / 36 / 0 | source label, single source and essentially one phone |
| MNG004 | 6 | Mango Die Back | MANGOLEAFBD | 448 | 321 | 45 | 344 / 52 / 52 / 0 | source label, single source, leaf-only diagnosis doubtful |
| MNG005 | 7 | Mango Gall Midge | MANGOLEAFBD | 500 | 393 | 984 | 354 / 142 / 4 / 0 | medium: MangoLeafBD labels only; SAR 'Golmichi' mapping provisional and quarantined |
| MNG006 | 8 | Mango Healthy | ABCGMP;MANGOLEAFBD;SAR25 | 1597 | 906 | 1 | 1343 / 117 / 137 / 0 | source label, unverified by an expert |
| MNG007 | 9 | Mango Powdery Mildew | MANGOLEAFBD;SAR25 | 1252 | 617 | 11 | 851 / 228 / 169 / 4 | source label, unverified by an expert |
| MNG008 | 10 | Mango Sooty Mould | MANGOLEAFBD | 500 | 376 | 3 | 384 / 71 / 45 / 0 | source label, single source and one phone |
| POT001 | 11 | Potato Early Blight | PLANTVILLAGE | 1000 | 248 | 0 | 700 / 152 / 148 / 0 | source label, unverified by an expert |
| POT002 | 12 | Potato Late Blight | PLANTVILLAGE | 1000 | 249 | 0 | 700 / 152 / 148 / 0 | source label, unverified by an expert |
| POT003 | 13 | Potato Healthy | PLANTVILLAGE | 152 | 38 | 0 | 104 / 24 / 24 / 0 | source label, unverified by an expert |
| TOM001 | 14 | Tomato Bacterial Spot | PLANTVILLAGE | 2127 | 505 | 0 | 1488 / 320 / 319 / 0 | source label, unverified by an expert |
| TOM002 | 15 | Tomato Early Blight | PLANTVILLAGE | 1000 | 251 | 0 | 700 / 151 / 149 / 0 | source label, unverified by an expert |
| TOM003 | 16 | Tomato Late Blight | PLANTVILLAGE | 1901 | 1188 | 0 | 1331 / 285 / 285 / 0 | source label, unverified by an expert |
| TOM004 | 17 | Tomato Leaf Mould | PLANTVILLAGE | 952 | 238 | 0 | 664 / 144 / 144 / 0 | source label, unverified by an expert |
| TOM005 | 18 | Tomato Septoria Leaf Spot | PLANTVILLAGE | 1771 | 1018 | 0 | 1240 / 266 / 265 / 0 | source label, unverified by an expert |
| TOM006 | 19 | Tomato Spider Mites (Two-spotted) | PLANTVILLAGE | 1676 | 401 | 0 | 1172 / 252 / 252 / 0 | source label, unverified by an expert |
| TOM007 | 20 | Tomato Target Spot | PLANTVILLAGE | 1404 | 1402 | 0 | 983 / 211 / 210 / 0 | source label, unverified by an expert |
| TOM008 | 21 | Tomato Yellow Leaf Curl Virus | PLANTVILLAGE | 3208 | 2218 | 0 | 2246 / 481 / 481 / 0 | source label, unverified by an expert |
| TOM009 | 22 | Tomato Mosaic Virus | PLANTVILLAGE | 373 | 370 | 0 | 261 / 56 / 56 / 0 | source label, unverified by an expert |
| TOM010 | 23 | Tomato Healthy | PLANTVILLAGE | 1585 | 819 | 0 | 1109 / 238 / 238 / 0 | source label, unverified by an expert |
| MNG009 |  | Mango Turning Brown (provisional) | SAR25 | 0 | 0 | 1000 | 0 / 0 / 0 / 0 | provisional; symptom, not a diagnosis; unreviewed |

MNG009 Turning Brown is in the taxonomy but not in the model (provisional class). MNG005 Gall Midge uses MangoLeafBD-labelled images only; the SAR 'Golmichi' images are quarantined until the mapping is reviewed by an expert.

## How groups and splits were made
- Mango: leaf groups, copy groups and capture bursts from AGL-MANGO-MD. The five-class splits of AGL-MANGO-MD v1.1.0-rc1 are inherited unchanged (frozen test tiers keep their meaning). Cutting Weevil, Die Back and Sooty Mould are split with the same rule (seed 42).
- Potato and Tomato (PlantVillage): leaf identity from the public PlantVillage leaf map ({'Potato': 2152, 'Tomato': 10310} images matched) united with perceptual-hash near-duplicate clusters. Potato's 2,152 images come from 535 leaves.
- Apple (Plant Pathology 2020): perceptual-hash near-duplicate clusters.
- Every split unit lies in exactly one split. Leakage checks: {'leaf_group_id': 0, 'copy_group_id': 0, 'split_unit': 0}.
- Exact duplicates: one copy kept per class; cross-class duplicates and cross-class leaf groups are quarantined, never auto-resolved.

## Evaluation tiers
`test_known_device` (all crops) and `test_heldout_device` (Mango only: five SAR phones never seen in training; only Anthracnose now has an adequate sample) are separate tiers and must never be pooled. Apple, Potato and Tomato have no device information, so no device-independence claim is possible for them.

## Known limitations
- Apple, Potato and Tomato come from one source each; PlantVillage images are laboratory photographs on plain backgrounds; there are no field or C270 images in this dataset.
- About 36% of Tomato images have no known leaf identity; undetected same-leaf photographs may remain across splits.
- Mango limitations from AGL-MANGO-MD carry over (device/source bias, single-source classes, unverified labels, ABCGMP overlap with MangoLeafBD).
- Labels are source labels; none has been verified by an expert.
- Licences differ by source (`metadata/licences.json`); MangoLeafBD is non-commercial.

## Use for training
Reference this dataset by version and by the split manifests. Do not copy or edit it. A different sampling strategy is a new experiment manifest, not a new dataset.
