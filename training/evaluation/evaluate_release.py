#!/usr/bin/env python3
"""Single release evaluation of AGRILENS-MULTICROP 1.0.0 against the frozen test tiers and the ood_v2 evaluation half (criteria C1-C9 in
RELEASE_EVALUATION_CRITERIA.md). Runs ONCE: refuses if the lock exists or if any frozen input differs from the hashes recorded in the lock request.
Both the release model and the 4.9.4 production model are run through the application's own six-view path (release main.py, read-only).
Run with the application's Python (numpy, Pillow, onnxruntime, cv2, tkinter; no pandas).
  python evaluate_release.py --app-main AGRILENS_RaspberryPi/main.py --dataset <root> --cache <cache> --ood <ood_v2> --calibration <FROZEN_GATE_CALIBRATION.json> --out <dir>"""
import argparse, csv, hashlib, json, os, sys, time, datetime as dt
from collections import Counter, defaultdict
import numpy as np
from PIL import Image
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
import kiosk_path as K
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))


def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [float(c - h), float(c + h)]


def cls_metrics(y, p, K_):
    cm = np.zeros((K_, K_), int)
    for t, q in zip(y, p): cm[t, q] += 1
    per = []
    for k in range(K_):
        tp = cm[k, k]; fp = cm[:, k].sum() - tp; fn = cm[k].sum() - tp; pr = tp / (tp + fp) if tp + fp else float("nan"); rc = tp / (tp + fn) if tp + fn else float("nan")
        per.append({"n": int(cm[k].sum()), "precision": pr, "recall": rc, "f1": (2 * pr * rc / (pr + rc)) if pr == pr and rc == rc and pr + rc > 0 else (0.0 if cm[k].sum() else float("nan"))})
    f1s = [x["f1"] for x in per if x["n"] > 0]
    return {"n": int(len(y)), "accuracy": float(np.mean(np.array(y) == np.array(p))) if len(y) else float("nan"), "macro_f1": float(np.mean(f1s)) if f1s else float("nan"), "per_class": per, "confusion": cm.tolist()}


