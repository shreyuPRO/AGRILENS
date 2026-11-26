#!/bin/bash
# =============================================================================
# AGRILENS Over-The-Air (OTA) Software Updater for Raspberry Pi 5
# Connects to GitHub over the internet, downloads & validates latest updates,
# and automatically restarts the running AGRILENS kiosk if changes were applied.
# Usage:
#   bash ota_update.sh           # Check, update & auto-restart kiosk if changed
#   bash ota_update.sh --force   # Force re-download all files & restart kiosk
# =============================================================================
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

FORCE_FLAG="${1:-}"

python3 - "$APP_DIR" "$FORCE_FLAG" << 'EOF'
import hashlib
import os
import py_compile
import subprocess
import sys
import time
import urllib.request

app_dir = sys.argv[1]
force = (len(sys.argv) > 2 and sys.argv[2] == "--force")
if os.path.exists(os.path.expanduser("~/.agrilens_ota_hold")) and not force:
    print("[AGRILENS OTA] On hold (~/.agrilens_ota_hold present, set by rollback.sh). Use --force or remove the file.")
    sys.exit(0)
raw_base = "https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi"

files = [
    "main.py",
    "labels.txt",
    "logos/agrilens_logo.jpg",
    "logos/gundecha_logo.png",
    "HOW_TO_RUN_ON_RASPBERRY_PI.md",
    "setup_rpi.sh",
    "run_agrilens.sh",
    "ota_update.sh",
    "setup_remote_ota.sh",
    "rollback.sh",
]

os.makedirs(os.path.join(app_dir, "logos"), exist_ok=True)
legacy_assets = os.path.join(app_dir, "assets")
if os.path.exists(legacy_assets):
    import shutil
    shutil.rmtree(legacy_assets, ignore_errors=True)
ts = int(time.time())
updated = 0
remote_ver = "unknown"

def parse_ver(v_str):
    import re
    nums = re.findall(r"\d+", str(v_str or ""))
    return tuple(int(x) for x in nums[:4]) if nums else (0, 0, 0)

def extract_const(text_src, name):
    for line in str(text_src or "").splitlines():
        s = line.strip()
        if s.startswith(name) and "=" in s:
            lhs, rhs = s.split("=", 1)
            if lhs.strip() == name:
                return rhs.split("#", 1)[0].strip().strip('"').strip("'")
    return ""

def extract_ver(text_src):
    return extract_const(text_src, "APP_VERSION") or "0.0.0"

local_ver = "0.0.0"
local_main = os.path.join(app_dir, "main.py")
if os.path.exists(local_main):
    try:
        with open(local_main, "r", encoding="utf-8", errors="replace") as f_loc:
            local_ver = extract_ver(f_loc.read())
    except Exception:
        local_ver = "0.0.0"
local_tuple = parse_ver(local_ver)
rollback_dir = os.path.join(app_dir, "rollback", f"v{local_ver}")

def backup_for_rollback(path):
    """Keeps a copy of the running version's file before it is replaced (first copy wins)."""
    try:
        if os.path.exists(path):
            import shutil
            dst = os.path.join(rollback_dir, os.path.relpath(path, app_dir))
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(path, dst)
    except Exception:
        pass

