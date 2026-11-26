"""
OTA publication tests for AGRILENS 5.0.0.

Deployed kiosks run the 4.9.4 updater, which downloads a fixed file list from main/AGRILENS_RaspberryPi/ over HTTPS. These tests serve the
generated AGRILENS_RaspberryPi/ folder from a local HTTP server and run the REAL updater code against a fake device folder:
  * first hop: the archived 4.9.4 updater (tests/regression/baseline/legacy_4.9.4/ota_update.sh) upgrades a 4.9.4 device to the package;
  * second hop: the 5.0.0 updater upgrades that device to a synthetic 5.0.1 and must keep a rollback copy; the OTA hold file must stop it.
Only the GitHub base URL and the process-restart call are substituted. Nothing leaves the machine.
"""
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading

import pytest

from conftest import ROOT

PKG = os.path.join(ROOT, "AGRILENS_RaspberryPi")
LEGACY = os.path.join(ROOT, "tests", "regression", "baseline", "legacy_4.9.4")
PROD_MODEL = os.path.join(ROOT, "models", "production", "agrilens-24class-4.9.4", "agrilens.onnx")
GITHUB_BASE = "https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi"
FETCHED_BY_4_9_4 = ["main.py", "labels.txt", "logos/agrilens_logo.jpg", "logos/gundecha_logo.png", "HOW_TO_RUN_ON_RASPBERRY_PI.md",
                    "setup_rpi.sh", "run_agrilens.sh", "ota_update.sh", "setup_remote_ota.sh", "agrilens.onnx"]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def const(path, name):
    m = re.search(r'^%s\s*=\s*"([^"]*)"' % name, open(path, encoding="utf-8").read(), re.M)
    return m.group(1) if m else ""


@pytest.fixture()
def serve():
    servers = []

    def start(folder):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=folder)
        handler.log_message = lambda *a, **k: None
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return "http://127.0.0.1:%d" % srv.server_address[1]

    yield start
    for s in servers:
        s.shutdown()


def updater_body(script_path, base_url):
    """Python body of an ota_update.sh (between << 'EOF' and EOF) with only the base URL and the restart call replaced."""
    text = open(script_path, encoding="utf-8").read()
    body = text.split("<< 'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0]
    assert GITHUB_BASE in body
    body = body.replace(GITHUB_BASE, base_url)
    body = body.replace('res = subprocess.run(["pgrep", "-f", "main.py"], stdout=subprocess.PIPE, text=True)', 'res = type("R", (), {"stdout": ""})()')
    return body


def run_updater(script_path, base_url, device, home, force=False):
    body = updater_body(script_path, base_url)
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PYTHONDONTWRITEBYTECODE="1")
    args = [sys.executable, "-", str(device)] + (["--force"] if force else [])
    return subprocess.run(args, input=body, text=True, capture_output=True, env=env, timeout=180)


@pytest.fixture()
def device_4_9_4(tmp_path):
    d = tmp_path / "AGRILENS_RaspberryPi"
    (d / "logos").mkdir(parents=True)
    for f in ("main.py", "ota_update.sh", "labels.txt"):
        shutil.copy(os.path.join(LEGACY, f), d / f)
    shutil.copy(PROD_MODEL, d / "agrilens.onnx")
    for f in ("agrilens_logo.jpg", "gundecha_logo.png"):
        shutil.copy(os.path.join(ROOT, "application", "logos", f), d / "logos" / f)
    (tmp_path / "home").mkdir()
    return d


# ---- static checks of the publication folder ------------------------------------------------------------------------
def test_package_contains_every_file_deployed_kiosks_fetch():
    missing = [f for f in FETCHED_BY_4_9_4 + ["rollback.sh"] if not os.path.isfile(os.path.join(PKG, f))]
    assert not missing


def test_release_manifest_matches_files():
    man = json.load(open(os.path.join(PKG, "RELEASE_MANIFEST.json"), encoding="utf-8"))
    for rel, h in man["files_sha256"].items():
        assert sha(os.path.join(PKG, rel)) == h, rel
    assert man["app_version"] == const(os.path.join(PKG, "main.py"), "APP_VERSION")


def test_model_sha256_in_main_matches_packaged_model():
    assert const(os.path.join(PKG, "main.py"), "MODEL_SHA256").lower() == sha(os.path.join(PKG, "agrilens.onnx"))


def test_ota_source_urls_are_unchanged_for_deployed_kiosks():
    assert const(os.path.join(PKG, "main.py"), "OTA_REPO_RAW_BASE") == GITHUB_BASE
    assert ('raw_base = "%s"' % GITHUB_BASE) in open(os.path.join(PKG, "ota_update.sh"), encoding="utf-8").read()


def test_labels_are_byte_compatible_with_4_9_4():
    # the release keeps the production class order, so a partial first update cannot mis-map classes
    new = [l.strip() for l in open(os.path.join(PKG, "labels.txt"), encoding="utf-8") if l.strip()]
    old = [l.strip() for l in open(os.path.join(LEGACY, "labels.txt"), encoding="utf-8") if l.strip()]
    assert new == old


