#!/usr/bin/env python3
"""Calibrate the release rejection gates on VALIDATION data only (rule in training/configurations/SELECTION_RULE.md, point 5):
largest ood_logit such that the false rejection of correctly classified validation images is at most 3% in EVERY crop and in every Mango source
with at least 50 validation images; confidence 0.40 and margin 0.12 unchanged. Uses the application's six-view path. The ood_v2 calibration half
is used only to REPORT false acceptance at the chosen point (it does not move the threshold). Run with the application's Python.
  python calibrate_gates.py --app-main application/main.py --model <onnx> --labels <labels> --dataset <root> --cache <cache> --ood <ood_v2 dir> --out <dir>"""
import argparse, csv, json, os, sys
import numpy as np
from PIL import Image
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kiosk_path as K

ap = argparse.ArgumentParser()
for n in ("app-main", "model", "labels", "dataset", "cache", "ood", "out"): ap.add_argument("--" + n, required=True)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); CONF, MARGIN, FRR = 0.40, 0.12, 0.03
app = K.load_app(a.app_main); clf = K.classifier(app, a.model, a.labels)
va = list(csv.DictReader(open(os.path.join(a.dataset, "splits", "val.csv"), encoding="utf-8")))
oc = [r for r in csv.DictReader(open(os.path.join(a.ood, "ood_v2_manifest.csv"), encoding="utf-8")) if r["split"] == "calibration"]
rows = []
for r in va:
    p, raw = K.kiosk(clf, Image.fromarray(np.load(os.path.join(a.cache, r["image_id"] + ".npy"))))
    rows.append({"kind": "val", "crop": r["crop"], "source": r["source_id"], "y": int(r["model_index"]), "pred": int(p.argmax()), "conf": float(p.max()), "margin": float(np.sort(p)[-1] - np.sort(p)[-2]), "maxlogit": float(raw.max()), "probs": p, "raw": raw})
for r in oc:
    p, raw = K.kiosk(clf, Image.fromarray(np.load(os.path.join(a.ood, "cache", r["ood_id"] + ".npy"))))
    rows.append({"kind": "ood", "group": r["group"], "y": -1, "pred": int(p.argmax()), "conf": float(p.max()), "margin": float(np.sort(p)[-1] - np.sort(p)[-2]), "maxlogit": float(raw.max()), "probs": p, "raw": raw})
V = [r for r in rows if r["kind"] == "val"]; O = [r for r in rows if r["kind"] == "ood"]
groups = {f"crop:{c}": [r for r in V if r["crop"] == c] for c in sorted({r["crop"] for r in V})}
for s in sorted({r["source"] for r in V if r["crop"] == "Mango"}):
    g = [r for r in V if r["crop"] == "Mango" and r["source"] == s]
    if len(g) >= 50: groups[f"mango_source:{s}"] = g
def frr(g, t): c = [r for r in g if r["y"] == r["pred"]]; return sum(K.verdict(r["probs"], r["raw"], CONF, MARGIN, t) != "ACCEPT" for r in c) / max(1, len(c))
grid = [round(x, 2) for x in np.arange(0.0, 6.51, 0.05)]; sweep = []
for t in grid:
    row = {"ood_logit": t, **{f"frr_{k}": frr(g, t) for k, g in groups.items()}}
    row["worst_group_frr"] = max(v for k, v in row.items() if k.startswith("frr_")); row["pooled_frr"] = frr(V, t)
    for gname in sorted({r["group"] for r in O}): row[f"ood_cal_accepted_{gname}"] = float(np.mean([K.verdict(r["probs"], r["raw"], CONF, MARGIN, t) == "ACCEPT" for r in O if r["group"] == gname]))
    sweep.append(row)
ok = [r for r in sweep if r["worst_group_frr"] <= FRR]; chosen = max(r["ood_logit"] for r in ok) if ok else 0.0
clamped = min(6.5, max(1.0, chosen)); pick = [r for r in sweep if r["ood_logit"] == chosen][0]
with open(os.path.join(a.out, "gate_sweep_validation.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, list(sweep[0].keys())); w.writeheader(); w.writerows(sweep)
res = {"rule": "largest ood_logit with false rejection of correct validation images <= 3% in every crop and every Mango source with >= 50 validation images",
       "confidence_threshold": CONF, "ood_margin": MARGIN, "ood_logit_rule_value": chosen, "ood_logit_frozen": clamped,
       "note_on_clamp": "the application accepts ood_logit 1.0 to 6.5; the frozen value is the rule value clamped to that range" if clamped != chosen else "",
       "at_frozen_point": [r for r in sweep if abs(r["ood_logit"] - clamped) < 1e-9][0] if any(abs(r["ood_logit"] - clamped) < 1e-9 for r in sweep) else pick,
       "validation_classification_accuracy_kiosk_path": float(np.mean([r["y"] == r["pred"] for r in V])), "validation_images": len(V), "ood_calibration_images": len(O),
       "validation_maxlogit_quantiles": {f"p{q}": float(np.percentile([r["maxlogit"] for r in V], q)) for q in (1, 5, 25, 50, 75, 99)},
       "ood_cal_maxlogit_quantiles": {f"p{q}": float(np.percentile([r["maxlogit"] for r in O], q)) for q in (5, 25, 50, 75, 95)},
       "model_sha256": clf.model_sha256}
json.dump(res, open(os.path.join(a.out, "FROZEN_GATE_CALIBRATION.json"), "w"), indent=1); print(json.dumps(res, indent=1))