print(f"[AGRILENS OTA] Local version: v{local_ver}. Connecting to GitHub over internet...")
for rel in files:
    dest = os.path.join(app_dir, rel)
    url = f"{raw_base}/{rel}?t={ts}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AGRILENS-RPi-OTA", "Cache-Control": "no-cache"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception as e:
        if rel == "main.py":
            print(f"[AGRILENS OTA] Internet/GitHub unreachable: {e}")
            sys.exit(0)
        continue

    if not data:
        continue

    if rel == "main.py":
        # compile the downloaded main.py BEFORE the model (or anything else) is replaced
        chk = os.path.join(app_dir, "main.py.ota_check")
        with open(chk, "wb") as f_chk:
            f_chk.write(data)
        try:
            py_compile.compile(chk, doraise=True)
        finally:
            try:
                os.remove(chk)
            except Exception:
                pass
        text_src = data.decode("utf-8", errors="replace")
        remote_ver = extract_ver(text_src)
        remote_model_sha = extract_const(text_src, "MODEL_SHA256").lower()
        remote_tuple = parse_ver(remote_ver)
        # Strict Anti-Downgrade Protection: NEVER allow downgrading to an older version
        if remote_tuple < local_tuple:
            print(f"[AGRILENS OTA] Downgrade blocked: Local v{local_ver} is newer than remote v{remote_ver}.")
            sys.exit(0)

        # Check if trained ONNX model (agrilens.onnx) changed on GitHub via MODEL_SHA256
        model_dest = os.path.join(app_dir, "agrilens.onnx")
        local_model_sha = ""
        if os.path.exists(model_dest):
            try:
                with open(model_dest, "rb") as f_m:
                    local_model_sha = hashlib.sha256(f_m.read()).hexdigest().lower()
            except Exception:
                local_model_sha = ""
        if not os.path.exists(model_dest) or (remote_model_sha and local_model_sha != remote_model_sha):
            print("[AGRILENS OTA] New trained AI model (agrilens.onnx) detected on GitHub! Downloading (~10.07 MB)...")
            m_req = urllib.request.Request(
                f"{raw_base}/agrilens.onnx?t={ts}",
                headers={"User-Agent": "AGRILENS-RPi-OTA", "Cache-Control": "no-cache"}
            )
            with urllib.request.urlopen(m_req, timeout=60) as m_resp:
                m_data = m_resp.read()
            if m_data and len(m_data) > 1000000:
                dl_sha = hashlib.sha256(m_data).hexdigest().lower()
                if not remote_model_sha or dl_sha == remote_model_sha:
                    m_tmp = model_dest + ".ota_tmp"
                    with open(m_tmp, "wb") as f_mout:
                        f_mout.write(m_data)
                    backup_for_rollback(model_dest)
                    os.replace(m_tmp, model_dest)
                    print("[AGRILENS OTA] Updated trained model: agrilens.onnx")
                    updated += 1

    new_hash = hashlib.sha256(data).hexdigest()
    old_hash = ""
    if os.path.exists(dest) and not force:
        try:
            with open(dest, "rb") as f_old:
                old_hash = hashlib.sha256(f_old.read()).hexdigest()
        except Exception:
            old_hash = ""

    if new_hash != old_hash:
        tmp = dest + ".ota_tmp"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(tmp, "wb") as f_out:
            f_out.write(data)
        if rel == "main.py":
            py_compile.compile(tmp, doraise=True)
        backup_for_rollback(dest)
        os.replace(tmp, dest)
        if dest.endswith(".sh"):
            os.chmod(dest, 0o755)
        print(f"[AGRILENS OTA] Updated: {rel}")
        updated += 1

if updated > 0:
    print(f"[AGRILENS OTA] Applied {updated} update(s) -> Version v{remote_ver}.")
    # If AGRILENS kiosk is currently running, restart it cleanly on DISPLAY :0
    res = subprocess.run(["pgrep", "-f", "main.py"], stdout=subprocess.PIPE, text=True)
    pids = [p.strip() for p in res.stdout.splitlines() if p.strip() and int(p.strip()) != os.getpid()]
    if pids:
        print("[AGRILENS OTA] Restarting running AGRILENS kiosk...")
        for pid in pids:
            subprocess.run(["kill", pid], stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XAUTHORITY", os.path.expanduser("~/.Xauthority"))
        subprocess.Popen(
            ["python3", os.path.join(app_dir, "main.py")],
            cwd=app_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("[AGRILENS OTA] Kiosk restarted with new version!")
else:
    print(f"[AGRILENS OTA] Already up to date (v{remote_ver}).")
EOF
