# Documentation audit, 2026-11-18

Scope: every tracked documentation file (Markdown, text, CSV records, JSON result records, CAD drawings) on branch `governance/engineering-controls`, based on `9017320` (AGRILENS 5.0.0 as published). No PDF or Word files are tracked (`*.pdf` is git-ignored). Method: read each document, check its status statements against the repository and the 2026-11-17 publication, and check references with `agl_governance.py check --full`.

Classification: **KEEP** authoritative and useful; **MERGE** content duplicated elsewhere; **ARCHIVE** historically useful, no longer current; **DELETE** redundant or misleading. Release records, evaluation results, dataset provenance, rollback records and licences are kept regardless of age.

## Register

| Document | Class | Reason | Action taken |
|---|---|---|---|
| `README.md` | KEEP | Project overview | Status corrected (published 2026-11-17), version marker added; its documentation table moved into the `HOW_TO.md` index (MERGE of the table only) |
| `HOW_TO.md` | KEEP (new) | Required central navigation guide with checked index | Created |
| `documentation/technical/INSTALLATION.md` | KEEP | Canonical installation | Section A no longer says "after publication"; section D referred to a tag `AGRILENS-5.0.0` that was never created, now names commit `9017320` |
| `documentation/technical/ARCHITECTURE.md` | KEEP | Canonical architecture and OTA design | Added the single-source version rule and the recorded publication deviation |
| `documentation/technical/ROLLBACK.md` | KEEP | Canonical rollback | No change needed; its "while `main` serves 5.0.0" statements are now the actual situation |
| `documentation/technical/TRAINING.md` | KEEP | Canonical training and evaluation | No change; contains machine-specific dataset paths (`D:\AGRILENS_Training\...`) on purpose, because the dataset lives outside git |
| `documentation/technical/CONFIGURATION.md` | KEEP (new) | No configuration guide existed; keys, ranges, precedence and threshold selection were only in code | Created from `application/main.py` |
| `documentation/technical/field_validation_protocol_phase_A.md` | KEEP | Still the C270 accuracy-validation procedure | Stale paths fixed (`scripts/` → `tools/validation/`, `models/class_labels.txt`, `test_samples/`), gate statement updated for 5.0.0, status line added. File name kept so existing references stay valid |
| `deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md` | KEEP | Device guide, shipped to kiosks by OTA | Not changed: any change is a shipped change and needs an application version increment. Open item 2 below |
| `AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md`, `deployment/rollback/AGRILENS-5.0.1-rollback/HOW_TO_RUN_ON_RASPBERRY_PI.md` | KEEP | Generated and frozen copies of the device guide (duplicates by design: OTA folder and rollback release) | None |
| `AGRILENS_RaspberryPi/README_GENERATED.md` | KEEP | Marks the generated folder | None |
| `documentation/release_notes/RELEASE_NOTES_5.0.0.md` | KEEP | Canonical release notes | Title and status corrected; dated sections added for the publication, the retention decision, the effect on the exhibition kit and the 2026-11-18 field observation |
| `documentation/release_notes/AGRILENS_5.0.0_RELEASE_READINESS_REPORT.md` | KEEP (record) | Dated release record | Not edited (records are not rewritten); superseded statements ("not published") are corrected in the release notes and `CR-0001` |
| `documentation/release_notes/C2_DEVIATION_EXHIBITION_ACCEPTANCE.md` | KEEP (record) | Decision record | None |
| `documentation/release_notes/EXHIBITION_READINESS_REPORT_5.0.0.md` | KEEP (record) | Dated report | Not edited; its "GitHub `main` still serves 4.9.4" is superseded (open item 1) |
| `documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv`, `REPOSITORY_CHANGE_LOG_5.0.0.csv` | KEEP (record) | Change records of the 5.0.0 restructure | None. `REPOSITORY_CHANGE_LOG_5.0.0.csv` has a UTF-8 BOM; kept byte-for-byte and listed in `bom_exceptions` |
| `documentation/release_notes/GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md` | ARCHIVE | Planned procedure; the release was published differently | Moved to `documentation/history/release_5.0.0/`; the reusable part (publisher script) is described in `ARCHITECTURE.md` |
| `documentation/technical/phase_A_reports/phase_A.md`, `phase_A_git_integrity.md`, `phase_A_test_results.txt` | ARCHIVE | Phase A evidence; superseded by the 5.0.0 layout (they cite `docs/` and `scripts/` paths that no longer exist) | Moved to `documentation/history/phase_A/` unchanged. `phase_A_test_results.txt` has a BOM; kept byte-for-byte (`bom_exceptions`) |
| `documentation/history/README_4.9.x.md`, `REVISION_HISTORY_to_4.9.4.md` | KEEP (history) | Version history up to 4.9.4 | Not edited; their links to `REVISION.md` and `../MobileV4/` are broken historical links |
| `documentation/CHANGE_REGISTER.md` | KEEP (new) | Required change register | Created with `CR-0001` (5.0.0 publication) and `CR-0002` (this work) |
| `documentation/governance/ENGINEERING_GOVERNANCE.md` | KEEP (new) | Versioning, hooks, quality gate, documentation rules | Created |
| `documentation/exhibition/desktop_check_results.json`, `gui_check_results.json` | KEEP (record) | Exhibition desktop check results | None |
| `deployment/exhibition/README_KIT.md`, `EXHIBITION_TEST_CHECKLIST.md` | KEEP (release-specific) | Shipped inside the checksummed exhibition kit | Not edited (open item 1) |
| `datasets/master/AGL-MULTICROP-MD/DATASET_CARD.md` and manifests | KEEP (provenance) | Frozen dataset record | None |
| `training/evaluation/RELEASE_EVALUATION_CRITERIA.md`, `training/configurations/SELECTION_RULE.md` | KEEP (record) | Pre-declared criteria and selection rule | None |
| `training/reports/agrilens-multicrop-1.0.0/EXPERIMENT_REGISTER.md` and JSON reports | KEEP (record) | Training evidence for the release model | None |
| `training/experiments/EXPERIMENT_REGISTER_mango5_exp001.md`, `training/experiments/mango5_exp001/reports/*` | KEEP (record) | Experimental Mango model evidence; `PROPOSALS.md` is clearly marked "prepared, not executed" | None |
| `models/manifests/MODEL_REGISTRY.json` | KEEP | Model status registry | Roles corrected: release model published 2026-11-17; 4.9.4 model is the previous production model and fleet rollback target |
| `models/candidates/agrilens-multicrop-1.0.0/MODEL_MANIFEST.json` | KEEP (record) | Export record written by `training/scripts/export_onnx.py`; referenced by the release record | Not edited; its status "not deployed" describes the export date |
| `documentation/hardware/*.stl`, `7inch_HDMI_LCD_H_drawing/*` | KEEP | Enclosure and display drawings | `f16-2.prt.36` (32 MB) looks like a CAD revision file next to the `.dwg` and `.stp` of the same part: review proposed, no action |
| `archive/legacy_tools/push_ota_update_4.9.4.bat` | DELETE (proposed, not done) | Retired publisher that ran `git add -A` and pushed without checks; running it by mistake would publish an unchecked tree to every kiosk | Awaiting approval. History stays in git; `ARCHITECTURE.md` already records why it was retired |
| `archive/legacy_mobilenet_v2_97.78/*` | KEEP (archive) | Legacy experiment | None |

