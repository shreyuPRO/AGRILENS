# AGRILENS 5.0.0 repository restructure (run once, in the release clone, on branch release/agrilens-5.0.0).
# Every action is appended to documentation/release_notes/REPOSITORY_CHANGE_LOG_5.0.0.csv. Removed files stay recoverable from git history (tag phase-A, commit 585698f)
# and from the baseline bundle D:\AGRILENS_Training\release_5.0.0\baseline_4.9.4\AGRILENS_all_refs.bundle.
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent; Set-Location $root
if ((git branch --show-current) -ne 'release/agrilens-5.0.0') { throw 'wrong branch' }
$log = Join-Path $root 'documentation\release_notes\REPOSITORY_CHANGE_LOG_5.0.0.csv'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
if (-not (Test-Path $log)) { 'action,from,to,reason' | Set-Content $log -Encoding utf8 }
function Write-ChangeLog($a, $f, $t, $r) { ('"{0}","{1}","{2}","{3}"' -f $a, $f, $t, ($r -replace '"', "'")) | Add-Content $log -Encoding utf8 }
function Invoke-RepoMove($f, $t, $r) { New-Item -ItemType Directory -Force (Split-Path $t) | Out-Null; git mv -- $f $t; Write-ChangeLog 'moved' $f $t $r }
function Invoke-RepoCopy($f, $t, $r) { New-Item -ItemType Directory -Force (Split-Path $t) | Out-Null; Copy-Item -LiteralPath $f -Destination $t -Recurse -Force; git add -- $t; Write-ChangeLog 'copied' $f $t $r }
function Invoke-RepoRemove($f, $r) { git rm -r -q -- $f; Write-ChangeLog 'removed' $f '' $r }

# 1. One authoritative application source (MobileV4 was the edit location; AGRILENS_RaspberryPi was a copy made by push_ota_update.bat)
Invoke-RepoMove 'MobileV4/main.py' 'application/main.py' 'authoritative application source (MobileV4/main.py and AGRILENS_RaspberryPi/main.py were byte-identical)'
Invoke-RepoMove 'MobileV4/diagnosis_samples' 'application/diagnosis_samples' 'sample images used by the file-diagnosis workflow (identical in both app folders)'
Invoke-RepoMove 'MobileV4/logos' 'application/logos' 'logos read from <app dir>/logos by find_logo_file (identical in both app folders)'
Invoke-RepoCopy 'AGRILENS_RaspberryPi/requirements.txt' 'application/requirements.txt' 'device runtime dependencies (identical to MobileV4 copy)'
Invoke-RepoCopy 'AGRILENS_RaspberryPi/test_deps.py' 'application/test_deps.py' 'dependency check helper shipped to the device'
New-Item -ItemType Directory -Force 'application/configuration' | Out-Null
cmd /c 'git show HEAD:AGRILENS_RaspberryPi/kiosk_config.json > application\configuration\kiosk_config.default.json'   # cmd redirect keeps the blob bytes (a PowerShell pipe re-encodes and adds a BOM); git add 'application/configuration/kiosk_config.default.json'
Write-ChangeLog 'copied' 'HEAD:AGRILENS_RaspberryPi/kiosk_config.json' 'application/configuration/kiosk_config.default.json' 'committed default configuration; the uncommitted device calibration (ood_logit 6.0) in the original working tree is not taken over'

# 2. Production model 4.9.4 preserved for rollback and comparison
Invoke-RepoMove 'MobileV4/agrilens.onnx' 'models/production/agrilens-24class-4.9.4/agrilens.onnx' 'production model 4.9.4 (sha256 0b5bb7fb...ff80), preserved unchanged'
Invoke-RepoMove 'MobileV4/labels.txt' 'models/production/agrilens-24class-4.9.4/labels.txt' 'production labels 4.9.4 (content identical to AGRILENS_RaspberryPi/labels.txt)'

