"""Unit tests for the AGRILENS 5.0.0 changes: version identity, model-specific gate calibration, model/label compatibility, OTA file list."""
import os
import re

import pytest

from conftest import ROOT


def test_version_identifiers_are_independent(app):
    # Application version is single-sourced (APP_VERSION, written by agl_governance.py bump); 5.0.0 or later, release id derived from it.
    assert re.fullmatch(r"\d+\.\d+\.\d+", app.APP_VERSION)
    assert tuple(int(x) for x in app.APP_VERSION.split(".")) >= (5, 0, 0)
    assert app.OTA_RELEASE_ID == "AGRILENS-" + app.APP_VERSION
    assert app.MODEL_ID == "AGRILENS-MULTICROP" and re.fullmatch(r"1\.\d+\.\d+", app.MODEL_VERSION)   # same 24-class contract since 1.0.0 (5.2.0: 1.1.0)
    assert app.DATASET_VERSION == "AGL-MULTICROP-MD 1.0.0"
    assert re.fullmatch(r"[0-9a-f]{64}", app.MODEL_SHA256)
    assert app.BUILD_TIMESTAMP not in ("", "UNSET")


def test_calibration_is_used_for_the_release_model_without_saved_settings(app):
    th, src = app.resolve_gate_thresholds({}, app.MODEL_SHA256)
    assert th == {"confidence_threshold": app.MODEL_CALIBRATION_CONFIDENCE, "ood_margin": app.MODEL_CALIBRATION_MARGIN, "ood_logit": app.MODEL_CALIBRATION_OOD_LOGIT}
    assert "calibration" in src


def test_settings_saved_for_another_model_are_ignored(app):
    cfg = {"confidence_threshold": 0.55, "ood_margin": 0.30, "ood_logit": 6.0, "calibration_model_sha256": "0" * 64}
    th, _ = app.resolve_gate_thresholds(cfg, app.MODEL_SHA256)
    assert th["ood_logit"] == app.MODEL_CALIBRATION_OOD_LOGIT


def test_settings_without_model_tag_are_ignored(app):
    th, _ = app.resolve_gate_thresholds({"confidence_threshold": 0.5, "ood_margin": 0.2, "ood_logit": 6.0}, app.MODEL_SHA256)
    assert th["ood_logit"] == app.MODEL_CALIBRATION_OOD_LOGIT


def test_settings_saved_for_this_model_are_honoured_and_clamped(app):
    cfg = {"confidence_threshold": 0.99, "ood_margin": 0.20, "ood_logit": 2.0, "calibration_model_sha256": app.MODEL_SHA256}
    th, src = app.resolve_gate_thresholds(cfg, app.MODEL_SHA256)
    assert th == {"confidence_threshold": 0.95, "ood_margin": 0.20, "ood_logit": 2.0} and src.startswith("saved")


def test_unrecognised_model_gets_generic_defaults(app):
    th, src = app.resolve_gate_thresholds({}, "f" * 64)
    assert th == {"confidence_threshold": app.CONFIDENCE_THRESHOLD, "ood_margin": app.OOD_MARGIN_THRESHOLD, "ood_logit": app.OOD_LOGIT_THRESHOLD}
    assert "not recognised" in src


def test_classifier_reports_release_model_identity(classifier, app):
    assert classifier.model_sha256 == app.MODEL_SHA256
    assert classifier.mode == "ONNX %s %s" % (app.MODEL_ID, app.MODEL_VERSION)


def test_label_count_mismatch_disables_inference(app, ort, tmp_path):
    bad = tmp_path / "labels.txt"
    bad.write_text("\n".join(["Mango_A", "Mango_B", "Mango_C", "Mango_D", "Mango_E"]) + "\n", encoding="utf-8")
    clf = app.Classifier(app.MODEL_PATH, str(bad))
    assert clf.session is None and clf.mode == "DEMO"
    assert "24 classes" in clf.error_reason and "has 5" in clf.error_reason


def test_unrecognised_model_file_is_flagged(app, ort, tmp_path):
    import shutil
    other = tmp_path / "agrilens.onnx"
    shutil.copy(os.path.join(ROOT, "models", "production", "agrilens-24class-4.9.4", "agrilens.onnx"), other)
    clf = app.Classifier(str(other), app.LABELS_PATH)
    assert clf.session is not None and clf.mode == "ONNX (unrecognised model file)"


def test_saved_settings_record_the_model_they_were_calibrated_for():
    src = open(os.path.join(ROOT, "application", "main.py"), encoding="utf-8").read()
    block = src.split("def _save_current_settings(self):", 1)[1].split("save_kiosk_config(cfg)", 1)[0]
    assert '"calibration_model_sha256"' in block


def test_in_app_ota_list_matches_shell_updater_list():
    src = open(os.path.join(ROOT, "application", "main.py"), encoding="utf-8").read()
    in_app = re.findall(r'\("([^"]+)", os\.path\.join\((?:APP_BASE_DIR|LOGOS_DIR)', src.split("ota_files = [", 1)[1].split("]", 1)[0])
    sh = open(os.path.join(ROOT, "deployment", "ota", "ota_update.sh"), encoding="utf-8").read()
    shell = re.findall(r'^\s+"([^"]+)",$', sh.split("files = [", 1)[1].split("]", 1)[0], re.M)
    assert in_app == shell and "rollback.sh" in shell


def test_in_app_ota_compiles_main_before_replacing_the_model():
    src = open(os.path.join(ROOT, "application", "main.py"), encoding="utf-8").read()
    worker = src.split("def ota_worker():", 1)[1].split("threading.Thread(target=ota_worker", 1)[0]
    assert worker.index("main.py.ota_check") < worker.index("model_url = ")
    assert worker.count("backup_for_rollback(") >= 3   # definition + model + other files


def _release_model_dir():
    """The models/ folder whose MODEL_MANIFEST.json carries the MODEL_SHA256 of application/main.py (the model the release ships)."""
    import json
    src = open(os.path.join(ROOT, "application", "main.py"), encoding="utf-8").read()
    want = re.search(r'^MODEL_SHA256 = "([0-9a-f]{64})"', src, re.M).group(1)
    for kind in ("candidates", "production"):
        base = os.path.join(ROOT, "models", kind)
        for d in sorted(os.listdir(base)):
            man = os.path.join(base, d, "MODEL_MANIFEST.json")
            if os.path.isfile(man) and json.load(open(man, encoding="utf-8")).get("sha256") == want:
                return os.path.join(base, d)
    raise AssertionError("no model folder in models/ matches MODEL_SHA256 " + want)

@pytest.mark.parametrize("name", ["main.py", "labels.txt", "agrilens.onnx"])
def test_device_package_is_generated_from_the_sources(name):
    import hashlib
    h = lambda p: hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n") if not p.endswith(".onnx") else open(p, "rb").read()).hexdigest()   # package text files are LF
    model_dir = _release_model_dir()
    src = {"main.py": os.path.join(ROOT, "application", "main.py"), "labels.txt": os.path.join(model_dir, "labels.txt"),
           "agrilens.onnx": os.path.join(model_dir, "agrilens.onnx")}[name]
    assert h(os.path.join(ROOT, "AGRILENS_RaspberryPi", name)) == h(src)
