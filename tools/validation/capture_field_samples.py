#!/usr/bin/env python3
"""
Capture field-validation images with the real AGRILENS camera (Logitech C270 in the enclosure).

For every capture it stores
  frames/<id>.png   the ORIGINAL frame exactly as the kiosk would hold it (after the camera's ISP
                    settings from the effective device config), lossless
  crops/<id>.png    the crop that is passed to the classifier
  field_samples.csv one row per capture: id, time, true_class, source, lighting, crop box, ...
  session_<session>_device_config.json  the effective configuration used (thresholds + camera)

Stop the kiosk first: only one program can hold the camera.
It reads the application and its configuration but changes neither. It pushes the same camera
hardware settings the kiosk applies at start-up (auto exposure / white balance via V4L2).

Ground truth: --true-class must be one of the 24 labels, or Out_of_scope for non-target leaves,
hands, background and so on. Run one session per class and source so records stay clean.

  source = real_leaf | phone_screen | printed
Results are always reported per source and never mixed.

Crop selection mirrors the kiosk: press SPACE to capture, then drag a box (ENTER accepts,
ESC or C uses the default 14% inset the kiosk proposes). The kiosk's own crop handles cannot be
recorded without changing the application, so this tool reproduces that step and stores the box.
Use --no-preview for unattended captures with the default inset.

Examples
  python3 scripts/capture_field_samples.py --session s01 --source real_leaf --true-class Tomato_Late_blight --lighting daylight
  python3 scripts/capture_field_samples.py --session s02 --source phone_screen --true-class Out_of_scope --no-preview --count 10 --interval 2
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app_harness as H  # noqa: E402

SOURCES = ("real_leaf", "phone_screen", "printed")
OUT_OF_SCOPE = "Out_of_scope"
CSV_FIELDS = ["id", "timestamp_utc", "session", "true_class", "source", "lighting", "frame_file", "crop_file",
              "frame_w", "frame_h", "crop_x0", "crop_y0", "crop_x1", "crop_y1", "crop_mode", "camera",
              "app_version", "note"]


def default_inset_box(w, h, inset=0.14, minimum=16):
    """The kiosk proposes a crop inset by 14% on each side (see AgriLensApp._init_crop_selection)."""
    px, py = max(minimum, int(round(w * inset))), max(minimum, int(round(h * inset)))
    return (px, py, w - px, h - py)


def clamp_box(box, w, h):
    """Same bounds rules as AgriLensApp._get_crop_pixel_bounds (at least 16 px, inside the frame)."""
    x0, y0, x1, y1 = box
    x0 = max(0, min(w - 16, int(x0)))
    y0 = max(0, min(h - 16, int(y0)))
    x1 = max(x0 + 16, min(w, int(x1)))
    y1 = max(y0 + 16, min(h, int(y1)))
    return (x0, y0, x1, y1)


def next_index(out_dir, session):
    path = os.path.join(out_dir, "field_samples.csv")
    if not os.path.exists(path):
        return 1
    with open(path, newline="", encoding="utf-8") as f:
        return 1 + sum(1 for r in csv.DictReader(f) if r["session"] == session)


def save_capture(out_dir, frame, box, meta):
    """Persist one capture. `frame` is a PIL RGB image, `box` the crop in frame pixels."""
    os.makedirs(os.path.join(out_dir, "frames"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "crops"), exist_ok=True)
    w, h = frame.size
    box = clamp_box(box, w, h)
    cid = "%s_%04d" % (meta["session"], meta["seq"])
    frame_file, crop_file = "frames/%s.png" % cid, "crops/%s.png" % cid
    frame.save(os.path.join(out_dir, frame_file), format="PNG")
    frame.crop(box).save(os.path.join(out_dir, crop_file), format="PNG")
    row = {"id": cid, "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "session": meta["session"], "true_class": meta["true_class"], "source": meta["source"],
           "lighting": meta.get("lighting", ""), "frame_file": frame_file, "crop_file": crop_file,
           "frame_w": w, "frame_h": h, "crop_x0": box[0], "crop_y0": box[1], "crop_x1": box[2], "crop_y1": box[3],
           "crop_mode": meta["crop_mode"], "camera": meta.get("camera", ""), "app_version": meta.get("app_version", ""),
           "note": meta.get("note", "")}
    path = os.path.join(out_dir, "field_samples.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            wr.writeheader()
        wr.writerow(row)
    return row


def validate_args(a, labels):
    if a.source not in SOURCES:
        raise SystemExit("--source must be one of %s" % ", ".join(SOURCES))
    if a.true_class != OUT_OF_SCOPE and a.true_class not in labels:
        raise SystemExit("--true-class must be %s or one of: %s" % (OUT_OF_SCOPE, ", ".join(labels)))


def build_camera(app, cfg):
    cam = app.Camera(auto_detect=False)
    for key, attr, cast in [("cam_contrast", "contrast", int), ("cam_brightness", "brightness", int),
                            ("cam_saturation", "saturation", int), ("cam_sharpness", "sharpness", int),
                            ("cam_wb_temp", "wb_temp", int), ("cam_zoom", "zoom", int),
                            ("cam_flip_h", "flip_h", bool), ("cam_flip_v", "flip_v", bool),
                            ("cam_auto_exp", "auto_exp", bool), ("cam_auto_wb", "auto_wb", bool)]:
        setattr(cam, attr, cast(cfg.get(key, getattr(cam, attr))))
    ok, msg = cam.detect_webcam()
    if not ok:
        raise SystemExit("Camera not available: %s" % msg)
    time.sleep(1.0)  # let auto exposure settle, as the kiosk's warm-up does
    return cam


def run_interactive(cam, a, app, out_dir):
    import cv2
    import numpy as np
    seq = next_index(out_dir, a.session)
    print("SPACE = capture   Q = quit.  Saved so far this session: %d" % (seq - 1))
    while True:
        frame = cam.read()
        if frame is None:
            time.sleep(0.03)
            continue
        view = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
        cv2.putText(view, "%s | %s | %s | #%d  SPACE=capture Q=quit" % (a.session, a.source, a.true_class, seq),
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
        cv2.imshow("AGRILENS field capture", view)
        k = cv2.waitKey(30) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == 32:
            still = frame.copy()
            bgr = cv2.cvtColor(np.asarray(still), cv2.COLOR_RGB2BGR)
            x, y, w, h = cv2.selectROI("AGRILENS field capture", bgr, showCrosshair=False)
            if w >= 16 and h >= 16:
                box, mode = (x, y, x + w, y + h), "manual"
            else:
                box, mode = default_inset_box(*still.size), "default_inset14pct"
            row = save_capture(out_dir, still, box, {
                "session": a.session, "seq": seq, "true_class": a.true_class, "source": a.source,
                "lighting": a.lighting, "crop_mode": mode, "camera": cam.kind, "app_version": app.APP_VERSION, "note": a.note})
            print("saved %s crop=%s (%s)" % (row["id"], box, mode))
            seq += 1
    cv2.destroyAllWindows()


def run_unattended(cam, a, app, out_dir):
    seq = next_index(out_dir, a.session)
    for _ in range(a.count):
        frame = cam.read()
        tries = 0
        while frame is None and tries < 50:
            time.sleep(0.05)
            frame = cam.read()
            tries += 1
        if frame is None:
            print("no frame; stopping")
            break
        row = save_capture(out_dir, frame, default_inset_box(*frame.size), {
            "session": a.session, "seq": seq, "true_class": a.true_class, "source": a.source, "lighting": a.lighting,
            "crop_mode": "default_inset14pct", "camera": cam.kind, "app_version": app.APP_VERSION, "note": a.note})
        print("saved", row["id"])
        seq += 1
        time.sleep(a.interval)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(H.REPO_ROOT, "field_validation"))
    ap.add_argument("--session", required=True, help="short id, e.g. s01")
    ap.add_argument("--source", required=True, choices=SOURCES)
    ap.add_argument("--true-class", required=True)
    ap.add_argument("--lighting", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--interval", type=float, default=2.0)
    a = ap.parse_args()

    app = H.load_app()
    with open(app.LABELS_PATH, encoding="utf-8") as f:
        labels = [ln.strip() for ln in f if ln.strip()]
    validate_args(a, labels)
    os.makedirs(a.out, exist_ok=True)
    cfg = app.load_kiosk_config()
    cam = build_camera(app, cfg)
    try:
        with open(os.path.join(a.out, "session_%s_device_config.json" % a.session), "w", encoding="utf-8") as f:
            json.dump({"effective_config": cfg, "camera": cam.kind, "app_version": app.APP_VERSION,
                       "model_sha256": app.MODEL_SHA256, "captured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, f, indent=2)
        (run_unattended if a.no_preview else run_interactive)(cam, a, app, a.out)
    finally:
        cam.close()


if __name__ == "__main__":
    main()