def main():
    ap = argparse.ArgumentParser()
    for n in ("app-main", "dataset", "cache", "ood", "calibration", "out"): ap.add_argument("--" + n, required=True)
    ap.add_argument("--smoke", action="store_true", help="code-path check on a few VALIDATION images and the ood_v2 CALIBRATION half; reads no test tier, writes no lock; results are meaningless")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); lock = os.path.join(a.out, "SMOKE_RUN.json" if a.smoke else "RELEASE_EVALUATION_RUN_ONCE.json")
    if os.path.exists(lock) and not a.smoke: raise SystemExit("Refusing: the release evaluation has already been run once.")
    pkg = os.path.dirname(os.path.abspath(a.app_main)); new_onnx, new_lab = os.path.join(pkg, "agrilens.onnx"), os.path.join(pkg, "labels.txt")
    prod_dir = os.path.join(ROOT, "models", "production", "agrilens-24class-4.9.4"); prod_onnx, prod_lab = os.path.join(prod_dir, "agrilens.onnx"), os.path.join(prod_dir, "labels.txt")
    cal = json.load(open(a.calibration)); app = K.load_app(a.app_main)
    assert abs(app.MODEL_CALIBRATION_OOD_LOGIT - cal["ood_logit_frozen"]) < 1e-9 and app.MODEL_SHA256 == sha(new_onnx) == cal["model_sha256"], "release main.py, model and frozen calibration disagree"
    rec = {}
    for ln in open(os.path.join(a.dataset, "FREEZE_CHECKSUMS.sha256"), encoding="utf-8"):
        if ln.strip(): h, p = ln.rstrip("\n").split("  ", 1); rec[p] = h
    for n in ("splits/test_known_device.csv", "splits/test_heldout_device.csv", "manifests/image_manifest.csv"): assert sha(os.path.join(a.dataset, n.replace("/", os.sep))) == rec[n], n
    fp = open(os.path.join(a.ood, "OOD_V2_EVALUATION_HALF.sha256")).read().split()[0]
    hashes = {"app_main": sha(a.app_main), "release_model": sha(new_onnx), "production_model": sha(prod_onnx), "calibration": sha(a.calibration), "criteria": sha(os.path.join(HERE, "RELEASE_EVALUATION_CRITERIA.md")),
              "this_script": sha(__file__), "kiosk_path": sha(os.path.join(HERE, "kiosk_path.py")), "dataset_freeze": sha(os.path.join(a.dataset, "FREEZE_CHECKSUMS.sha256")), "ood_v2_eval_fingerprint": fp}
    json.dump({"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "hashes": hashes}, open(lock, "w"), indent=1)
    new = K.classifier(app, new_onnx, new_lab); prod = K.classifier(app, prod_onnx, prod_lab); labels = new.labels; K_ = len(labels); assert labels == prod.labels
    G_NEW = (cal["confidence_threshold"], cal["ood_margin"], cal["ood_logit_frozen"]); G_PROD = {"device_6.0": (0.40, 0.12, 6.0), "code_default_1.4": (0.40, 0.12, 1.40)}
    items = []
    for tier in ("test_known_device", "test_heldout_device"):
        if a.smoke:
            va = rd(os.path.join(a.dataset, "splits", "val.csv")); src = va[::40] if tier == "test_known_device" else [r for r in va if r["class_id"] == "MNG001"][:30]
        else: src = rd(os.path.join(a.dataset, "splits", f"{tier}.csv"))
        for r in src: items.append({"tier": tier, **r, "path": os.path.join(a.cache, r["image_id"] + ".npy")})
    for r in rd(os.path.join(a.ood, "ood_v2_manifest.csv")):
        if r["split"] == ("calibration" if a.smoke else "evaluation"): items.append({"tier": "ood_v2_evaluation", "image_id": r["ood_id"], "group": r["group"], "path": os.path.join(a.ood, "cache", r["ood_id"] + ".npy")})
    # gate-code equivalence with the application's decision code on the first 300 in-distribution items
    eq = bad = 0; rows = []; t0 = time.time()
    for n, it in enumerate(items):
        pil = Image.fromarray(np.load(it["path"])); pn, rn = K.kiosk(new, pil); ps, rs = K.single(new, pil); pp, rp = K.kiosk(prod, pil)
        row = {"tier": it["tier"], "image_id": it["image_id"], "crop": it.get("crop", ""), "source": it.get("source_id", it.get("group", "")), "device": it.get("capture_device", ""), "leaf_group": it.get("leaf_group_id", ""),
               "y": int(it["model_index"]) if "model_index" in it else -1, "new_pred": int(pn.argmax()), "new_single_pred": int(ps.argmax()), "prod_pred": int(pp.argmax()), "new_conf": float(pn.max()), "new_maxlogit": float(rn.max()),
               "new_verdict": K.verdict(pn, rn, *G_NEW), "prod_verdict_device_6.0": K.verdict(pp, rp, *G_PROD["device_6.0"]), "prod_verdict_code_default_1.4": K.verdict(pp, rp, *G_PROD["code_default_1.4"])}
        if n < 300 and row["y"] >= 0:
            v = K.H.decide(app, labels, list(pn), rn, thresholds={"confidence_threshold": G_NEW[0], "ood_margin": G_NEW[1], "ood_logit": G_NEW[2]})["verdict"]
            v = "ACCEPT" if v in ("HEALTHY", "DISEASE") else v; eq += 1; bad += v != row["new_verdict"]
        rows.append(row)
    with open(os.path.join(a.out, "per_image.csv"), "w", newline="", encoding="utf-8") as f: w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    R = {"NOTE": "Single release evaluation (run once). Tiers are never pooled.", "hashes": hashes, "gates_release": dict(zip(("confidence", "margin", "ood_logit"), G_NEW)), "gate_code_equivalence": {"checked": eq, "mismatches": bad},
         "seconds": time.time() - t0, "tiers": {}}
    crops = ["Apple", "Mango", "Potato", "Tomato"]
    for tier in ("test_known_device", "test_heldout_device"):
        sub = [r for r in rows if r["tier"] == tier]; y = [r["y"] for r in sub]; T = {}
        for key, nm in (("new_pred", "release_kiosk_path"), ("new_single_pred", "release_single_view"), ("prod_pred", "production_kiosk_path")): T[nm] = cls_metrics(y, [r[key] for r in sub], K_)
        T["release_by_crop"] = {c: cls_metrics([r["y"] for r in sub if r["crop"] == c], [r["new_pred"] for r in sub if r["crop"] == c], K_) for c in crops if any(r["crop"] == c for r in sub)}
        for c in T["release_by_crop"]: T["release_by_crop"][c].pop("confusion", None)
        cor = [r["y"] == r["new_pred"] for r in sub]; acc_ = [r["new_verdict"] == "ACCEPT" for r in sub]
        dl = {"accepted_correct": int(sum(a_ and c for a_, c in zip(acc_, cor))), "accepted_wrong": int(sum(a_ and not c for a_, c in zip(acc_, cor))), "rejected_though_correct": int(sum((not a_) and c for a_, c in zip(acc_, cor))),
              "rejected_and_wrong": int(sum((not a_) and not c for a_, c in zip(acc_, cor))), "rejections_by_gate": dict(Counter(r["new_verdict"] for r in sub if r["new_verdict"] != "ACCEPT"))}
        dl["false_rejection_rate"] = dl["rejected_though_correct"] / max(1, sum(cor)); dl["false_rejection_ci"] = wilson(dl["rejected_though_correct"], sum(cor)); dl["accuracy_among_accepted"] = dl["accepted_correct"] / max(1, sum(acc_))
        dl["false_rejection_by_crop"] = {c: (lambda cc: {"correct": len(cc), "rejected": sum(r["new_verdict"] != "ACCEPT" for r in cc), "rate": sum(r["new_verdict"] != "ACCEPT" for r in cc) / max(1, len(cc))})([r for r in sub if r["crop"] == c and r["y"] == r["new_pred"]]) for c in crops if any(r["crop"] == c for r in sub)}
        dl["decision_recall_by_class"] = {labels[k]: {"n": sum(r["y"] == k for r in sub), "decision_recall": sum(r["y"] == k and r["new_pred"] == k and r["new_verdict"] == "ACCEPT" for r in sub) / max(1, sum(r["y"] == k for r in sub)),
                                                      "classification_recall": T["release_kiosk_path"]["per_class"][k]["recall"]} for k in range(K_) if any(r["y"] == k for r in sub)}
        T["decision_level_release"] = dl
        T["by_device_release_accuracy"] = {d: {"n": len(g), "accuracy": float(np.mean([r["y"] == r["new_pred"] for r in g]))} for d, g in ((d, [r for r in sub if r["device"] == d]) for d in sorted({r["device"] for r in sub})) if len(g) >= 30}
        T["by_source_accuracy"] = {s: {"n": len(g), "release": float(np.mean([r["y"] == r["new_pred"] for r in g])), "production": float(np.mean([r["y"] == r["prod_pred"] for r in g]))} for s, g in ((s, [r for r in sub if r["source"] == s]) for s in sorted({r["source"] for r in sub}))}
        T["cross_crop_confusions_release"] = sum(1 for r in sub if r["new_pred"] != r["y"] and labels[r["new_pred"]].split("_")[0] != labels[r["y"]].split("_")[0])
        T["cross_crop_confusions_production"] = sum(1 for r in sub if r["prod_pred"] != r["y"] and labels[r["prod_pred"]].split("_")[0] != labels[r["y"]].split("_")[0])
        T["production_decision_level"] = {p: {"accept_rate": float(np.mean([r[f"prod_verdict_{p}"] == "ACCEPT" for r in sub])), "false_rejection_rate": sum(r[f"prod_verdict_{p}"] != "ACCEPT" and r["y"] == r["prod_pred"] for r in sub) / max(1, sum(r["y"] == r["prod_pred"] for r in sub))} for p in G_PROD}
        R["tiers"][tier] = T
    # C4 paired comparison on images the production model was not trained on
    un = [r for r in rows if r["tier"] in ("test_known_device", "test_heldout_device") and r["source"] in ("SAR25", "ABCGMP")]
    diff = np.array([(r["y"] == r["new_pred"]) - (r["y"] == r["prod_pred"]) for r in un], float); grp = np.array([r["leaf_group"] for r in un]); ug = np.unique(grp); idx = {g: np.nonzero(grp == g)[0] for g in ug}
    rng = np.random.default_rng(0); bs = [diff[np.concatenate([idx[g] for g in rng.choice(ug, len(ug))])].mean() for _ in range(2000)]
    R["c4_unseen_by_production"] = {"images": len(un), "release_accuracy": float(np.mean([r["y"] == r["new_pred"] for r in un])), "production_accuracy": float(np.mean([r["y"] == r["prod_pred"] for r in un])),
                                    "difference": float(diff.mean()), "difference_95ci_leaf_group_bootstrap": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
    oo = [r for r in rows if r["tier"] == "ood_v2_evaluation"]; R["ood"] = {}
    for g in sorted({r["source"] for r in oo}):
        s = [r for r in oo if r["source"] == g]; k = sum(r["new_verdict"] == "ACCEPT" for r in s); kp = sum(r["prod_verdict_device_6.0"] == "ACCEPT" for r in s); kp2 = sum(r["prod_verdict_code_default_1.4"] == "ACCEPT" for r in s)
        R["ood"][g] = {"n": len(s), "release_accepted": k, "release_rate": k / len(s), "release_ci": wilson(k, len(s)), "production_device_6.0_rate": kp / len(s), "production_code_1.4_rate": kp2 / len(s)}
    nl = [r for r in oo if r["source"].startswith("nonleaf")]; k = sum(r["new_verdict"] == "ACCEPT" for r in nl); R["ood_nonleaf_pooled"] = {"n": len(nl), "release_accepted": k, "release_rate": k / max(1, len(nl)), "release_ci": wilson(k, len(nl))}
    man = json.load(open(os.path.join(ROOT, "models", "candidates", "agrilens-multicrop-1.0.0", "MODEL_MANIFEST.json"))); par = man["parity_vs_pytorch_256_validation_images"]
    kn, ho = R["tiers"]["test_known_device"], R["tiers"]["test_heldout_device"]; ai = labels.index("Mango_Anthracnose")
    V = {"C1": kn["release_kiosk_path"]["macro_f1"] >= 0.90, "C2": all(v["macro_f1"] >= 0.85 for v in kn["release_by_crop"].values()), "C3": ho["release_kiosk_path"]["per_class"][ai]["recall"] >= 0.80,
         "C4": R["c4_unseen_by_production"]["difference"] >= 0, "C5": all(v["rate"] <= 0.05 for v in kn["decision_level_release"]["false_rejection_by_crop"].values()), "C6": ho["decision_level_release"]["false_rejection_rate"] <= 0.10,
         "C7": all(v["decision_recall"] >= v["classification_recall"] - 0.10 for t in (kn,) for v in t["decision_level_release"]["decision_recall_by_class"].values()) and ho["decision_level_release"]["decision_recall_by_class"]["Mango_Anthracnose"]["decision_recall"] >= ho["decision_level_release"]["decision_recall_by_class"]["Mango_Anthracnose"]["classification_recall"] - 0.10,
         "C8": R["ood_nonleaf_pooled"]["release_rate"] <= 0.35, "C9": par["max_abs_logit_diff"] <= 1e-3 and par["argmax_agreement"] == 1.0}
    V = {k: bool(v) for k, v in V.items()}; V["ALL_PASS"] = all(V.values()); R["criteria"] = V; R["labels"] = labels
    json.dump(R, open(os.path.join(a.out, "release_evaluation.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)); print(json.dumps(V)); print("known macroF1", round(kn["release_kiosk_path"]["macro_f1"], 4), "prod", round(kn["production_kiosk_path"]["macro_f1"], 4))


if __name__ == "__main__":
    main()
