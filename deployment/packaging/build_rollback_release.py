#!/usr/bin/env python3
"""Prepare (never publish) the fleet rollback release AGRILENS-5.0.1-rollback: the unmodified 4.9.4 application and production model, with only
APP_VERSION raised to 5.0.1 and BUILD_TIMESTAMP set. Deployed updaters block downgrades, so a fleet rollback after 5.0.0 must carry a HIGHER version.
Output: deployment/rollback/AGRILENS-5.0.1-rollback/ (a complete AGRILENS_RaspberryPi-style folder) with SHA256SUMS and ROLLBACK_MANIFEST.json.
To use it, follow documentation/technical/ROLLBACK.md (copy the folder over AGRILENS_RaspberryPi/, run the tests, publish with explicit approval)."""
import datetime as dt, hashlib, json, os, re, shutil
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); OUT = os.path.join(R, "deployment", "rollback", "AGRILENS-5.0.1-rollback")
LEG = os.path.join(R, "tests", "regression", "baseline", "legacy_4.9.4"); PROD = os.path.join(R, "models", "production", "agrilens-24class-4.9.4")
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, "logos"))
src = open(os.path.join(LEG, "main.py"), encoding="utf-8").read()
assert src.count('APP_VERSION = "4.9.4"') == 1
src = src.replace('APP_VERSION = "4.9.4"', 'APP_VERSION = "5.0.1"', 1)
src = re.sub(r'^BUILD_TIMESTAMP = "[^"]*"', 'BUILD_TIMESTAMP = "%s (rollback of 5.0.0 to the 4.9.4 application and model)"' % dt.date.today(), src, count=1, flags=re.M)
open(os.path.join(OUT, "main.py"), "w", encoding="utf-8", newline="\n").write(src)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
assert re.search(r'^MODEL_SHA256 = "([0-9a-f]{64})"', src, re.M).group(1) == sha(os.path.join(PROD, "agrilens.onnx"))
shutil.copyfile(os.path.join(PROD, "agrilens.onnx"), os.path.join(OUT, "agrilens.onnx"))
open(os.path.join(OUT, "labels.txt"), "wb").write(open(os.path.join(LEG, "labels.txt"), "rb").read())
shutil.copyfile(os.path.join(LEG, "ota_update.sh"), os.path.join(OUT, "ota_update.sh"))
for f in ("agrilens_logo.jpg", "gundecha_logo.png"): shutil.copyfile(os.path.join(R, "application", "logos", f), os.path.join(OUT, "logos", f))
for s_, d_ in (("deployment/raspberry_pi/HOW_TO_RUN_ON_RASPBERRY_PI.md", "HOW_TO_RUN_ON_RASPBERRY_PI.md"), ("deployment/raspberry_pi/setup_rpi.sh", "setup_rpi.sh"), ("deployment/raspberry_pi/run_agrilens.sh", "run_agrilens.sh"),
               ("deployment/raspberry_pi/setup_remote_ota.sh", "setup_remote_ota.sh"), ("deployment/raspberry_pi/rollback.sh", "rollback.sh"), ("application/requirements.txt", "requirements.txt"), ("application/test_deps.py", "test_deps.py"),
               ("application/configuration/kiosk_config.default.json", "kiosk_config.json")):
    open(os.path.join(OUT, d_), "wb").write(open(os.path.join(R, s_), "rb").read().replace(b"\r\n", b"\n"))
shutil.copytree(os.path.join(R, "application", "diagnosis_samples"), os.path.join(OUT, "diagnosis_samples"))
files = {}
for dp, _, fs in os.walk(OUT):
    for f in fs:
        p = os.path.join(dp, f); files[os.path.relpath(p, OUT).replace(os.sep, "/")] = sha(p)
open(os.path.join(OUT, "SHA256SUMS"), "w", newline="\n").write("".join(f"{h}  {r}\n" for r, h in sorted(files.items())))
json.dump({"release": "AGRILENS-5.0.1-rollback", "app_version": "5.0.1", "application_code": "4.9.4 (unchanged except APP_VERSION and BUILD_TIMESTAMP)", "model": "AGRILENS-24CLASS 4.9.4-production", "model_sha256": files["agrilens.onnx"],
           "status": "PREPARED, NOT PUBLISHED. Publish only on an explicit rollback decision.", "files_sha256": files}, open(os.path.join(OUT, "ROLLBACK_MANIFEST.json"), "w", encoding="utf-8", newline="\n"), indent=1)
print("rollback release prepared:", OUT, len(files), "files")
