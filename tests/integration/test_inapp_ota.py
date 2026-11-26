"""
In-application OTA updater (ADMIN -> "OTA UPDATE (INTERNET)", and the start-up call _trigger_ota_update(silent_boot=True)).

These tests run the REAL AgriLensApp._trigger_ota_update code of a device's main.py against a local HTTP server that serves a package
folder. Substituted: the GitHub base URL (module constant OTA_REPO_RAW_BASE), the worker thread (run synchronously), and the Tk widgets
(recording stubs). Covered: the first hop with the 4.9.4 code, a 5.0.0 -> 5.0.1 hop with rollback copy, the OTA hold on boot, the
downgrade guard, and refusal of a main.py that does not compile before anything (including the model) is replaced.
"""
import hashlib
import os
import re
import shutil
import threading as _threading

import pytest

from test_ota_publication import FETCHED_BY_4_9_4, LEGACY, PKG, PROD_MODEL, const, next_patch, serve, sha  # noqa: F401  (serve is a fixture)
from conftest import ROOT


class _Widget:
    def __init__(self):
        self.calls = []

    def config(self, **kw):
        self.calls.append(kw)

    configure = config


class _Root:
    def __init__(self):
        self.pending = []

    def after(self, _ms, fn=None, *args):
        if fn is not None:
            self.pending.append((fn, args))
        return len(self.pending)

    def update_idletasks(self):
        pass


class _Stub:
    """Minimal stand-in for the Tk application object: only what _trigger_ota_update and its poll callback touch."""
    def __init__(self):
        self.root = _Root()
        self.ota_status_lbl = _Widget()
        self.ota_btn = _Widget()
        self._ota_in_progress = False
        self.restarted = False

    def _load_splash_logo(self):
        return None

    def _restart_application(self):
        self.restarted = True


_RealThread = _threading.Thread


class _SyncThread(_RealThread):
    """Runs only the OTA worker synchronously; every other thread (e.g. the local HTTP server's) behaves normally."""
    def start(self):
        if getattr(self, "_target", None) is not None and getattr(self._target, "__name__", "") == "ota_worker":
            self._target(*self._args, **self._kwargs)
        else:
            super().start()


