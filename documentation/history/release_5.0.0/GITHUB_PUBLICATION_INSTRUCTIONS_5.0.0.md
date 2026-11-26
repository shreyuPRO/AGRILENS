# Publishing AGRILENS-5.0.0 (to be done only after explicit release approval)

Publishing to `main` updates every deployed kiosk on its next boot. Nothing below has been run.

## What is published

| Item | Value |
|---|---|
| Repository | `https://github.com/faiyaze04/AGRILENS.git`, branch `main` (currently `01059f8`, "Release v4.9.4") |
| Release branch | `release/agrilens-5.0.0` in `D:\AGRILENS_Training\release_5.0.0\AGRILENS` (based on `restructure/v5` `585698f`, tag `phase-A`; `01059f8` is an ancestor) |
| Tag | `AGRILENS-5.0.0` (annotated) |
| Files kiosks download | `AGRILENS_RaspberryPi/` (38 files; `SHA256SUMS` SHA-256 `37fb89c6805e4130cb2e790b9c35b878011ee9029479d2319122fa19bda8229c`) |
| Release record | `deployment/release_manifests/AGRILENS-5.0.0.json` |

## Before publishing

1. Decide on the failed criterion C2 (Mango macro-F1 0.849 against 0.85). Publishing with it requires a recorded waiver; otherwise do not publish.
2. Decide whether Raspberry Pi 5, C270 and expert validation must come first (all pending).
3. Optional: run the Pi benchmark on one Pi with this folder, kiosk stopped:
   `python3 tools/validation/benchmark_pi5.py --app-path ~/AGRILENS_RaspberryPi/main.py --model ~/AGRILENS_RaspberryPi/agrilens.onnx --labels ~/AGRILENS_RaspberryPi/labels.txt --samples-dir ~/AGRILENS_RaspberryPi/diagnosis_samples --runs 100`
4. Optional staged roll-out: create `~/.agrilens_ota_hold` on kiosks that already run 5.0.0+ code. (4.9.4 kiosks ignore it; keep those offline if they must not update.)

## Publish (Windows PowerShell, from the release clone)

The clone's push URL is deliberately disabled. Add a separate remote for GitHub:

```powershell
cd D:\AGRILENS_Training\release_5.0.0\AGRILENS
git remote add github https://github.com/faiyaze04/AGRILENS.git
git fetch github
git log -1 --format=%H github/main          # expect 01059f8... ; if different, stop and rebase the release branch first
$py = "d:\OneDrive - Faiyaz Personal\OneDrive\3. Shreyance related Documents\AgriLens\AGRILENS\.venv\Scripts\python.exe"
powershell -ExecutionPolicy Bypass -File deployment\ota\publish_ota_release.ps1 -ReleaseId AGRILENS-5.0.0 -ModelDir models\candidates\agrilens-multicrop-1.0.0 -Python $py -Remote github
```

The publisher stops at the first failure. It checks the branch and a clean tree, rebuilds `AGRILENS_RaspberryPi/` and requires it to equal the committed folder, verifies `RELEASE_MANIFEST.json` hashes, runs the tests, asks you to type `AGRILENS-5.0.0`, then merges into `main` (`--no-ff`), tags `AGRILENS-5.0.0`, and pushes `main` and the tag to `github`.

Optional GitHub release page (after the push): `gh release create AGRILENS-5.0.0 --title "AGRILENS 5.0.0" --notes-file documentation/release_notes/RELEASE_NOTES_5.0.0.md --prerelease`.

## After publishing

1. On one kiosk: tap ADMIN → ☁ OTA UPDATE (INTERNET); confirm the brand-label tooltip shows `v5.0.0 (AGRILENS-5.0.0)` and `sha256sum agrilens.onnx` is `776d08ac…0332b`.
2. Watch the first kiosks for one day before treating the roll-out as complete.
3. If the release must be withdrawn: `documentation/technical/ROLLBACK.md` (fleet rollback is the prepared release `AGRILENS-5.0.1-rollback`, published the same way).
4. Optionally promote the model: move `models/candidates/agrilens-multicrop-1.0.0/` to `models/production/` and update `models/manifests/MODEL_REGISTRY.json` in a follow-up commit (the device package does not depend on that path).