def test_package_main_is_newer_than_4_9_4():
    pv = lambda v: tuple(int(x) for x in re.findall(r"\d+", v)[:3])
    assert pv(const(os.path.join(PKG, "main.py"), "APP_VERSION")) > pv(const(os.path.join(LEGACY, "main.py"), "APP_VERSION"))


# ---- first hop: deployed 4.9.4 updater -> 5.0.0 package -------------------------------------------------------------
def test_first_hop_with_the_4_9_4_updater(serve, device_4_9_4):
    url = serve(PKG)
    r = run_updater(os.path.join(LEGACY, "ota_update.sh"), url, device_4_9_4, device_4_9_4.parent / "home")
    assert r.returncode == 0, r.stderr
    for f in FETCHED_BY_4_9_4:
        assert sha(device_4_9_4 / f) == sha(os.path.join(PKG, f)), f
    assert const(device_4_9_4 / "main.py", "APP_VERSION") == const(os.path.join(PKG, "main.py"), "APP_VERSION")


def test_updated_device_starts_and_ignores_stale_4_9_4_thresholds(serve, device_4_9_4):
    import app_harness as H
    url = serve(PKG)
    assert run_updater(os.path.join(LEGACY, "ota_update.sh"), url, device_4_9_4, device_4_9_4.parent / "home").returncode == 0
    app = H.load_app(str(device_4_9_4 / "main.py"))
    clf = app.Classifier(str(device_4_9_4 / "agrilens.onnx"), str(device_4_9_4 / "labels.txt"))
    assert clf.session is not None and clf.mode == "ONNX %s %s" % (app.MODEL_ID, app.MODEL_VERSION)
    stale = {"confidence_threshold": 0.40, "ood_margin": 0.12, "ood_logit": 6.0}   # 4.9.4 device calibration, no calibration_model_sha256
    th, src = app.resolve_gate_thresholds(stale, clf.model_sha256)
    assert th["ood_logit"] == app.MODEL_CALIBRATION_OOD_LOGIT and "calibration" in src


# ---- second hop: 5.0.0 updater -> synthetic 5.0.1 ------------------------------------------------------------------
def next_patch(version):
    """The synthetic next release used for the second hop: current package version with PATCH + 1."""
    major, minor, patch = (int(x) for x in version.split("."))
    return "%d.%d.%d" % (major, minor, patch + 1)


@pytest.fixture()
def fake_5_0_1(tmp_path):
    # Historical name: a synthetic release one PATCH above the current package (5.0.1 when the package was 5.0.0).
    d = tmp_path / "pkg_next"
    shutil.copytree(PKG, d)
    m = (d / "main.py").read_text(encoding="utf-8")
    nxt = next_patch(const(os.path.join(PKG, "main.py"), "APP_VERSION"))
    (d / "main.py").write_text(re.sub(r'^APP_VERSION = "[^"]*"', 'APP_VERSION = "%s"' % nxt, m, count=1, flags=re.M), encoding="utf-8", newline="\n")
    return d


def test_second_hop_keeps_a_rollback_copy(serve, device_4_9_4, fake_5_0_1):
    home = device_4_9_4.parent / "home"
    assert run_updater(os.path.join(LEGACY, "ota_update.sh"), serve(PKG), device_4_9_4, home).returncode == 0
    before = sha(device_4_9_4 / "main.py")
    r = run_updater(str(device_4_9_4 / "ota_update.sh"), serve(str(fake_5_0_1)), device_4_9_4, home)
    assert r.returncode == 0, r.stderr
    assert const(device_4_9_4 / "main.py", "APP_VERSION") == next_patch(const(os.path.join(PKG, "main.py"), "APP_VERSION"))
    rb = device_4_9_4 / "rollback" / ("v" + const(os.path.join(PKG, "main.py"), "APP_VERSION")) / "main.py"
    assert rb.is_file() and sha(rb) == before


def test_ota_hold_stops_the_5_0_0_updater(serve, device_4_9_4, fake_5_0_1):
    home = device_4_9_4.parent / "home"
    assert run_updater(os.path.join(LEGACY, "ota_update.sh"), serve(PKG), device_4_9_4, home).returncode == 0
    (home / ".agrilens_ota_hold").write_text("hold")
    before = sha(device_4_9_4 / "main.py")
    r = run_updater(str(device_4_9_4 / "ota_update.sh"), serve(str(fake_5_0_1)), device_4_9_4, home)
    assert r.returncode == 0 and "On hold" in r.stdout
    assert sha(device_4_9_4 / "main.py") == before


def test_downgrade_is_still_blocked(serve, device_4_9_4):
    home = device_4_9_4.parent / "home"
    assert run_updater(os.path.join(LEGACY, "ota_update.sh"), serve(PKG), device_4_9_4, home).returncode == 0
    old = device_4_9_4.parent / "old_pkg"
    shutil.copytree(LEGACY, old)
    r = run_updater(str(device_4_9_4 / "ota_update.sh"), serve(str(old)), device_4_9_4, home)
    assert "Downgrade blocked" in r.stdout