# 3. Deployment sources (the device-facing AGRILENS_RaspberryPi/ folder becomes a generated publication directory)
Invoke-RepoCopy 'AGRILENS_RaspberryPi/ota_update.sh' 'deployment/ota/ota_update.sh' 'source of the device OTA updater (newer than the MobileV4 copy)'
Invoke-RepoCopy 'AGRILENS_RaspberryPi/setup_rpi.sh' 'deployment/raspberry_pi/setup_rpi.sh' 'device setup script source'
Invoke-RepoCopy 'AGRILENS_RaspberryPi/run_agrilens.sh' 'deployment/raspberry_pi/run_agrilens.sh' 'device launcher source'
Invoke-RepoCopy 'AGRILENS_RaspberryPi/setup_remote_ota.sh' 'deployment/raspberry_pi/setup_remote_ota.sh' 'remote OTA provisioning source'
cmd /c 'git show HEAD:AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md > deployment\raspberry_pi\HOW_TO_RUN_ON_RASPBERRY_PI.md'; git add 'deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md'
Write-ChangeLog 'copied' 'HEAD:AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md' 'deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md' 'device guide source (committed version)'

# 4. Superseded duplicates in MobileV4 (older copies of the AGRILENS_RaspberryPi files)
foreach ($f in 'HOW_TO_RUN_ON_RASPBERRY_PI.md','kiosk_config.json','ota_update.sh','requirements.txt','run_agrilens.sh','setup_remote_ota.sh') { Invoke-RepoRemove "MobileV4/$f" "older or identical duplicate of AGRILENS_RaspberryPi/$f; superseded by the deployment/ sources" }
Invoke-RepoMove 'MobileV4/run_agrilens_py313.bat' 'tools/development/run_agrilens_windows_py313.bat' 'Windows development launcher'
Invoke-RepoMove 'MobileV4/Training_Scripts' 'training/legacy_4.9.4' 'training scripts of the 4.9.4 production model (kept for reproducibility of the baseline)'

# 5. Duplicate top-level logos (identical to application/logos)
Invoke-RepoRemove 'logos' 'byte-identical duplicate of application/logos'

# 6. Documentation
Invoke-RepoMove 'docs/phase_reports' 'documentation/technical/phase_A_reports' 'Phase A reports'
Invoke-RepoMove 'docs/field_validation_protocol.md' 'documentation/technical/field_validation_protocol_phase_A.md' 'Phase A field validation protocol (superseded by the C270 protocol; kept for history)'
Invoke-RepoMove 'Documentation_and_References/README.md' 'documentation/history/README_4.9.x.md' '4.9.x project README (history)'
Invoke-RepoMove 'Documentation_and_References/REVISION.md' 'documentation/history/REVISION_HISTORY_to_4.9.4.md' 'revision history up to 4.9.4'
Invoke-RepoMove 'Documentation_and_References/7inch HDMI LCD (H) drawing' 'documentation/hardware/7inch_HDMI_LCD_H_drawing' 'display CAD drawings (enclosure maintenance); NOTE: deleted but uncommitted in the original working tree - kept here pending owner decision'
Invoke-RepoMove 'Documentation_and_References/C270 cover.stl' 'documentation/hardware/C270_cover.stl' 'C270 cover model (enclosure); same note'
Invoke-RepoMove 'Documentation_and_References/C270 focus ring.stl' 'documentation/hardware/C270_focus_ring.stl' 'C270 focus ring model (enclosure); same note'
Invoke-RepoMove 'Documentation_and_References/MOBILENET V2 TRAINED 97.78 PERCENT' 'archive/legacy_mobilenet_v2_97.78' 'obsolete MobileNet V2 experiment notes (archive)'

# 7. Tools and tests
foreach ($f in 'app_harness.py','benchmark_pi5.py','capture_baseline.py','capture_field_samples.py','collect_pi_environment.sh','evaluate_field_validation.py','git_integrity_report.py') { Invoke-RepoMove "scripts/$f" "tools/validation/$f" 'validation and diagnostics tool (Phase A)' }
Invoke-RepoMove 'tests/baseline' 'tests/regression/baseline' 'behavioural baselines of production 4.9.4'
foreach ($f in 'test_camera.py','test_classifier.py','test_configuration.py','test_decision_rules.py','test_field_validation_tools.py','test_label_mapping.py','test_legacy_ota_surface.py') { Invoke-RepoMove "tests/$f" "tests/regression/$f" 'Phase A regression test' }

# 8. OTA publisher: the 4.9.4 script committed and pushed everything with git add -A and no checks
Invoke-RepoMove 'push_ota_update.bat' 'archive/legacy_tools/push_ota_update_4.9.4.bat' 'replaced by deployment/ota/publish_ota_release.ps1 (verified, explicit-confirmation publisher)'
'restructure complete'
