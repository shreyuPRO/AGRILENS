#!/usr/bin/env python3
"""Compare two models (normally the released model and a candidate) through the APPLICATION's own six-view path and gate rules.
Each model is judged with its own calibrated gates (FROZEN_GATE_CALIBRATION.json from calibrate_gates.py). Read-only: nothing in the dataset,
the application or the frozen 1.0.0 release evaluation is changed, and the 1.0.0 run-once lock is not touched.

Sets (reported separately, never pooled):
  val                  validation split (used for selection, so not an independent test)
  val_c270_proxy       the validation images degraded with four fixed, seeded "C270-like" capture profiles (colour cast, exposure, wash-out,
                       noise, low detail, JPEG). SIMULATED: it is related to the candidate's training augmentation, so it favours that model.
  test_known_device    frozen test tier (all crops)
  test_heldout_device  frozen test tier (Mango, phones never seen in training)
  ood_eval             evaluation half of the unsupported-image set ood_v2 (should be rejected)
Run with the application's Python (numpy, Pillow, onnxruntime, cv2):
  python compare_models.py --app-main application/main.py --dataset <root> --cache <cache> --ood <ood_v2>
      --a-name 1.0.0 --a-model <onnx> --a-labels <txt> --a-gates <json> --b-name 1.1.0 --b-model ... --b-labels ... --b-gates ... --out <dir> [--limit N]"""
import argparse, csv, json, os, sys, time
import numpy as np
from PIL import Image, ImageFilter
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kiosk_path as K

ap = argparse.ArgumentParser()
for n in ("app-main", "dataset", "cache", "ood", "out"): ap.add_argument("--" + n, required=True)
for m in ("a", "b"):
    for n in ("name", "model", "labels", "gates"): ap.add_argument(f"--{m}-{n}", required=True)
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

PROFILES = [  # fixed C270-like capture profiles (proxy, not real C270 images)
    {"name": "warm_overexposed", "r": 1.08, "b": 0.90, "gain": 1.30, "gamma": 1.00, "wash": 0.15, "noise": 4.0, "down": 0.50, "blur": 0.0, "jpeg": 55},
    {"name": "cool_dim", "r": 0.92, "b": 1.10, "gain": 0.80, "gamma": 1.15, "wash": 0.00, "noise": 6.0, "down": 0.60, "blur": 0.0, "jpeg": 60},
    {"name": "washed_out", "r": 1.00, "b": 1.00, "gain": 1.15, "gamma": 0.90, "wash": 0.30, "noise": 3.0, "down": 0.45, "blur": 0.0, "jpeg": 50},
    {"name": "soft_focus", "r": 1.03, "b": 0.97, "gain": 1.05, "gamma": 1.00, "wash": 0.05, "noise": 5.0, "down": 1.00, "blur": 1.2, "jpeg": 45},
]


def c270_proxy(img, i):
    p = PROFILES[i % len(PROFILES)]; rng = np.random.default_rng(10_000 + i)
    x = np.asarray(img, dtype=np.float32).copy(); x[..., 0] *= p["r"]; x[..., 2] *= p["b"]
    x = 255.0 * np.clip(x * p["gain"] / 255.0, 0, 1) ** p["gamma"]; x = x * (1 - p["wash"]) + 238.0 * p["wash"]
    x = x + rng.normal(0, p["noise"], x.shape); im = Image.fromarray(np.clip(x, 0, 255).astype(np.uint8))
    if p["down"] < 1.0:
        W, H = im.size; im = im.resize((max(16, int(W * p["down"])), max(16, int(H * p["down"]))), Image.BILINEAR).resize((W, H), Image.BILINEAR)
    if p["blur"] > 0: im = im.filter(ImageFilter.GaussianBlur(p["blur"]))
    import io
    b = io.BytesIO(); im.save(b, "JPEG", quality=p["jpeg"]); b.seek(0); return Image.open(b).convert("RGB")


rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
splits = {s: rd(os.path.join(a.dataset, "splits", f"{s}.csv")) for s in ("val", "test_known_device", "test_heldout_device")}
ood = [r for r in rd(os.path.join(a.ood, "ood_v2_manifest.csv")) if r["split"] == "evaluation"]
if a.limit:
    splits = {k: v[:a.limit] for k, v in splits.items()}; ood = ood[:a.limit]
cache_img = lambda iid: Image.fromarray(np.load(os.path.join(a.cache, iid + ".npy")))
SETS = [("val", splits["val"], lambda r, i: cache_img(r["image_id"])),
        ("val_c270_proxy", splits["val"], lambda r, i: c270_proxy(cache_img(r["image_id"]), i)),
        ("test_known_device", splits["test_known_device"], lambda r, i: cache_img(r["image_id"])),
        ("test_heldout_device", splits["test_heldout_device"], lambda r, i: cache_img(r["image_id"])),
        ("ood_eval", ood, lambda r, i: Image.fromarray(np.load(os.path.join(a.ood, "cache", r["ood_id"] + ".npy"))))]

app = K.load_app(a.app_main)
models = {}
for m in ("a", "b"):
    g = json.load(open(getattr(a, f"{m}_gates"), encoding="utf-8"))
    models[getattr(a, f"{m}_name")] = {"clf": K.classifier(app, getattr(a, f"{m}_model"), getattr(a, f"{m}_labels")),
                                       "gates": (float(g["confidence_threshold"]), float(g["ood_margin"]), float(g["ood_logit_frozen"])), "gates_file": getattr(a, f"{m}_gates")}
