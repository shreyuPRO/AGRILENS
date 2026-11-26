#!/bin/bash
# AGRILENS - Raspberry Pi environment report (DRAFT). READ-ONLY: changes nothing, installs nothing.
# Usage:  bash collect_pi_environment.sh | tee ~/agrilens_env_report.txt
# Run it as the user that runs the kiosk (not with sudo) so user-level settings are visible.

section() { printf '\n===== %s =====\n' "$1"; }
run()     { printf '$ %s\n' "$*"; "$@" 2>&1 || echo "(exit $?)"; }

section "Identity / time"
run date -Is
run hostname
run whoami
run id

section "Hardware and OS"
run cat /proc/device-tree/model; echo
run cat /etc/os-release
run uname -a
run cat /etc/rpi-issue
run vcgencmd version
run vcgencmd get_throttled
run vcgencmd measure_temp
run bash -c 'cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
run free -h
run df -h / /home
run bash -c 'mount | grep -E " / | /boot"'

section "Desktop session (kiosk needs this)"
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE  XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP  DISPLAY=$DISPLAY  WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
run bash -c 'ps -eo comm | grep -E "wayfire|labwc|Xorg|Xwayland|lxsession" | sort -u'
run bash -c 'grep -E "autologin" /etc/lightdm/lightdm.conf 2>/dev/null; raspi-config nonint get_autologin 2>/dev/null'

section "Python installation type"
run which -a python3 python
run python3 --version
run python3 -c "import sys,sysconfig;print('exe',sys.executable);print('prefix',sys.prefix);print('base_prefix',sys.base_prefix);print('in_venv',sys.prefix!=sys.base_prefix);print('purelib',sysconfig.get_paths()['purelib'])"
run bash -c 'ls /usr/lib/python3*/EXTERNALLY-MANAGED 2>/dev/null || echo "no EXTERNALLY-MANAGED marker (PEP 668 not enforced)"'
run bash -c 'echo "VIRTUAL_ENV=${VIRTUAL_ENV:-<none>}"'
run bash -c 'find ~ -maxdepth 3 -name pyvenv.cfg 2>/dev/null'
run python3 -m pip --version

section "Python packages (how installed: apt vs pip)"
run python3 - <<'PY'
import importlib, importlib.metadata as md
for m, dist in [("numpy","numpy"),("PIL","pillow"),("cv2","opencv-python"),("onnxruntime","onnxruntime"),
                ("cryptography","cryptography"),("tkinter",None)]:
    try:
        mod = importlib.import_module(m)
        ver = getattr(mod, "__version__", None) or (md.version(dist) if dist else "n/a")
        print(f"{m:14} {ver:12} {getattr(mod,'__file__','')}")
    except Exception as e:
        print(f"{m:14} MISSING ({e})")
import tkinter; print("Tk version", tkinter.TkVersion)
try:
    import onnxruntime as ort; print("ORT providers", ort.get_available_providers())
except Exception: pass
PY
run bash -c 'python3 -m pip list 2>/dev/null | grep -iE "numpy|pillow|opencv|onnx|cryptography"'
run bash -c 'dpkg -l | grep -iE "python3-(numpy|opencv|pil|tk|cryptography)|libopencv|openssl "'
run openssl version
run bash -c 'openssl list -public-key-algorithms 2>/dev/null | grep -i ed25519'

section "Camera"
run v4l2-ctl --list-devices
run bash -c 'ls -l /dev/video* 2>/dev/null'
run bash -c 'groups'

section "AGRILENS installation"
run bash -c 'ls -la ~ | grep -i agrilens'
run bash -c 'ls -la ~/AGRILENS_RaspberryPi 2>/dev/null'
run bash -c 'grep -m1 "^APP_VERSION" ~/AGRILENS_RaspberryPi/main.py 2>/dev/null'
run bash -c 'sha256sum ~/AGRILENS_RaspberryPi/agrilens.onnx ~/AGRILENS_RaspberryPi/labels.txt 2>/dev/null'
run bash -c 'ls -la ~/.agrilens_kiosk_config.json ~/AGRILENS_RaspberryPi/kiosk_config.json 2>/dev/null'
echo "--- config contents (no secrets are stored in these files):"
run bash -c 'cat ~/.agrilens_kiosk_config.json 2>/dev/null; echo; cat ~/AGRILENS_RaspberryPi/kiosk_config.json 2>/dev/null'
run bash -c 'ls -la ~/.config/autostart/ 2>/dev/null; cat ~/.config/autostart/agrilens.desktop 2>/dev/null'
run bash -c 'cat ~/.config/labwc/autostart 2>/dev/null; grep -n agrilens ~/.config/wayfire.ini 2>/dev/null'
run bash -c 'crontab -l 2>/dev/null'

section "systemd"
run systemctl status agrilens-ota.service --no-pager
run systemctl cat agrilens-ota.service
run systemctl is-enabled agrilens-ota.service agrilens-ota.timer
run systemctl list-unit-files --no-pager 'agrilens*'
run systemctl --user list-unit-files --no-pager 'agrilens*'
run bash -c 'journalctl -u agrilens-ota.service --no-pager -n 40'
run bash -c 'loginctl show-user "$USER" -p Linger'
run bash -c 'systemctl is-active network-online.target; nmcli -t -f DEVICE,STATE,CONNECTION dev 2>/dev/null'

section "Remote access"
run bash -c 'systemctl is-enabled ssh; systemctl is-active ssh'
run bash -c 'sshd -T 2>/dev/null | grep -iE "passwordauthentication|permitrootlogin|pubkeyauthentication|port "'
run bash -c 'ls -la ~/.ssh 2>/dev/null | sed "s/authorized_keys.*/authorized_keys (present)/"'
run bash -c 'rpi-connect status 2>/dev/null'

section "Running AGRILENS processes"
run bash -c 'pgrep -af "main.py|agrilens" || echo none'
echo
echo "Report finished. It contains hostname, username and network device names; review before sharing."
