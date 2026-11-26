#!/usr/bin/env python3
"""Write deployment/release_manifests/<release>.json: the identity and evidence of one release candidate (versions, checksums of the
device package, model, dataset freeze file, gate calibration and the release evaluation or model comparison, and the verdicts).
  python write_release_record.py --dataset <AGL-MULTICROP-MD-1.0.0> --tests-junit <junit.xml>
      [--model-dir models/candidates/<model>] [--calibration <FROZEN_GATE_CALIBRATION.json>] [--comparison <comparison.json>]
Defaults reproduce the 5.0.0 / 5.1.0 records (model 1.0.0 with its frozen calibration and run-once release evaluation). A release with another
model passes its model folder, its calibration and, when it has no run-once release evaluation, the comparison made by
training/evaluation/compare_models.py."""
import argparse, hashlib, json, os, xml.etree.ElementTree as ET
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); PKG = os.path.join(R, "AGRILENS_RaspberryPi")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
rel = lambda p: os.path.relpath(p, R).replace(os.sep, "/")
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); ap.add_argument("--tests-junit", required=True)
ap.add_argument("--model-dir", default="models/candidates/agrilens-multicrop-1.0.0")
ap.add_argument("--calibration", default="training/evaluation/calibration_1.0.0/FROZEN_GATE_CALIBRATION.json")
ap.add_argument("--comparison", default=None); a = ap.parse_args()
man = json.load(open(os.path.join(PKG, "RELEASE_MANIFEST.json"), encoding="utf-8"))
mdir = os.path.join(R, a.model_dir); mman = json.load(open(os.path.join(mdir, "MODEL_MANIFEST.json"), encoding="utf-8"))
assert mman["sha256"] == man["model_sha256"], "model folder does not hold the packaged model"
cal_p = os.path.join(R, a.calibration); cal = json.load(open(cal_p))
assert cal.get("model_sha256", man["model_sha256"]) == man["model_sha256"], "calibration was made for another model"
suite = ET.parse(a.tests_junit).getroot(); suite = suite.find("testsuite") if suite.tag == "testsuites" else suite
t = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}; t["passed"] = t["tests"] - t["failures"] - t["errors"] - t["skipped"]
if a.comparison:
    cp = os.path.join(R, a.comparison); cmp_ = json.load(open(cp, encoding="utf-8"))
    evaluation = {"kind": "comparison with the previous release model (compare_models.py; no run-once release evaluation for this model)", "file": rel(cp), "sha256": sha(cp),
                  "summary": {s: {n: {k: v for k, v in m.items() if isinstance(v, float)} for n, m in d.items() if n != "n"} for s, d in cmp_["sets"].items()}}
    criteria = "not evaluated against C1-C9 (comparison only)"
else:
    ev_dir = os.path.join(R, "training", "evaluation", "release_eval_1.0.0"); ev = json.load(open(os.path.join(ev_dir, "release_evaluation.json")))
    evaluation = {"lock_file_sha256": sha(os.path.join(ev_dir, "RELEASE_EVALUATION_RUN_ONCE.json")), "results_sha256": sha(os.path.join(ev_dir, "release_evaluation.json")), "criteria": ev["criteria"]}
    criteria = "ALL PASS" if ev["criteria"]["ALL_PASS"] else "FAILED: " + ", ".join(k for k, v in ev["criteria"].items() if k != "ALL_PASS" and not v)
rec = {"release": man["release"], "app_version": man["app_version"], "build_timestamp": man["build_timestamp"],
       "model": {"id": man["model_id"], "version": man["model_version"], "sha256": man["model_sha256"], "bytes": os.path.getsize(os.path.join(PKG, "agrilens.onnx")),
                 "manifest": rel(os.path.join(mdir, "MODEL_MANIFEST.json"))},
       "dataset": {"id_version": man["dataset_version"], "freeze_checksums_sha256": sha(os.path.join(a.dataset, "FREEZE_CHECKSUMS.sha256"))},
       "device_package": {"path": "AGRILENS_RaspberryPi/", "files": len(man["files_sha256"]), "SHA256SUMS_sha256": sha(os.path.join(PKG, "SHA256SUMS")),
                          "RELEASE_MANIFEST_sha256": sha(os.path.join(PKG, "RELEASE_MANIFEST.json")), "main_py_sha256": man["files_sha256"]["main.py"],
                          "ota_files_fetched_by_devices": man["ota_files_fetched_by_devices"]},
       "gate_calibration": {"file": rel(cal_p), "sha256": sha(cal_p), "confidence": cal["confidence_threshold"], "margin": cal["ood_margin"], "ood_logit": cal["ood_logit_frozen"]},
       "release_evaluation": evaluation,
       "automated_tests": t,
       "rollback_release": {"path": "deployment/rollback/AGRILENS-5.0.1-rollback/", "SHA256SUMS_sha256": sha(os.path.join(R, "deployment", "rollback", "AGRILENS-5.0.1-rollback", "SHA256SUMS")),
                            "note": "kiosks on 5.1.0 or later refuse 5.0.1 as a downgrade; single-kiosk rollback.sh restores the previous version"},
       "status": {"published": False, "deployed": False, "raspberry_pi_validation": "pending", "c270_field_validation": "pending", "expert_label_review": "pending",
                  "release_criteria": criteria}}
out = os.path.join(R, "deployment", "release_manifests", man["release"] + ".json"); os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(rec, open(out, "w", encoding="utf-8", newline="\n"), indent=1); print(out); print(json.dumps(rec["status"], indent=1))