labels = models[a.a_name]["clf"].labels; K_ = len(labels)
assert labels == models[a.b_name]["clf"].labels, "the two models have different class lists"


def macro_f1(y, p):
    f = []
    for k in sorted(set(y)):
        tp = sum(1 for t, q in zip(y, p) if t == k and q == k); fp = sum(1 for t, q in zip(y, p) if t != k and q == k); fn = sum(1 for t, q in zip(y, p) if t == k and q != k)
        f.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0)
    return float(np.mean(f)) if f else float("nan")


res = {"models": {n: {"sha256": v["clf"].model_sha256, "gates": dict(zip(("confidence", "margin", "ood_logit"), v["gates"])), "gates_file": v["gates_file"]} for n, v in models.items()},
       "c270_proxy_profiles": PROFILES, "sets": {}}
rows_out = []
t0 = time.time()
for sname, rows, load in SETS:
    per = {n: [] for n in models}
    for i, r in enumerate(rows):
        img = load(r, i)
        for n, v in models.items():
            p, raw = K.kiosk(v["clf"], img); verdict = K.verdict(p, raw, *v["gates"])
            per[n].append((int(p.argmax()), verdict, float(raw.max())))
        rows_out.append({"set": sname, "id": r.get("image_id", r.get("ood_id")), "crop": r.get("crop", ""), "y": r.get("model_index", ""),
                         **{f"{n}_pred": per[n][-1][0] for n in models}, **{f"{n}_verdict": per[n][-1][1] for n in models}, **{f"{n}_maxlogit": round(per[n][-1][2], 3) for n in models}})
    out = {"n": len(rows)}
    for n in models:
        P = per[n]; V = [q[1] for q in P]
        if sname == "ood_eval":
            groups = sorted({r["group"] for r in rows})
            out[n] = {"accepted_rate": float(np.mean([v == "ACCEPT" for v in V])), "unknown_rate": float(np.mean([v == "UNKNOWN" for v in V])),
                      "accepted_by_group": {g: float(np.mean([V[i] == "ACCEPT" for i, r in enumerate(rows) if r["group"] == g])) for g in groups}}
        else:
            y = [int(r["model_index"]) for r in rows]; pr = [q[0] for q in P]
            ok = [t == q for t, q in zip(y, pr)]
            o = {"top1_accuracy": float(np.mean(ok)), "macro_f1": macro_f1(y, pr),
                 "correct_and_accepted": float(np.mean([c and v == "ACCEPT" for c, v in zip(ok, V)])),
                 "rejected_unknown": float(np.mean([v == "UNKNOWN" for v in V])), "low_confidence": float(np.mean([v == "LOW_CONFIDENCE" for v in V])),
                 "wrong_but_accepted": float(np.mean([(not c) and v == "ACCEPT" for c, v in zip(ok, V)])),
                 "by_crop_accuracy": {c: float(np.mean([ok[i] for i, r in enumerate(rows) if r["crop"] == c])) for c in sorted({r["crop"] for r in rows})},
                 "mango_recall": {labels[k]: float(np.mean([pr[i] == k for i, t in enumerate(y) if t == k])) for k in sorted(set(y)) if labels[k].startswith("Mango") and any(t == k for t in y)}}
            out[n] = o
    res["sets"][sname] = out
    print(sname, json.dumps({n: (out[n].get("top1_accuracy"), out[n].get("correct_and_accepted"), out[n].get("accepted_rate")) for n in models}), f"{time.time() - t0:.0f}s", flush=True)
res["seconds"] = time.time() - t0
json.dump(res, open(os.path.join(a.out, "comparison.json"), "w", encoding="utf-8"), indent=1)
with open(os.path.join(a.out, "per_image.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, list(rows_out[0].keys())); w.writeheader(); w.writerows(rows_out)

A, B = a.a_name, a.b_name
L = [f"# Model comparison: {A} vs {B} (application six-view path, each model with its own gates)", "",
     f"Gates: {A} {res['models'][A]['gates']}; {B} {res['models'][B]['gates']}.", "",
     "| Set | n | Metric | " + A + " | " + B + " | Change |", "|---|---|---|---|---|---|"]
for sname, o in res["sets"].items():
    keys = ["accepted_rate", "unknown_rate"] if sname == "ood_eval" else ["top1_accuracy", "macro_f1", "correct_and_accepted", "rejected_unknown", "wrong_but_accepted"]
    for k in keys:
        va, vb = o[A][k], o[B][k]; L.append(f"| {sname} | {o['n']} | {k} | {va:.4f} | {vb:.4f} | {vb - va:+.4f} |")
L += ["", "Mango per-class recall (test_known_device):", "", "| Class | " + A + " | " + B + " |", "|---|---|---|"]
for c, v in res["sets"]["test_known_device"][A]["mango_recall"].items():
    L.append(f"| {c} | {v:.3f} | {res['sets']['test_known_device'][B]['mango_recall'].get(c, float('nan')):.3f} |")
L += ["", "`val` was used for selection and calibration; `val_c270_proxy` is simulated and related to the candidate's training augmentation; "
      "only real Logitech C270 captures on the kiosk can confirm live behaviour. For ood_eval, lower accepted_rate is better."]
open(os.path.join(a.out, "COMPARISON.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done", f"{res['seconds']:.0f}s")
