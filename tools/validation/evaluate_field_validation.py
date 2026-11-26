#!/usr/bin/env python3
"""
Field-validation evaluation: how does the CURRENT model and decision logic behave on real captures?

Input : a folder written by scripts/capture_field_samples.py (field_samples.csv, frames/, crops/, session_*.json)
Output: field_validation_report.md and field_validation_results.csv in the same folder

This is ACCURACY validation. It is separate from the performance benchmark (scripts/benchmark_pi5.py).
It reports; it never changes the model, labels, preprocessing or thresholds.

* Results are reported separately for each source: real_leaf, phone_screen, printed. They are never pooled.
* The frame is cropped with the stored box (the same operation as the kiosk: frame.crop(box)) and passed to
  Classifier.predict. The verdict comes from the application's own decision code with the thresholds
  recorded in the session's device config (the effective calibration actually used), unless
  --profile code_defaults|device is given.
* The ood_logit sensitivity table is INFORMATION ONLY. It shows what other settings would have done on
  this data. Changing a threshold needs its own review and approval.
* Small samples: intervals are Wilson 95% intervals and are printed so wide bands are visible.
"""
import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app_harness as H  # noqa: E402

OUT_OF_SCOPE = "Out_of_scope"
ACCEPTED = ("HEALTHY", "DISEASE")
SENSITIVITY_OOD = (1.4, 2.4, 3.0, 4.0, 5.0, 6.0)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def fmt(k, n):
    if n == 0:
        return "n/a (0)"
    lo, hi = wilson(k, n)
    return "%d/%d = %.1f%% (95%% CI %.0f-%.0f%%)" % (k, n, 100.0 * k / n, 100 * lo, 100 * hi)


