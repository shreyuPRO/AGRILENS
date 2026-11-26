"""
Characterisation of the existing configuration loader (load_kiosk_config / save_kiosk_config).

Verified order, lowest to highest priority:
    code DEFAULT_CONFIG  <  app-dir kiosk_config.json  <  ~/.agrilens_kiosk_config.json (user file)
After merging, values are clamped, then a legacy-reset rule runs (see test_legacy_reset_*).
None of this is changed by the restructuring. These tests fail if it is.
"""
import json
import os

import pytest

import app_harness as H
from conftest import BASELINE_DIR

# Representative device calibration seen in the working-tree kiosk_config.json at Phase A.
DEVICE = {
    "confidence_threshold": 0.4, "ood_margin": 0.12, "ood_logit": 6.0, "sharpness_min": 25.0,
    "cam_contrast": 100, "cam_brightness": 0, "cam_saturation": 100, "cam_sharpness": 100,
    "cam_wb_temp": 0, "cam_zoom": 100, "cam_flip_h": False, "cam_flip_v": False,
    "cam_auto_exp": False, "cam_auto_wb": False, "language": "EN",
}
THRESHOLD_KEYS = ("confidence_threshold", "ood_margin", "ood_logit", "sharpness_min")


def eff(app, repo=None, user=None):
    return H.effective_config(app, repo, user)


def test_code_defaults(app):
    c = eff(app)
    assert (c["confidence_threshold"], c["ood_margin"], c["ood_logit"], c["sharpness_min"]) == (0.40, 0.12, 1.40, 25.0)
    assert c["cam_auto_exp"] is True and c["cam_auto_wb"] is True and c["language"] == "EN"


def test_app_dir_file_overrides_defaults(app):
    c = eff(app, repo=DEVICE)
    assert c["ood_logit"] == 6.0
    assert c["cam_auto_exp"] is False and c["cam_auto_wb"] is False


def test_user_file_overrides_app_dir_file(app):
    # The user file wins. (An earlier discovery note said the opposite; this test is the evidence.)
    assert eff(app, repo=DEVICE, user={"ood_logit": 1.4})["ood_logit"] == 1.4
    assert eff(app, repo={"ood_logit": 1.4}, user=DEVICE)["ood_logit"] == 6.0


def test_keys_missing_from_user_file_come_from_app_dir_file(app):
    c = eff(app, repo=DEVICE, user={"language": "HI"})
    assert c["ood_logit"] == 6.0 and c["language"] == "HI" and c["cam_auto_exp"] is False


def test_device_calibration_is_not_reset(app):
    c = eff(app, repo=DEVICE)
    assert {k: c[k] for k in DEVICE} == DEVICE


# ---- the legacy threshold reset: "if ood_logit >= 1.80 and confidence_threshold >= 0.48" -------------

def test_legacy_reset_triggers_with_device_ood_and_raised_confidence(app):
    c = eff(app, repo=dict(DEVICE, confidence_threshold=0.5))
    assert (c["confidence_threshold"], c["ood_margin"], c["ood_logit"], c["sharpness_min"]) == (0.40, 0.12, 1.40, 25.0)


def test_legacy_reset_boundaries(app):
    reset = eff(app, repo={"ood_logit": 1.8, "confidence_threshold": 0.48})
    assert reset["ood_logit"] == 1.4 and reset["confidence_threshold"] == 0.4
    below_ood = eff(app, repo={"ood_logit": 1.79, "confidence_threshold": 0.48})
    assert below_ood["ood_logit"] == 1.79 and below_ood["confidence_threshold"] == 0.48
    below_conf = eff(app, repo={"ood_logit": 1.8, "confidence_threshold": 0.47})
    assert below_conf["ood_logit"] == 1.8 and below_conf["confidence_threshold"] == 0.47


def test_legacy_reset_only_touches_the_four_threshold_keys(app):
    c = eff(app, repo=dict(DEVICE, confidence_threshold=0.5, ood_margin=0.3, sharpness_min=60.0, cam_zoom=150, language="HI"))
    assert (c["ood_margin"], c["sharpness_min"]) == (0.12, 25.0)  # reset too
    assert c["cam_zoom"] == 150 and c["language"] == "HI"
    assert c["cam_auto_exp"] is False and c["cam_auto_wb"] is False


def test_legacy_reset_applies_to_merged_values_not_per_file(app):
    # ood_logit from the app-dir file and the raised confidence from the user file together trigger it.
    c = eff(app, repo=DEVICE, user={"confidence_threshold": 0.6})
    assert c["ood_logit"] == 1.4 and c["confidence_threshold"] == 0.4


