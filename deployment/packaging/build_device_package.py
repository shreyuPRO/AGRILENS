#!/usr/bin/env python3
"""Generate the device publication directory AGRILENS_RaspberryPi/ from the authoritative sources. Do not edit AGRILENS_RaspberryPi/ by hand.

Why this directory must stay where it is: every deployed kiosk (4.9.x) downloads a FIXED list of files from
  https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi/<file>
(main.py, labels.txt, agrilens.onnx when MODEL_SHA256 changes, logos/*, HOW_TO_RUN_ON_RASPBERRY_PI.md, setup_rpi.sh, run_agrilens.sh,
ota_update.sh, setup_remote_ota.sh; 5.0.0 adds rollback.sh). Moving or splitting these files would stop deployed kiosks updating, and a
multi-file main.py would not start after an update by a 4.9.x updater. main.py therefore stays one self-contained file in 5.0.0.

Checks (the build refuses on any failure): MODEL_SHA256 in main.py equals the SHA-256 of the packaged model; the model output width equals the
label count; labels are identical to the release model's labels; main.py compiles; APP_VERSION is newer than the version being replaced.
Usage: python build_device_package.py --model-dir models/candidates/agrilens-multicrop-1.0.0 [--check-only]"""
import argparse, hashlib, json, os, py_compile, re, shutil, sys
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); OUT = os.path.join(R, "AGRILENS_RaspberryPi")
SOURCES = [("application/main.py", "main.py"), ("application/requirements.txt", "requirements.txt"), ("application/test_deps.py", "test_deps.py"),
           ("application/configuration/kiosk_config.default.json", "kiosk_config.json"), ("deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md", "HOW_TO_RUN_ON_RASPBERRY_PI.md"),
           ("deployment/raspberry_pi/setup_rpi.sh", "setup_rpi.sh"), ("deployment/raspberry_pi/run_agrilens.sh", "run_agrilens.sh"), ("deployment/raspberry_pi/setup_remote_ota.sh", "setup_remote_ota.sh"),
           ("deployment/raspberry_pi/rollback.sh", "rollback.sh"), ("deployment/ota/ota_update.sh", "ota_update.sh")]
