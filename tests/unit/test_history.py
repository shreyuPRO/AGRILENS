"""Diagnosis history (5.3.0): every diagnosis stores the diagnosed leaf image and a record outside the application folder."""
import csv
import glob
import json
import os
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import app_harness as H


def _leaf(w=120, h=80):
    return Image.new("RGB", (w, h), (60, 140, 50))


def _meta(**kw):
    m = {"verdict": "DISEASE", "status": "MANGO DIE BACK DETECTED", "result": "Mango_Die_Back", "crop": "Mango", "condition": "Die Back",
         "confidence_pct": 91.2, "input_mode": "LIVE", "app_version": "5.3.0", "model_version": "1.1.0"}
    m.update(kw)
    return m


def _csv_rows(base):
    with open(os.path.join(base, "diagnosis_log.csv"), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_record_writes_image_record_and_log_row(app, tmp_path):
    hist = app.DiagnosisHistory(str(tmp_path), enabled=True, max_images=0)
    rid = hist.record(_leaf(), _meta(), wait=True)
    assert rid and hist.last_error == ""
    imgs = glob.glob(os.path.join(str(tmp_path), "????-??-??", f"{rid}_DISEASE.jpg"))
    assert len(imgs) == 1 and Image.open(imgs[0]).size == (120, 80)
    rec = json.load(open(imgs[0][:-4] + ".json", encoding="utf-8"))
    assert rec["record_id"] == rid and rec["save_status"] == "saved" and rec["result"] == "Mango_Die_Back"
    assert rec["image_file"].endswith(f"{rid}_DISEASE.jpg") and rec["timestamp_local"] and rec["timestamp_utc"].endswith("Z")
    assert (rec["image_width"], rec["image_height"]) == (120, 80)
    rows = _csv_rows(str(tmp_path))
    assert len(rows) == 1 and rows[0]["record_id"] == rid and rows[0]["verdict"] == "DISEASE" and rows[0]["status"] == "MANGO DIE BACK DETECTED"
    assert list(rows[0].keys()) == app.DiagnosisHistory.CSV_FIELDS


def test_log_appends_one_row_per_diagnosis_with_a_single_header(app, tmp_path):
    hist = app.DiagnosisHistory(str(tmp_path), max_images=0)
    for v in ("HEALTHY", "UNKNOWN", "LOW_CONFIDENCE"):
        hist.record(_leaf(), _meta(verdict=v), wait=True)
    rows = _csv_rows(str(tmp_path))
    assert [r["verdict"] for r in rows] == ["HEALTHY", "UNKNOWN", "LOW_CONFIDENCE"]
    assert open(os.path.join(str(tmp_path), "diagnosis_log.csv"), encoding="utf-8-sig").read().count("record_id,") == 1


def test_disabled_history_writes_nothing(app, tmp_path):
    hist = app.DiagnosisHistory(str(tmp_path / "h"), enabled=False)
    assert hist.record(_leaf(), _meta(), wait=True) is None
    assert not (tmp_path / "h").exists()


def test_oldest_images_are_pruned_above_the_limit(app, tmp_path):
    hist = app.DiagnosisHistory(str(tmp_path), max_images=3)
    day = tmp_path / "2026-11-01"
    day.mkdir()
    for i in range(5):   # pre-existing older history
        (day / f"20261101_10000{i}_000_HEALTHY.jpg").write_bytes(b"x")
        (day / f"20261101_10000{i}_000_HEALTHY.json").write_text("{}")
    hist.record(_leaf(), _meta(), wait=True)   # first save triggers pruning
    left = sorted(os.path.basename(p) for p in glob.glob(os.path.join(str(tmp_path), "????-??-??", "*.jpg")))
    assert len(left) == 3 and "20261101_100000_000_HEALTHY.jpg" not in left
    assert not (day / "20261101_100000_000_HEALTHY.json").exists()   # record removed with its image
    assert len(_csv_rows(str(tmp_path))) == 1                          # the log itself is never pruned


def test_low_disk_space_keeps_the_record_but_not_the_image(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app, "HISTORY_MIN_FREE_MB", 10 ** 12)
    hist = app.DiagnosisHistory(str(tmp_path), max_images=0)
    rid = hist.record(_leaf(), _meta(), wait=True)
    assert not glob.glob(os.path.join(str(tmp_path), "????-??-??", "*.jpg"))
    rec = json.load(open(glob.glob(os.path.join(str(tmp_path), "????-??-??", f"{rid}_*.json"))[0], encoding="utf-8"))
    assert rec["save_status"].startswith("image not saved") and rec["image_file"] == ""


def test_write_errors_never_raise(app, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    hist = app.DiagnosisHistory(str(blocker / "sub"), max_images=0)
    hist.record(_leaf(), _meta(), wait=True)
    assert hist.last_error


def test_background_write_completes(app, tmp_path):
    hist = app.DiagnosisHistory(str(tmp_path), max_images=0)
    hist.record(_leaf(), _meta())
    import time
    for _ in range(100):
        if os.path.exists(os.path.join(str(tmp_path), "diagnosis_log.csv")):
            break
        time.sleep(0.05)
    assert len(_csv_rows(str(tmp_path))) == 1


@pytest.mark.parametrize("lang", ["EN", "HI"])
def test_render_records_a_language_independent_verdict(app, labels, lang, monkeypatch):
    k = labels.index("Mango_Die_Back")
    raw = np.full(len(labels), -2.0)
    raw[k] = 6.0
    probs = np.exp(raw) / np.exp(raw).sum()
    out = H.decide(app, labels, list(probs), raw, profile="code_defaults")
    v = out["last_verdict"]
    assert v["verdict"] == "DISEASE" and v["result"] == "Mango_Die_Back" and v["status"] == "DIE BACK DETECTED"
    assert v["confidence_pct"] > 90 and v["max_logit"] == 6.0 and v["top3"][0]["label"] == "Mango_Die_Back" and v["selected_crop"] == "AUTO"


@pytest.mark.parametrize("raw_top,verdict", [(6.0, "HEALTHY"), (0.5, "UNKNOWN")])
def test_render_verdict_codes(app, labels, raw_top, verdict):
    k = labels.index("Mango_Healthy")
    raw = np.full(len(labels), -2.0)
    raw[k] = raw_top
    probs = np.exp(raw) / np.exp(raw).sum()
    assert H.decide(app, labels, list(probs), raw, profile="code_defaults")["last_verdict"]["verdict"] == verdict


def test_record_history_builds_the_full_record(app):
    calls = []
    fake = SimpleNamespace(
        history=SimpleNamespace(enabled=True, record=lambda img, meta: calls.append((img, meta))),
        last_verdict={"verdict": "HEALTHY", "status": "HEALTHY LEAF - NO DISEASE", "result": "Tomato_healthy"},
        _is_live_mode=lambda: False, captured_frame=_leaf(640, 480), classifier=SimpleNamespace(model_sha256="ab" * 32, mode="ONNX AGRILENS-MULTICROP 1.1.0"),
        camera=SimpleNamespace(kind="USB Camera (Port 0, V4L2, 1280x720)"), last_file_path="/home/pi/leaf.jpg", gate_source="calibration", lang="HI",
    )
    app.AgriLensApp._record_history(fake, _leaf(), (10, 20, 130, 100), 81, "Good", 133.4)
    assert len(calls) == 1
    meta = calls[0][1]
    assert meta["verdict"] == "HEALTHY" and meta["input_mode"] == "FILE" and meta["source_file"] == "/home/pi/leaf.jpg" and meta["camera"] == ""
    assert meta["crop_box"] == "10,20,130,100" and (meta["frame_width"], meta["frame_height"]) == (640, 480)
    assert meta["quality_score"] == 81 and meta["latency_ms"] == 133.4 and meta["language"] == "HI"
    assert meta["app_version"] == app.APP_VERSION and meta["model_version"] == app.MODEL_VERSION and meta["model_sha256"] == "ab" * 32


def test_record_history_is_skipped_without_a_verdict(app):
    calls = []
    fake = SimpleNamespace(history=SimpleNamespace(enabled=True, record=lambda *a: calls.append(a)), last_verdict=None)
    app.AgriLensApp._record_history(fake, _leaf(), (0, 0, 1, 1), 0, "", 0)
    assert calls == []


def test_history_settings_are_validated_and_saved():
    import app_harness
    app = app_harness.load_app()
    c = H.effective_config(app)
    assert c["history_enabled"] is True and c["history_max_images"] == 5000
    c = H.effective_config(app, repo_cfg={"history_enabled": "no", "history_max_images": -5})
    assert c["history_enabled"] is True and c["history_max_images"] == 0
    assert H.effective_config(app, repo_cfg={"history_enabled": False, "history_max_images": 10 ** 9})["history_max_images"] == 100000
    src = open(os.path.join(H.REPO_ROOT, "application", "main.py"), encoding="utf-8").read()
    block = src.split("def _save_current_settings(self):", 1)[1].split("save_kiosk_config(cfg)", 1)[0]
    assert '"history_enabled"' in block and '"history_max_images"' in block


def test_history_folder_is_outside_the_ota_folder(app):
    assert os.path.normcase(os.path.abspath(app.HISTORY_DIR)) != os.path.normcase(os.path.abspath(app.APP_BASE_DIR))
    assert not os.path.normcase(os.path.abspath(app.HISTORY_DIR)).startswith(os.path.normcase(os.path.abspath(app.APP_BASE_DIR)) + os.sep)