## Conflicting or outdated instructions found

1. **Exhibition kit versus the published release.** `deployment/exhibition/README_KIT.md`, the message at the end of `pi_restore_previous.sh` ("GitHub main still serves 4.9.4, so nothing changes") and `EXHIBITION_READINESS_REPORT_5.0.0.md` assume `main` serves 4.9.4. Since 2026-11-17 a kiosk restored to 4.9.4 that goes online updates itself to 5.0.0. The kit files are checksummed release artefacts and were not edited; the warning is in `RELEASE_NOTES_5.0.0.md`, `HOW_TO.md` (Rollback) and `ROLLBACK.md`. Open item: correct the kit text and script message in the next kit revision.
2. **Device guide, Admin access.** `HOW_TO_RUN_ON_RASPBERRY_PI.md` says Admin opens directly ("password lock is disabled") and, under Troubleshooting, "ADMIN (`PIN: AGRILENS`)". Open item for the next application release (shipped file).
3. **"Not published" statements** in `README.md`, `INSTALLATION.md`, `RELEASE_NOTES_5.0.0.md` and `MODEL_REGISTRY.json`: corrected.
4. **Publication procedure** (`GITHUB_PUBLICATION_INSTRUCTIONS_5.0.0.md`) said nothing had been run and that publication would use the publisher and a tag. Archived; the actual publication is `CR-0001`.
5. **Stale paths** in the field-validation protocol: corrected.

## Not found

No duplicate training guides (one `TRAINING.md`), no abandoned plans outside clearly labelled experiment folders, no empty documents, no documents describing a future version, no secrets in documentation. Reference checks of all current documents pass after the changes above (`agl_governance.py check --full`).
