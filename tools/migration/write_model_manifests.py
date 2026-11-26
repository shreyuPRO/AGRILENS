"""Write models/production/agrilens-24class-4.9.4/MODEL_MANIFEST.json, models/candidates/mango5-exp001/CANDIDATE_POINTER.json and models/manifests/MODEL_REGISTRY.json."""
import hashlib, json, os
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
pd_ = os.path.join(R, "models", "production", "agrilens-24class-4.9.4"); onnx = os.path.join(pd_, "agrilens.onnx")
labels = [l.strip() for l in open(os.path.join(pd_, "labels.txt"), encoding="utf-8") if l.strip()]
prod = {"model_id": "AGRILENS-24CLASS", "model_version": "4.9.4-production", "status": "PRODUCTION BASELINE (deployed with AGRILENS 4.9.4); preserved unchanged for rollback and comparison",
        "file": "agrilens.onnx", "sha256": sha(onnx), "bytes": os.path.getsize(onnx), "labels_file": "labels.txt", "labels_sha256_content_lf": hashlib.sha256(("\n".join(labels) + "\n").encode()).hexdigest(), "classes": labels,
        "architecture": "MobileNetV4-Conv-Small (timm), ONNX", "training": "training/legacy_4.9.4 (stratified 80/20 per-image split, seed 42; ImageNet init; no checkpoint or log was found)",
        "known_properties": ["very likely trained on the MangoLeafBD and PlantVillage images in AGL-MULTICROP-MD (scores ~100% on MangoLeafBD), so its scores on those images are not independent",
                             "rejection gates calibrated on device to ood_logit 6.0 (working-tree kiosk_config.json, uncommitted); code default 1.40", "no group-aware split; no held-out-device evaluation"]}
json.dump(prod, open(os.path.join(pd_, "MODEL_MANIFEST.json"), "w"), indent=1)
cd = os.path.join(R, "models", "candidates", "mango5-exp001"); os.makedirs(cd, exist_ok=True)
json.dump({"candidate": "mango5_exp001 / B_partial_ft_s43", "status": "EXPERIMENTAL five-class Mango candidate; preserved for comparison; not part of 5.0.0",
           "preserved_at": r"D:\AGRILENS_Training\AGL-MANGO-MD\candidates\mango5_exp001_B_partial_ft_s43_v1", "onnx_sha256": "a241d91c8b06352f3185343dd0371680e4c4f6c6c1257b151dc3c9d775e55aba",
           "checkpoint_sha256": "1fcddfd8366eae4753cc0e7c28c8ec86051d3722d3e848e1fd379b39e306a9e8", "checksums": "CANDIDATE_CHECKSUMS.sha256 in the preserved folder (48 files)",
           "kiosk_path_evaluation": "executed once 2026-11-17: P1 pass, P2 FAIL (false rejection 6.0% / 12.4%), P3 FAIL, P4 pass, P5 pass", "why_not_in_repo": "binary artefacts kept outside git; this pointer records identity"},
          open(os.path.join(cd, "CANDIDATE_POINTER.json"), "w"), indent=1)
md = os.path.join(R, "models", "manifests"); os.makedirs(md, exist_ok=True)
reg = {"models": [{"id": "AGRILENS-24CLASS 4.9.4", "role": "production baseline / rollback", "path": "models/production/agrilens-24class-4.9.4/", "sha256": prod["sha256"]},
                  {"id": "mango5_exp001 B_partial_ft_s43", "role": "experimental Mango comparison", "path": "models/candidates/mango5-exp001/CANDIDATE_POINTER.json", "sha256": "a241d91c8b06352f3185343dd0371680e4c4f6c6c1257b151dc3c9d775e55aba"},
                  {"id": "AGRILENS-MULTICROP 1.0.0", "role": "release candidate for AGRILENS 5.0.0", "path": "models/candidates/agrilens-multicrop-1.0.0/", "sha256": "see MODEL_MANIFEST.json there (written after training)"}]}
json.dump(reg, open(os.path.join(md, "MODEL_REGISTRY.json"), "w"), indent=1); print("written; production sha", prod["sha256"])
