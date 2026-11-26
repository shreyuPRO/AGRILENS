# Deviation record: release criterion C2, accepted for EXPISCOR 2026 only

| Item | Record |
|---|---|
| Release | AGRILENS 5.0.0 (`AGRILENS-5.0.0`), commit `243fbf5`, model AGRILENS-MULTICROP 1.0.0 (run `multicrop1_R2_s42`, SHA-256 `776d08ac669d0ea8874a458bfb6ea2657c5d40525d30021c7c8c1204d520332b`) |
| Criterion | C2: known-device classification macro-F1 at least 0.85 for each crop (`training/evaluation/RELEASE_EVALUATION_CRITERIA.md`, fixed before testing) |
| Result | Mango 0.849 (Apple 0.945, Potato 0.997, Tomato 0.966). **C2 failed.** C1 and C3–C9 passed. |
| Evidence | `training/evaluation/release_eval_1.0.0/release_evaluation.json` (single run, lock `RELEASE_EVALUATION_RUN_ONCE.json`) |
| Decision | The project owner accepted 5.0.0 with this deviation **for the EXPISCOR 2026 school exhibition demonstration only** (directive of 2026-11-17). |
| Not changed | The test results, the criteria, the model and the gate thresholds are unchanged. C2 remains recorded as failed. No retraining or tuning was done. |
| Scope of the acceptance | Supervised exhibition use. Not commercial use, not field advice, not an OTA release to deployed kiosks, not GitHub publication. |
| Known causes | Mango Die Back recall 0.462 (24 of 52 test images; 20 read as Powdery Mildew, 7 as Gall Midge). Mango Gall Midge F1 0.381 (4 test images, 13 false positives); Gall Midge is also a provisional class. |
| Presentation rule | Do not quote accuracy figures at the exhibition. Present results as a demonstration of the technology, with the on-screen advisory note. |
