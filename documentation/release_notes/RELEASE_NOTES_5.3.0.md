# AGRILENS 5.3.0 release notes (built, not published)

| Item | Value |
|---|---|
| OTA release id | `AGRILENS-5.3.0` |
| Previous version | 5.2.0 |
| Increment | minor: Diagnosis history: every diagnosis stores the diagnosed leaf image (date-time stamped) and a log record with metadata and status |
| Model | AGRILENS-MULTICROP 1.1.0, unchanged (SHA-256 `0774ca4a…e0f08e`); the kiosk does not download the model again |
| Status | Built on branch `release/agrilens-5.3.0`. Not published, not deployed. |

## What changes for the kiosk

- **Diagnosis history.** Every tap of **DIAGNOSE NOW** stores, in `~/AGRILENS_history/` on the kiosk:
  - `YYYY-MM-DD/YYYYMMDD_HHMMSS_mmm_<VERDICT>.jpg`: the diagnosed (cropped) leaf image, exactly the area the model saw (JPEG quality 92). `<VERDICT>` is `DISEASE`, `HEALTHY`, `LOW_CONFIDENCE` or `UNKNOWN`.
  - `YYYY-MM-DD/YYYYMMDD_HHMMSS_mmm_<VERDICT>.json`: the record of that diagnosis: local and UTC time, status (English), result class, crop and condition, confidence, top-1 probability, margin, maximum logit, second class and the top 3, input mode (LIVE or FILE) and source file, selected crop (AUTO or a crop), crop box and full-frame size, image-quality score and rating, camera description, rejection thresholds and their source, app version and release, model id, version and SHA-256, engine, latency, screen language, host name and save status.
  - `diagnosis_log.csv`: one row per diagnosis with the same fields, for a spreadsheet.
- The history is outside the application folder `~/AGRILENS_RaspberryPi/`, so OTA updates and `rollback.sh` never change or delete it.
- Writing happens on a background thread after the result is shown; it does not slow the diagnosis, and a write error (for example a full disk) is printed to the console and never interrupts the kiosk.
- Storage limits: at most `history_max_images` images (default 5000, about 0.1–0.3 MB each); above it the oldest images and their records are deleted, the CSV log is kept. No image is written while less than 300 MB of disk space is free; the record is still written with `save_status` explaining why.
- New settings `history_enabled` (default `true`) and `history_max_images` (default 5000, 0 = keep everything), validated and saved with the other kiosk settings.
- A language switch after a diagnosis re-draws the result but does not add a second record.

## Tests

- `pytest -q` (Windows, kiosk `.venv`): 207 passed, 0 failed (15 new tests in `tests/unit/test_history.py`: image, record and CSV row written; one header; disabled history writes nothing; pruning of the oldest images; low-disk behaviour; write errors never raise; background write; language-independent verdict codes from the real decision code; record contents for file mode; settings validation and saving; history folder outside the OTA folder).
- End-to-end on the PC with the release model: two sample images diagnosed through the application's classifier and decision code produced `…_DISEASE.jpg/.json`, `…_HEALTHY.jpg/.json` and two CSV rows with the expected values.
- Not tested on the Raspberry Pi 5 (write speed of the SD card, folder permissions).

## Known limitations

- The history stores the cropped leaf only, not the full camera frame (the crop box and frame size are recorded).
- There is no screen in the kiosk to browse or delete the history; copy `~/AGRILENS_history/` to a USB stick or PC.
- All limitations of 5.2.0 remain (model 1.1.0 not validated on live C270 captures; see `RELEASE_NOTES_5.2.0.md`).
