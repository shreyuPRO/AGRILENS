# AGRILENS OTA publisher (replaces the 4.9.4 push_ota_update.bat, which ran "git add -A" and pushed without any check).
# PUBLISHING CHANGES EVERY DEPLOYED KIOSK ON ITS NEXT BOOT. Run only after the release has been explicitly approved for publication.
# What it does, in order, stopping at the first failure:
#   1. verifies you are on the release branch with a clean working tree;
#   2. rebuilds AGRILENS_RaspberryPi/ with deployment/packaging/build_device_package.py and checks it reproduces the committed folder exactly;
#   3. verifies RELEASE_MANIFEST.json and SHA256SUMS against the files;
#   4. runs the test suite;
#   5. asks you to type the release identifier;
#   6. merges the release branch into main, tags it, and pushes main and the tag to origin.
# Usage (from the repository root):  powershell -ExecutionPolicy Bypass -File deployment\ota\publish_ota_release.ps1 -ReleaseId AGRILENS-5.0.0 -ModelDir models\candidates\agrilens-multicrop-1.0.0 -Python <python with onnxruntime, cv2, pytest> -Remote github
param([Parameter(Mandatory=$true)][string]$ReleaseId, [Parameter(Mandatory=$true)][string]$ModelDir, [string]$ReleaseBranch = 'release/agrilens-5.0.0', [string]$Python = 'python', [string]$Remote = 'origin')
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent; Set-Location $root
if ((git branch --show-current) -ne $ReleaseBranch) { throw "Not on $ReleaseBranch" }
if (git status --porcelain) { throw 'Working tree is not clean' }
& $Python deployment\packaging\build_device_package.py --model-dir $ModelDir; if ($LASTEXITCODE) { throw 'package build refused' }
if (git status --porcelain -- AGRILENS_RaspberryPi) { throw 'Rebuilt AGRILENS_RaspberryPi/ differs from the committed folder: commit the build first' }
$man = Get-Content AGRILENS_RaspberryPi\RELEASE_MANIFEST.json -Raw | ConvertFrom-Json
if ($man.release -ne $ReleaseId) { throw "Manifest release $($man.release) is not $ReleaseId" }
foreach ($p in $man.files_sha256.PSObject.Properties) { if ((Get-FileHash ("AGRILENS_RaspberryPi\" + $p.Name)).Hash.ToLower() -ne $p.Value) { throw "hash mismatch: $($p.Name)" } }
& $Python -m pytest; if ($LASTEXITCODE) { throw 'tests failed' }
Write-Host "Release $ReleaseId : app $($man.app_version), model $($man.model_id) $($man.model_version) ($($man.model_sha256))"
Write-Host 'Publishing makes every deployed kiosk download this release on its next boot.'
$typed = Read-Host "Type the release identifier ($ReleaseId) to publish, anything else to abort"
if ($typed -ne $ReleaseId) { Write-Host 'Aborted. Nothing was published.'; exit 1 }
git fetch $Remote main; if ($LASTEXITCODE) { throw "cannot fetch $Remote/main" }
git merge-base --is-ancestor "$Remote/main" $ReleaseBranch; if ($LASTEXITCODE) { throw "$Remote/main has commits that are not in $ReleaseBranch; rebase the release first" }
git checkout -B main "$Remote/main"; git merge --no-ff $ReleaseBranch -m "Release $ReleaseId"; if ($LASTEXITCODE) { throw 'merge failed' }
git tag -a $ReleaseId -m "AGRILENS $ReleaseId"
git push $Remote main; git push $Remote $ReleaseId
Write-Host "Published $ReleaseId."