# ---- clamping ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key,given,expected", [
    ("ood_logit", 7.5, 6.5), ("ood_logit", 0.1, 1.0),
    ("confidence_threshold", 0.01, 0.30),
    ("ood_margin", 0.0, 0.10), ("ood_margin", 0.9, 0.60),
    ("sharpness_min", 1, 20.0), ("sharpness_min", 500, 120.0),
    ("cam_contrast", 999, 200), ("cam_contrast", 0, 50),
    ("cam_brightness", 99, 50), ("cam_brightness", -99, -50),
    ("cam_saturation", 999, 200), ("cam_sharpness", 10, 50), ("cam_sharpness", 999, 250),
    ("cam_wb_temp", 99, 50), ("cam_zoom", 50, 100), ("cam_zoom", 999, 200),
])
def test_values_are_clamped(app, key, given, expected):
    # confidence_threshold stays below 0.48 here so the legacy reset cannot mask the clamp.
    base = {"confidence_threshold": 0.4, "ood_logit": 1.4}
    cfg = dict(base, **{key: given})
    assert eff(app, repo=cfg)[key] == expected


def test_confidence_threshold_upper_clamp(app):
    # Reached only when the legacy reset does not fire (ood_logit < 1.8).
    assert eff(app, repo={"confidence_threshold": 0.99, "ood_logit": 1.0})["confidence_threshold"] == 0.95


def test_bad_types_fall_back_to_defaults(app):
    c = eff(app, repo={"ood_logit": "abc", "cam_zoom": None, "cam_flip_h": "yes", "language": "fr"})
    assert c["ood_logit"] == 1.4 and c["cam_zoom"] == 100 and c["cam_flip_h"] is False and c["language"] == "EN"


def test_language_hi_is_case_insensitive(app):
    assert eff(app, repo={"language": "hi"})["language"] == "HI"


def test_corrupt_user_file_is_ignored(app, tmp_path):
    rp, up = tmp_path / "kiosk_config.json", tmp_path / "user.json"
    rp.write_text(json.dumps(DEVICE), encoding="utf-8")
    up.write_text("{ not json", encoding="utf-8")
    old = app.CONFIG_PATH, app.USER_CONFIG_PATH
    app.CONFIG_PATH, app.USER_CONFIG_PATH = str(rp), str(up)
    try:
        assert app.load_kiosk_config()["ood_logit"] == 6.0
    finally:
        app.CONFIG_PATH, app.USER_CONFIG_PATH = old


def test_save_writes_both_files_and_round_trips(app, tmp_path):
    rp, up = tmp_path / "kiosk_config.json", tmp_path / "user.json"
    old = app.CONFIG_PATH, app.USER_CONFIG_PATH
    app.CONFIG_PATH, app.USER_CONFIG_PATH = str(rp), str(up)
    try:
        app.save_kiosk_config(DEVICE)
        assert json.loads(rp.read_text(encoding="utf-8")) == DEVICE
        assert json.loads(up.read_text(encoding="utf-8")) == DEVICE
        assert app.load_kiosk_config() == {**app.DEFAULT_CONFIG, **DEVICE}
    finally:
        app.CONFIG_PATH, app.USER_CONFIG_PATH = old


def test_stored_precedence_matrix_still_matches(app):
    """Regression against tests/baseline/config_precedence_matrix.json (captured from the legacy code)."""
    with open(os.path.join(BASELINE_DIR, "config_precedence_matrix.json"), encoding="utf-8") as f:
        matrix = json.load(f)
    assert matrix["cases"]
    for case in matrix["cases"]:
        # cam_resolution (added in 5.1.0) is not in the legacy matrix; it takes its default unless a file sets it.
        expected = dict(case["effective"])
        expected.setdefault("cam_resolution", app.DEFAULT_CONFIG["cam_resolution"])
        # history_enabled / history_max_images (added in 5.3.0) likewise take their defaults.
        expected.setdefault("history_enabled", app.DEFAULT_CONFIG["history_enabled"])
        expected.setdefault("history_max_images", app.DEFAULT_CONFIG["history_max_images"])
        # history_sync_* (added in 5.4.0) likewise take their defaults.
        for key in ("history_sync_enabled", "history_sync_remote", "history_sync_path", "history_sync_minutes"):
            expected.setdefault(key, app.DEFAULT_CONFIG[key])
        assert eff(app, case["app_dir_file"], case["user_file"]) == expected, case["name"]


# ---- camera capture resolution (5.1.0) -----------------------------------------------------------------

def test_cam_resolution_defaults_to_c270_maximum(app):
    assert eff(app)["cam_resolution"] == "1280x720"
    assert app.parse_camera_resolution(None) == (1280, 720)


@pytest.mark.parametrize("given,expected", [
    ("640x480", "640x480"), ("1280x720", "1280x720"), (" 640X480 ", "640x480"),
    ("1920x1080", "1280x720"), ("abc", "1280x720"), (None, "1280x720"), (720, "1280x720"),
])
def test_cam_resolution_is_validated(app, given, expected):
    assert eff(app, repo={"cam_resolution": given})["cam_resolution"] == expected


def test_user_file_cam_resolution_wins(app):
    assert eff(app, repo={"cam_resolution": "1280x720"}, user={"cam_resolution": "640x480"})["cam_resolution"] == "640x480"