def load_device_module(main_path, name):
    import importlib.util
    import sys
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, str(main_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_inapp(main_path, base_url, monkeypatch, home, silent_boot=False):
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    mod = load_device_module(main_path, "agrilens_inapp_ota_%s" % hashlib.sha1(str(main_path).encode()).hexdigest()[:10])
    monkeypatch.setattr(mod, "OTA_REPO_RAW_BASE", base_url)
    monkeypatch.setattr(mod.threading, "Thread", _SyncThread)
    stub = _Stub()
    mod.AgriLensApp._trigger_ota_update(stub, silent_boot=silent_boot)
    for _ in range(10):                      # run the scheduled poll callback(s)
        if not stub.root.pending:
            break
        fn, args = stub.root.pending.pop(0)
        fn(*args)
    texts = " | ".join(str(c.get("text", "")) for c in stub.ota_status_lbl.calls)
    return stub, texts


def make_device(tmp_path, source):
    d = tmp_path / "dev" / "AGRILENS_RaspberryPi"
    if source == "4.9.4":
        (d / "logos").mkdir(parents=True)
        for f in ("main.py", "ota_update.sh", "labels.txt"):
            shutil.copy(os.path.join(LEGACY, f), d / f)
        shutil.copy(PROD_MODEL, d / "agrilens.onnx")
        for f in ("agrilens_logo.jpg", "gundecha_logo.png"):
            shutil.copy(os.path.join(ROOT, "application", "logos", f), d / "logos" / f)
    else:
        shutil.copytree(source, d)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return d, home


def package_variant(tmp_path, name, version=None, break_main=False):
    d = tmp_path / name
    shutil.copytree(PKG, d)
    m = (d / "main.py").read_text(encoding="utf-8")
    if version:
        m = re.sub(r'^APP_VERSION = "[^"]*"', 'APP_VERSION = "%s"' % version, m, count=1, flags=re.M)
    if break_main:
        m = re.sub(r'^MODEL_SHA256 = "[^"]*"', 'MODEL_SHA256 = "%s"' % ("1" * 64), m, count=1, flags=re.M) + "\ndef broken(:\n"
    (d / "main.py").write_text(m, encoding="utf-8", newline="\n")
    return d


def test_inapp_first_hop_from_4_9_4_code(serve, tmp_path, monkeypatch):
    dev, home = make_device(tmp_path, "4.9.4")
    stub, texts = run_inapp(dev / "main.py", serve(PKG), monkeypatch, home)
    assert "OTA Updated to v" in texts and stub.restarted, texts
    for f in FETCHED_BY_4_9_4:
        assert sha(dev / f) == sha(os.path.join(PKG, f)), f


def test_inapp_5_0_0_to_5_0_1_keeps_rollback_and_model(serve, tmp_path, monkeypatch):
    # Historical name: current package -> a synthetic release one PATCH above it (5.0.0 -> 5.0.1 when written).
    cur = const(os.path.join(PKG, "main.py"), "APP_VERSION")
    nxt = next_patch(cur)
    dev, home = make_device(tmp_path, PKG)
    before_main, before_model = sha(dev / "main.py"), sha(dev / "agrilens.onnx")
    stub, texts = run_inapp(dev / "main.py", serve(str(package_variant(tmp_path, "pkgnext", nxt))), monkeypatch, home)
    assert ("OTA Updated to v" + nxt) in texts and stub.restarted, texts
    assert const(dev / "main.py", "APP_VERSION") == nxt
    assert sha(dev / "rollback" / ("v" + cur) / "main.py") == before_main
    assert sha(dev / "agrilens.onnx") == before_model and not (dev / "rollback" / ("v" + cur) / "agrilens.onnx").exists()   # same MODEL_SHA256: no model download


def test_inapp_boot_update_respects_ota_hold(serve, tmp_path, monkeypatch):
    dev, home = make_device(tmp_path, PKG)
    (home / ".agrilens_ota_hold").write_text("hold")
    before = sha(dev / "main.py")
    stub, _ = run_inapp(dev / "main.py", serve(str(package_variant(tmp_path, "pkg501", "5.0.1"))), monkeypatch, home, silent_boot=True)
    assert sha(dev / "main.py") == before and not stub.restarted


def test_inapp_downgrade_is_blocked(serve, tmp_path, monkeypatch):
    dev, home = make_device(tmp_path, PKG)
    old = tmp_path / "old_pkg"
    shutil.copytree(LEGACY, old)
    before = sha(dev / "main.py")
    stub, texts = run_inapp(dev / "main.py", serve(str(old)), monkeypatch, home)
    assert "Downgrade blocked" in texts and sha(dev / "main.py") == before and not stub.restarted


def test_inapp_rejects_uncompilable_main_before_touching_the_model(serve, tmp_path, monkeypatch):
    dev, home = make_device(tmp_path, PKG)
    before_main, before_model = sha(dev / "main.py"), sha(dev / "agrilens.onnx")
    stub, texts = run_inapp(dev / "main.py", serve(str(package_variant(tmp_path, "pkg_broken", "5.0.2", break_main=True))), monkeypatch, home)
    assert "OTA Update failed" in texts and not stub.restarted, texts
    assert sha(dev / "main.py") == before_main and sha(dev / "agrilens.onnx") == before_model


@pytest.mark.parametrize("name", ["main.py"])
def test_both_update_paths_fetch_the_same_files(name):
    """The in-app list and the ota_update.sh list must name the same files (including rollback.sh)."""
    src = open(os.path.join(PKG, "main.py"), encoding="utf-8").read()
    sh = open(os.path.join(PKG, "ota_update.sh"), encoding="utf-8").read()
    inapp = re.findall(r'\(\s*"([^"]+)",\s*os\.path\.join\((?:APP_BASE_DIR|LOGOS_DIR)', src)
    upd = re.findall(r'^\s*"([^"]+\.(?:py|txt|jpg|png|md|sh))",\s*$', sh.split("files = [", 1)[1].split("]", 1)[0], re.M)
    assert set(inapp) == set(upd) and "rollback.sh" in inapp, (inapp, upd)


# ---- device rollback script ------------------------------------------------------------------------------------------
def _bash():
    for c in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe", "/bin/bash"):
        if c and os.path.exists(c):
            return c
    return None


@pytest.mark.skipif(_bash() is None, reason="bash not available")
def test_rollback_script_restores_previous_version_and_sets_hold(tmp_path):
    import subprocess
    import sys
    dev, home = make_device(tmp_path, PKG)
    rb = dev / "rollback" / "v4.9.4"
    (rb / "logos").mkdir(parents=True)
    for f in ("main.py", "ota_update.sh", "labels.txt"):
        shutil.copy(os.path.join(LEGACY, f), rb / f)
    shutil.copy(PROD_MODEL, rb / "agrilens.onnx")
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "python3").write_text('#!/bin/bash\nexec "%s" "$@"\n' % sys.executable.replace("\\", "/"), newline="\n")
    os.chmod(shim / "python3", 0o755)
    to_posix = lambda p: subprocess.run([_bash(), "-c", 'cygpath -u "$0" 2>/dev/null || echo "$0"', str(p)], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, HOME=to_posix(home), PATH=to_posix(shim) + ":" + os.environ.get("PATH", ""))
    listing = subprocess.run([_bash(), to_posix(dev / "rollback.sh")], capture_output=True, text=True, env=env, timeout=60)
    assert "v4.9.4" in listing.stdout, listing.stdout + listing.stderr
    r = subprocess.run([_bash(), to_posix(dev / "rollback.sh"), "v4.9.4"], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert const(dev / "main.py", "APP_VERSION") == "4.9.4" and sha(dev / "agrilens.onnx") == sha(PROD_MODEL)
    assert (home / ".agrilens_ota_hold").exists() and "WARNING" in r.stdout
