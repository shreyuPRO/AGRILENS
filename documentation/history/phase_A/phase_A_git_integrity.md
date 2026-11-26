# Git integrity report

- Branch: `restructure/v5`  HEAD `b7b246ba2c`
- Commits on branch beyond `main`: 3
  - b7b246b Phase A: Raspberry Pi diagnostics, field-validation tools and git integrity report
  - 7a7ee48 Phase A: regression test suite and behavioural baselines for the unmodified application
  - 5a31061 Phase A: test tooling configuration (pytest/ruff settings, dev requirements, ignore rules)

| Check | Result | Detail |
|---|---|---|
| main branch unchanged | PASS | 01059f8c73 == original 01059f8c73 |
| origin/main unchanged (nothing pushed) | PASS | 01059f8c73 |
| no remote branch for the work branch | PASS | restructure/v5 |
| every pre-existing file is byte-identical (or a pure move) | PASS | 82 files compared, 0 moved, 1 approved edits ['.gitignore'], unexpected changes=[] missing=[] |
| pre-existing uncommitted changes still present and uncommitted | PASS | 12 of 12 still show as changed; lost=[] |
| nothing staged right now | PASS | staged=[] |
| no pre-existing uncommitted path was committed | PASS | leaked=[] |
| deleted documentation files were not restored | PASS | 9 entries remain deleted |
| AGRILENS_RaspberryPi/ untouched in commits | PASS | changes=[] |

## Working tree now

- Uncommitted tracked changes: 13 (12 pre-existing + any listed below)
- Untracked (new, not yet committed): 4
  - `docs/field_validation_protocol.md`
  - `docs/phase_reports/phase_A.md`
  - `docs/phase_reports/phase_A_git_integrity.md`
  - `docs/phase_reports/phase_A_test_results.txt`

## Pre-existing changes (must remain exactly as they were)

- `AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md` M
- `AGRILENS_RaspberryPi/kiosk_config.json` M
- `AGRILENS_RaspberryPi/labels.txt` M
- `Documentation_and_References/7inch HDMI LCD (H) drawing/f16-2.dwg` D
- `Documentation_and_References/7inch HDMI LCD (H) drawing/f16-2.prt.36` D
- `Documentation_and_References/7inch HDMI LCD (H) drawing/f16-2.stp` D
- `Documentation_and_References/C270 cover.stl` D
- `Documentation_and_References/C270 focus ring.stl` D
- `Documentation_and_References/MOBILENET V2 TRAINED 97.78 PERCENT/agri_lens_labels.json` D
- `Documentation_and_References/MOBILENET V2 TRAINED 97.78 PERCENT/run_20_agri_lens.py` D
- `Documentation_and_References/README.md` D
- `Documentation_and_References/REVISION.md` D