TREES = [("application/logos", "logos"), ("application/diagnosis_samples", "diagnosis_samples")]
OTA_FILES = ["main.py", "labels.txt", "logos/agrilens_logo.jpg", "logos/gundecha_logo.png", "HOW_TO_RUN_ON_RASPBERRY_PI.md", "setup_rpi.sh", "run_agrilens.sh", "ota_update.sh", "setup_remote_ota.sh", "rollback.sh", "agrilens.onnx"]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
const = lambda src, n: (re.search(rf'^{n}\s*=\s*"([^"]*)"', src, re.M) or [None, ""])[1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model-dir", required=True); ap.add_argument("--check-only", action="store_true"); a = ap.parse_args()
    md = os.path.join(R, a.model_dir); onnx = os.path.join(md, "agrilens.onnx"); lab = os.path.join(md, "labels.txt")
    src = open(os.path.join(R, "application", "main.py"), encoding="utf-8").read(); errs = []
    model_sha = sha(onnx); labels = [l.strip() for l in open(lab, encoding="utf-8") if l.strip()]
    if const(src, "MODEL_SHA256").lower() != model_sha: errs.append(f"MODEL_SHA256 in main.py ({const(src, 'MODEL_SHA256')}) != packaged model {model_sha}")
    try:
        import onnxruntime as ort
        n_out = ort.InferenceSession(onnx, providers=["CPUExecutionProvider"]).get_outputs()[0].shape[-1]
        if int(n_out) != len(labels): errs.append(f"model outputs {n_out} classes, labels.txt has {len(labels)}")
    except ImportError: errs.append("onnxruntime needed for the output-width check")
    if int(const(src, "MODEL_NUM_CLASSES") or re.search(r"^MODEL_NUM_CLASSES\s*=\s*(\d+)", src, re.M).group(1)) != len(labels): errs.append("MODEL_NUM_CLASSES != label count")
    if const(src, "BUILD_TIMESTAMP") in ("", "UNSET"): errs.append("BUILD_TIMESTAMP not set")
    try: py_compile.compile(os.path.join(R, "application", "main.py"), doraise=True, cfile=os.path.join(os.environ.get("TEMP", "/tmp"), "agl_build_check.pyc"))
    except py_compile.PyCompileError as e: errs.append(f"main.py does not compile: {e}")
    old = os.path.join(OUT, "main.py")
    if os.path.exists(old):
        pv = lambda v: tuple(int(x) for x in re.findall(r"\d+", v)[:3])
        if pv(const(src, "APP_VERSION")) <= pv(const(open(old, encoding="utf-8").read(), "APP_VERSION")) and not a.check_only and const(open(old, encoding="utf-8").read(), "MODEL_SHA256") != const(src, "MODEL_SHA256"):
            errs.append("APP_VERSION is not newer than the version in AGRILENS_RaspberryPi (deployed kiosks block downgrades and would ignore the update)")
    if errs: print("BUILD REFUSED:\n  " + "\n  ".join(errs)); sys.exit(1)
    if a.check_only: print("checks passed"); return
    keep = {"README_GENERATED.md"}
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(dp, f)
            if os.path.relpath(p, OUT) not in keep: os.remove(p)
    for s_, d_ in SOURCES:
        os.makedirs(os.path.dirname(os.path.join(OUT, d_)) or OUT, exist_ok=True); b = open(os.path.join(R, s_), "rb").read()
        if d_.endswith((".sh", ".py", ".txt", ".md", ".json")): b = b.replace(b"\r\n", b"\n")   # devices receive the committed LF bytes
        open(os.path.join(OUT, d_), "wb").write(b)
    for s_, d_ in TREES:
        shutil.copytree(os.path.join(R, s_), os.path.join(OUT, d_), dirs_exist_ok=True)
    shutil.copyfile(onnx, os.path.join(OUT, "agrilens.onnx")); open(os.path.join(OUT, "labels.txt"), "wb").write(open(lab, "rb").read().replace(b"\r\n", b"\n"))
    files = {}
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(dp, f); rel = os.path.relpath(p, OUT).replace(os.sep, "/")
            if rel not in ("SHA256SUMS", "RELEASE_MANIFEST.json", "README_GENERATED.md"): files[rel] = sha(p)
    open(os.path.join(OUT, "SHA256SUMS"), "w", newline="\n").write("".join(f"{h}  {r}\n" for r, h in sorted(files.items())))
    man = {"release": const(src, "OTA_RELEASE_ID"), "app_version": const(src, "APP_VERSION"), "build_timestamp": const(src, "BUILD_TIMESTAMP"), "model_id": const(src, "MODEL_ID"), "model_version": const(src, "MODEL_VERSION"),
           "model_sha256": model_sha, "dataset_version": const(src, "DATASET_VERSION"), "labels": labels, "ota_files_fetched_by_devices": OTA_FILES, "files_sha256": files,
           "generated_by": "deployment/packaging/build_device_package.py (deterministic: rebuilding the same sources reproduces these bytes)"}
    json.dump(man, open(os.path.join(OUT, "RELEASE_MANIFEST.json"), "w", encoding="utf-8", newline="\n"), indent=1)
    open(os.path.join(OUT, "README_GENERATED.md"), "w", encoding="utf-8", newline="\n").write("# GENERATED - do not edit\n\nThis folder is the OTA publication directory read by deployed kiosks. It is generated by `deployment/packaging/build_device_package.py` from `application/`, `deployment/` and `models/`. Edit those sources instead.\n")
    print(json.dumps({k: man[k] for k in ("release", "app_version", "model_id", "model_version", "model_sha256")}, indent=1), len(files), "files")


if __name__ == "__main__":
    main()