def load_rows(folder):
    path = os.path.join(folder, "field_samples.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def session_thresholds(folder, session):
    p = os.path.join(folder, "session_%s_device_config.json" % session)
    if not os.path.exists(p):
        return None
    cfg = json.load(open(p, encoding="utf-8"))["effective_config"]
    return {"confidence_threshold": cfg["confidence_threshold"], "ood_margin": cfg["ood_margin"], "ood_logit": cfg["ood_logit"]}


def evaluate(folder, app=None, profile="snapshot", classifier=None):
    from PIL import Image
    app = app or H.load_app()
    clf = classifier or app.Classifier(app.MODEL_PATH, app.LABELS_PATH)
    if clf.session is None:
        raise SystemExit("Classifier is in DEMO mode: %s" % clf.error_reason)
    labels = clf.labels
    rows = load_rows(folder)
    results = []
    problems = []
    for r in rows:
        tc, src = r["true_class"], r["source"]
        if tc != OUT_OF_SCOPE and tc not in labels:
            problems.append("%s: unknown true_class %r" % (r["id"], tc))
            continue
        frame = Image.open(os.path.join(folder, r["frame_file"])).convert("RGB")
        box = tuple(int(r[k]) for k in ("crop_x0", "crop_y0", "crop_x1", "crop_y1"))
        crop = frame.crop(box)
        saved = Image.open(os.path.join(folder, r["crop_file"])).convert("RGB")
        if saved.size != crop.size or saved.tobytes() != crop.tobytes():
            problems.append("%s: stored crop differs from frame.crop(box)" % r["id"])
        probs, _ms, raw = clf.predict(crop)
        if probs is None:
            problems.append("%s: inference returned no probabilities" % r["id"])
            continue
        top = max(range(len(probs)), key=lambda i: probs[i])
        if profile == "snapshot":
            thr = session_thresholds(folder, r["session"])
            if thr is None:
                problems.append("%s: no session config found, using code defaults" % r["id"])
                thr = H.PROFILES["code_defaults"]
        else:
            thr = H.PROFILES[profile]
        d = H.decide(app, labels, probs, raw, thresholds=thr)
        sens = {str(v): H.decide(app, labels, probs, raw, thresholds=dict(thr, ood_logit=v))["verdict"] for v in SENSITIVITY_OOD}
        order = sorted(range(len(probs)), key=lambda i: -probs[i])[:3]
        results.append({
            "id": r["id"], "session": r["session"], "source": src, "true_class": tc, "lighting": r.get("lighting", ""),
            "pred_label": labels[top], "pred_prob": probs[top], "max_logit": float(max(raw)),
            "top3": ";".join("%s:%.3f" % (labels[i], probs[i]) for i in order),
            "verdict": d["verdict"], "thresholds": thr, "sensitivity": sens,
        })
    return {"labels": labels, "results": results, "problems": problems, "profile": profile,
            "app_version": app.APP_VERSION, "model_sha256": app.MODEL_SHA256}


def summarise(results, labels):
    """Metrics for one source."""
    ins = [r for r in results if r["true_class"] != OUT_OF_SCOPE]
    oos = [r for r in results if r["true_class"] == OUT_OF_SCOPE]
    acc = [r for r in ins if r["verdict"] in ACCEPTED]
    s = {
        "in_scope_n": len(ins), "out_of_scope_n": len(oos),
        "top1_correct": sum(r["pred_label"] == r["true_class"] for r in ins),
        "accepted": len(acc),
        "accepted_correct": sum(r["pred_label"] == r["true_class"] for r in acc),
        "accepted_wrong": sum(r["pred_label"] != r["true_class"] for r in acc),
        "rejected_low_confidence": sum(r["verdict"] == "LOW_CONFIDENCE" for r in ins),
        "rejected_unknown": sum(r["verdict"] == "UNKNOWN" for r in ins),
        "oos_rejected": sum(r["verdict"] not in ACCEPTED for r in oos),
        "oos_wrongly_accepted": sum(r["verdict"] in ACCEPTED for r in oos),
    }
    per_class = {}
    for lbl in labels:
        sub = [r for r in ins if r["true_class"] == lbl]
        per_class[lbl] = {"n": len(sub), "top1_correct": sum(r["pred_label"] == lbl for r in sub),
                          "accepted": sum(r["verdict"] in ACCEPTED for r in sub)}
    conf = defaultdict(Counter)
    for r in ins:
        conf[r["true_class"]][r["pred_label"]] += 1
    s["per_class"], s["confusion"] = per_class, {k: dict(v) for k, v in conf.items()}
    sens = {}
    for v in SENSITIVITY_OOD:
        key = str(v)
        sens[key] = {"in_scope_accepted": sum(r["sensitivity"][key] in ACCEPTED for r in ins),
                     "in_scope_unknown": sum(r["sensitivity"][key] == "UNKNOWN" for r in ins),
                     "oos_rejected": sum(r["sensitivity"][key] not in ACCEPTED for r in oos)}
    s["sensitivity"] = sens
    return s


def render_report(ev, folder):
    results, labels = ev["results"], ev["labels"]
    by_src = defaultdict(list)
    for r in results:
        by_src[r["source"]].append(r)
    out = ["# Field validation report", "",
           "Accuracy validation of the unchanged model and decision logic on real captures. Not a performance benchmark.",
           "", "- App version: %s" % ev["app_version"], "- Model SHA-256: `%s`" % ev["model_sha256"],
           "- Threshold profile: **%s**" % ev["profile"], "- Images evaluated: %d" % len(results), ""]
    if ev["problems"]:
        out += ["## Data problems", ""] + ["- " + p for p in ev["problems"]] + [""]
    for src in ("real_leaf", "phone_screen", "printed"):
        sub = by_src.get(src, [])
        out += ["## Source: %s" % src, ""]
        if not sub:
            out += ["No images captured for this source.", ""]
            continue
        s = summarise(sub, labels)
        classes_with_data = sum(1 for v in s["per_class"].values() if v["n"])
        thr = sorted({json.dumps(r["thresholds"], sort_keys=True) for r in sub})
        out += ["Thresholds used: " + "; ".join("`%s`" % t for t in thr), "",
                "| Measure | Result |", "|---|---|",
                "| In-scope images | %d (%d classes covered of 24) |" % (s["in_scope_n"], classes_with_data),
                "| Top-1 correct (before rejection) | %s |" % fmt(s["top1_correct"], s["in_scope_n"]),
                "| Accepted by the decision gate | %s |" % fmt(s["accepted"], s["in_scope_n"]),
                "| Accepted and correct | %s |" % fmt(s["accepted_correct"], s["in_scope_n"]),
                "| Accepted but wrong | %s |" % fmt(s["accepted_wrong"], s["in_scope_n"]),
                "| Rejected as low confidence | %s |" % fmt(s["rejected_low_confidence"], s["in_scope_n"]),
                "| Rejected as unknown (OOD gate) | %s |" % fmt(s["rejected_unknown"], s["in_scope_n"]),
                "| Correct among accepted | %s |" % fmt(s["accepted_correct"], s["accepted"]),
                "| Out-of-scope images | %d |" % s["out_of_scope_n"],
                "| Out-of-scope rejected | %s |" % fmt(s["oos_rejected"], s["out_of_scope_n"]),
                "| Out-of-scope wrongly accepted | %s |" % fmt(s["oos_wrongly_accepted"], s["out_of_scope_n"]), "",
                "Per class (top-1 correct / accepted):", "", "| Class | n | Top-1 correct | Accepted |", "|---|---|---|---|"]
        for lbl, v in s["per_class"].items():
            if v["n"]:
                out.append("| %s | %d | %d | %d |" % (lbl, v["n"], v["top1_correct"], v["accepted"]))
        small = [lbl for lbl, v in s["per_class"].items() if 0 < v["n"] < 30]
        if small or classes_with_data < 24:
            out += ["", "> Pilot-size data: %d classes have fewer than 30 images and %d of 24 classes have none. "
                    "Treat the intervals as wide." % (len(small), 24 - classes_with_data)]
        out += ["", "Sensitivity of the OOD logit gate (INFORMATION ONLY, no threshold is changed by this report):", "",
                "| ood_logit | In-scope accepted | In-scope rejected as unknown | Out-of-scope rejected |", "|---|---|---|---|"]
        for v, m in s["sensitivity"].items():
            out.append("| %s | %s | %s | %s |" % (v, fmt(m["in_scope_accepted"], s["in_scope_n"]), fmt(m["in_scope_unknown"], s["in_scope_n"]),
                                                  fmt(m["oos_rejected"], s["out_of_scope_n"])))
        out.append("")
    return "\n".join(out) + "\n"


def write_outputs(ev, folder):
    with open(os.path.join(folder, "field_validation_report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_report(ev, folder))
    cols = ["id", "session", "source", "lighting", "true_class", "pred_label", "pred_prob", "max_logit", "verdict", "top3"]
    with open(os.path.join(folder, "field_validation_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(ev["results"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=os.path.join(H.REPO_ROOT, "field_validation"))
    ap.add_argument("--profile", default="snapshot", choices=["snapshot", "code_defaults", "device"])
    a = ap.parse_args()
    ev = evaluate(a.dir, profile=a.profile)
    write_outputs(ev, a.dir)
    print("evaluated %d images; report: %s" % (len(ev["results"]), os.path.join(a.dir, "field_validation_report.md")))
    for p in ev["problems"]:
        print("PROBLEM:", p)


if __name__ == "__main__":
    main()
