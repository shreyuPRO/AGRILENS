# AGRILENS 5.4.0 release notes (built, not published)

| Item | Value |
|---|---|
| OTA release id | `AGRILENS-5.4.0` |
| Previous version | 5.3.0 |
| Increment | minor: Diagnosis history upload to OneDrive with rclone copy every 30 minutes when the internet is available |
| Model | AGRILENS-MULTICROP 1.1.0, unchanged; the kiosk does not download the model again |
| Status | Built on branch `release/agrilens-5.4.0`. Not published, not deployed. |

## What changes for the kiosk

- **History upload to OneDrive.** A background task in the kiosk uploads `~/AGRILENS_history/` (leaf images, records and `diagnosis_log.csv` from 5.3.0) to a OneDrive folder:
  - first attempt about 2 minutes after the kiosk starts, then every 30 minutes (`history_sync_minutes`);
  - each attempt first checks that Microsoft's servers are reachable; without internet it is skipped and the next attempt catches up;
  - it runs `rclone copy`: new and changed files are uploaded, **nothing is ever deleted in OneDrive**, so images the kiosk removes at its 5000-image limit stay in OneDrive;
  - files younger than 20 seconds are left for the next attempt, so a diagnosis being written is never uploaded half-finished;
  - one line per attempt in `~/AGRILENS_history_sync.log` (kept to the last 1000 lines); errors never interrupt the kiosk.
- **Nothing happens until the one-time setup is done**: install rclone, create the rclone remote `agrilens_onedrive` with your OneDrive sign-in, and set `history_sync_path` to the destination folder (device guide, section "Diagnosis history upload to OneDrive"). The sign-in is stored by rclone in `~/.config/rclone/rclone.conf`; the kiosk application never stores or reads credentials.
- New settings `history_sync_enabled` (default `true`), `history_sync_remote` (default `agrilens_onedrive`), `history_sync_path` (default `AGRILENS_Kiosk_History`) and `history_sync_minutes` (default 30, 5 to 1440), validated and saved with the other kiosk settings.
- The upload is part of the kiosk program, so it needs no extra script, timer or cron entry and arrives with the normal OTA update.

## Tests

- `pytest -q` (Windows, kiosk `.venv`): 219 passed, 0 failed (12 new tests in `tests/unit/test_history_sync.py`: copy command never syncs or deletes; offline attempts skipped; nothing without rclone or without the remote; rclone failure reported; disabled; no history folder; errors never raise; log trimming; interval bound; settings validation and saving; no credentials in the application).
- End-to-end on the PC with the real rclone 1.76 and a local folder standing in for OneDrive: the first attempt uploaded 2 images, 2 records and the CSV; a file younger than 20 s was left for the next attempt and uploaded by it; an image deleted locally stayed in the destination; an unconfigured remote did nothing.
- Not tested: the real OneDrive sign-in (it needs your Microsoft account) and the Raspberry Pi 5.

## Known limitations

- The OneDrive sign-in stored by rclone can read and write the whole OneDrive, not only the destination folder. If the Pi is lost, remove the app's access in the Microsoft account or change the password.
- Some organisations require an administrator to approve the rclone app before the first sign-in.
- `diagnosis_log.csv` is uploaded again in full whenever it changes (it is small).
- The kiosk shows no upload status on screen; check `~/AGRILENS_history_sync.log`.
