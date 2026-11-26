# Rollback (AGRILENS 5.0.0)

There are two kinds of rollback. Pick the one that matches the problem.

| Situation | Use |
|---|---|
| One kiosk misbehaves after updating | Single-device rollback with `rollback.sh` |
| The 5.0.0 release is bad for every kiosk | Fleet rollback: publish the prepared release `AGRILENS-5.0.1-rollback` |

## Why fleet rollback is a new release and not a revert

Every updater (4.9.x and 5.0.0) refuses to install an `APP_VERSION` that is lower than the installed one. Re-publishing 4.9.4 on GitHub `main` would therefore be ignored by kiosks already on 5.0.0. The prepared release in `deployment/rollback/AGRILENS-5.0.1-rollback/` contains the 4.9.4 application code and the 4.9.4 model with only `APP_VERSION` raised to `5.0.1`, so the updaters accept it.

**After 5.1.0 is published:** kiosks on 5.1.0 refuse 5.0.1 as a downgrade, so `AGRILENS-5.0.1-rollback` only reaches kiosks still on 5.0.0. A fleet rollback of 5.1.0 needs a new release numbered above 5.1.0 (for example 5.1.1 built from the 5.0.0 sources, or 5.1.1 with `cam_resolution` defaulting to `640x480`). A single kiosk can return to 5.0.0 with `rollback.sh`, because the 5.0.0 updater keeps `rollback/v5.0.0/` when it installs 5.1.0. To return one kiosk to 640×480 capture without any rollback, set `"cam_resolution": "640x480"` in `~/.agrilens_kiosk_config.json`.

The diagnosis history in `~/AGRILENS_history/` (5.3.0 and later) is outside the application folder: neither OTA updates nor `rollback.sh` change or delete it. A version before 5.3.0 simply stops adding to it. The OneDrive upload (5.4.0 and later) is part of the application: after a rollback to 5.3.0 the uploads stop, the files already in OneDrive stay there, and the rclone sign-in on the Pi is not removed (delete it with `rclone config delete agrilens_onedrive` if wanted).

## Single-device rollback

The 5.0.0 updater copies every file it replaces into `rollback/v<previous version>/` inside the application folder before replacing it. A kiosk updated from 4.9.4 therefore has `rollback/v4.9.4/`.

On the kiosk (keyboard or SSH):

```bash
cd ~/AGRILENS_RaspberryPi
bash rollback.sh            # lists available rollback copies
bash rollback.sh v4.9.4     # restores that copy and creates ~/.agrilens_ota_hold
bash run_agrilens.sh
```

`rollback.sh` refuses to restore a copy whose `main.py` does not compile.

Limitation: the hold file `~/.agrilens_ota_hold` is honoured only by the 5.0.0 and later updaters. A kiosk restored to 4.9.4 runs the 4.9.4 updater on its next boot. That updater ignores the hold and upgrades again while GitHub `main` serves 5.0.0. To keep one kiosk on 4.9.4 while `main` serves 5.0.0, keep it offline. Disabling `agrilens-ota.service` is not enough, because 4.9.4 `main.py` also starts the updater itself on every boot.

To resume updates on a held 5.0.0+ kiosk: `rm ~/.agrilens_ota_hold`.

## Fleet rollback

1. Rebuild and verify the rollback package:
   `python deployment/packaging/build_rollback_release.py` (writes `deployment/rollback/AGRILENS-5.0.1-rollback/` with `SHA256SUMS` and `ROLLBACK_MANIFEST.json`).
2. Copy that folder's contents over `AGRILENS_RaspberryPi/` on a branch, commit, and publish it with `deployment/ota/publish_ota_release.ps1` (release id `AGRILENS-5.0.1-rollback`). The publisher is the only supported way to push to `main`.
3. Kiosks download 5.0.1 on their next boot. Because 5.0.1 contains the 4.9.4 `ota_update.sh`, those kiosks then behave exactly like 4.9.4 kiosks.
4. A later fixed release must use a version above 5.0.1 (for example 5.0.2).

Saved settings after rollback: the 4.9.4 code applies whatever thresholds are saved in `kiosk_config.json` / `~/.agrilens_kiosk_config.json` and ignores the `calibration_model_sha256` tag that 5.0.0 writes. If an operator saved Admin settings while running 5.0.0, those values (calibrated for the 5.0.0 model) will be applied to the 4.9.4 model after rollback. Press **↺ RESET DEFAULTS** in the Admin Console after a rollback, or delete `~/.agrilens_kiosk_config.json`.

## Repository rollback

The complete pre-5.0.0 history is in this repository's git history on GitHub `main` (Release v4.9.4 is commit `01059f8`; the Phase A work is tag `phase-A`, commit `585698f`). The separate backup bundle and working-tree zip in `Release_Evidence` were deleted on 2026-11-19 at the owner's request (CR-0009) after checking that every ref in the bundle is contained in GitHub `main`. The 4.9.4 application files are also kept byte-identical in `tests/regression/baseline/legacy_4.9.4/` and the 4.9.4 model in `models/production/agrilens-24class-4.9.4/`.
