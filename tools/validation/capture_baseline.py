#!/usr/bin/env python3
"""
Capture the behavioural baseline of the CURRENT AGRILENS application.

Writes (under tests/baseline/):
  golden_predictions.json       probabilities, raw logits and verdicts for each sample image
  config_precedence_matrix.json effective configuration for a fixed set of input-file cases
  legacy_ota_surface.json       git blob ids and SHA-256 of every file the deployed OTA downloads

Run it only against an application version you consider correct. It reads the application and
never edits it. The goldens exist to prove that later restructuring changed no behaviour. They
are NOT an accuracy measurement: there is one image per class.

Usage:
  python scripts/capture_baseline.py            # uses AGRILENS_APP_PATH or the legacy main.py
  python scripts/capture_baseline.py --check    # compare with the stored files, write nothing
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app_harness as H  # noqa: E402

BASELINE_DIR = os.environ.get("AGRILENS_BASELINE_DIR", os.path.join(H.REPO_ROOT, "tests", "regression", "baseline"))

# Files the deployed (v4.9.x) OTA downloads from main/AGRILENS_RaspberryPi/ (see ota_update.sh and
# AgriLensApp._trigger_ota_update). They must keep serving identical content until the device is migrated.
LEGACY_OTA_FILES = [
    "main.py", "labels.txt", "agrilens.onnx", "logos/agrilens_logo.jpg", "logos/gundecha_logo.png",
    "HOW_TO_RUN_ON_RASPBERRY_PI.md", "setup_rpi.sh", "run_agrilens.sh", "ota_update.sh", "setup_remote_ota.sh",
]

# Device calibration seen in the working-tree kiosk_config.json at Phase A (representative, not a default).
DEVICE_CALIBRATION = {
    "confidence_threshold": 0.4, "ood_margin": 0.12, "ood_logit": 6.0, "sharpness_min": 25.0,
    "cam_contrast": 100, "cam_brightness": 0, "cam_saturation": 100, "cam_sharpness": 100,
    "cam_wb_temp": 0, "cam_zoom": 100, "cam_flip_h": False, "cam_flip_v": False,
    "cam_auto_exp": False, "cam_auto_wb": False, "language": "EN",
}

CONFIG_CASES = [
    ("no_files", None, None),
    ("app_dir_only_device_calibration", DEVICE_CALIBRATION, None),
    ("user_overrides_app_dir_1.4", DEVICE_CALIBRATION, {"ood_logit": 1.4}),
    ("user_overrides_app_dir_6.0", {"ood_logit": 1.4}, DEVICE_CALIBRATION),
    ("user_file_without_key_keeps_app_dir", DEVICE_CALIBRATION, {"language": "HI"}),
    ("reset_trap_ood6.0_conf0.50", dict(DEVICE_CALIBRATION, confidence_threshold=0.5), None),
    ("reset_boundary_ood1.80_conf0.48", {"ood_logit": 1.8, "confidence_threshold": 0.48}, None),
    ("reset_just_below_ood1.79_conf0.48", {"ood_logit": 1.79, "confidence_threshold": 0.48}, None),
    ("reset_just_below_ood1.80_conf0.47", {"ood_logit": 1.8, "confidence_threshold": 0.47}, None),
    ("clamp_high", {"ood_logit": 7.5, "confidence_threshold": 0.99, "ood_margin": 0.9, "sharpness_min": 500}, None),
    ("clamp_low", {"ood_logit": 0.1, "confidence_threshold": 0.01, "ood_margin": 0.0, "sharpness_min": 1}, None),
    ("bad_types_fall_back", {"ood_logit": "abc", "cam_zoom": None, "cam_flip_h": "yes", "language": "fr"}, None),
]


def git(*args):
    return subprocess.run(["git", *args], cwd=H.REPO_ROOT, capture_output=True, check=True).stdout


def env_info(app):
    info = {"python": sys.version.split()[0], "platform": platform.platform(), "app_version": getattr(app, "APP_VERSION", None),
            "app_path": os.path.relpath(H.app_path(), H.REPO_ROOT)}
    for mod in ("onnxruntime", "numpy", "PIL", "cv2"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:
            info[mod] = None
    try:
        info["git_head"] = git("rev-parse", "HEAD").decode().strip()
    except Exception:
        info["git_head"] = None
    return info


def build_predictions(app):
    from PIL import Image
    clf = app.Classifier(app.MODEL_PATH, app.LABELS_PATH)
    if clf.session is None:
        raise SystemExit("Classifier is in DEMO mode: %s" % clf.error_reason)
    with open(app.MODEL_PATH, "rb") as f:
        model_sha = hashlib.sha256(f.read()).hexdigest()
    rows = []
    for label, path in H.sample_images():
        img = Image.open(path).convert("RGB")
        probs, _ms, raw = clf.predict(img)
        top = max(range(len(probs)), key=lambda i: probs[i])
        row = {
            "file": os.path.basename(path), "filename_label": label, "image_size": list(img.size),
            "probs": [float(p) for p in probs], "raw_logits": [float(x) for x in raw],
            "top1_index": top, "top1_label": clf.labels[top], "top1_prob": float(probs[top]),
            "top1_matches_filename": clf.labels[top] == label,
        }
        for prof in H.PROFILES:
            d = H.decide(app, clf.labels, probs, raw, profile=prof)
            row["verdict_" + prof] = d["verdict"]
        rows.append(row)
    return {
        "note": "Regression baseline, NOT an accuracy measurement (one image per class). Whole image, no crop.",
        "environment": env_info(app), "model_sha256": model_sha, "labels": clf.labels,
        "profiles": H.PROFILES, "samples": rows,
    }


def build_config_matrix(app):
    out = {"note": "Effective config from the application's own load_kiosk_config(). Later source wins: "
                   "code defaults < app-dir kiosk_config.json < ~/.agrilens_kiosk_config.json.",
           "cases": []}
    for name, repo_cfg, user_cfg in CONFIG_CASES:
        out["cases"].append({"name": name, "app_dir_file": repo_cfg, "user_file": user_cfg,
                             "effective": H.effective_config(app, repo_cfg, user_cfg)})
    return out


def build_ota_surface():
    surface = {}
    for rel in LEGACY_OTA_FILES:
        spec = "HEAD:AGRILENS_RaspberryPi/" + rel
        blob_id = git("rev-parse", spec).decode().strip()
        content = git("cat-file", "blob", blob_id)
        surface[rel] = {"git_blob": blob_id, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    return {"note": "What the deployed OTA fetches from main/AGRILENS_RaspberryPi/ (committed blobs, not the working tree). "
                    "These must not change before the device is migrated.",
            "files": surface}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare to stored baselines instead of writing")
    ap.add_argument("--only", choices=["predictions", "config", "ota"], help="limit to one baseline")
    a = ap.parse_args()
    app = H.load_app()
    builders = {
        "predictions": ("golden_predictions.json", lambda: build_predictions(app)),
        "config": ("config_precedence_matrix.json", lambda: build_config_matrix(app)),
        "ota": ("legacy_ota_surface.json", build_ota_surface),
    }
    os.makedirs(BASELINE_DIR, exist_ok=True)
    status = 0
    for key, (fname, fn) in builders.items():
        if a.only and a.only != key:
            continue
        data = fn()
        path = os.path.join(BASELINE_DIR, fname)
        if a.check:
            stored = json.load(open(path, encoding="utf-8"))
            same = json.dumps(stored.get("samples", stored.get("cases", stored.get("files"))), sort_keys=True) == \
                json.dumps(data.get("samples", data.get("cases", data.get("files"))), sort_keys=True)
            print("%-34s %s" % (fname, "MATCH" if same else "DIFFERS"))
            status |= 0 if same else 1
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, indent=2, sort_keys=False)
                f.write("\n")
            print("wrote", os.path.relpath(path, H.REPO_ROOT))
    return status


if __name__ == "__main__":
    sys.exit(main())
