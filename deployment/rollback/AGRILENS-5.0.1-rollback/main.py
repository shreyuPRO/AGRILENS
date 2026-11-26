#!python3.13
"""
AGRILENS - AI Plant Health & Disease Diagnosis Kiosk
Target Runtime: Python 3.13+
Hardware: Raspberry Pi 5 (8GB) + 7" Capacitive Touch Display + USB Webcam
Model: MobileNetV4 (ONNX) - 98.31% Accuracy
Features:
- Separate [CAPTURE] / [RETAKE] and [DIAGNOSE] buttons
- Integrated Leaf Image Quality AI (Sharpness, Lighting & Foliage Presence check)
- 30% Confidence Threshold with Auto (Beta Production) mode
- Blue [ADMIN] Button with Webcam Detection and Close Application
"""

import io
import os
import sys
import json
import glob
import subprocess
import platform
import queue
import random
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import filedialog
import tkinter.font as tkFont
from collections import deque

# Automatically include Raspberry Pi OS system package paths in sys.path
for _p in [
    "/usr/lib/python3/dist-packages",
    "/usr/local/lib/python3/dist-packages",
    "/usr/lib/python3.13/dist-packages",
    "/usr/lib/python3.11/dist-packages",
]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.append(_p)

def _auto_install_package(import_name, pip_name=None):
    if pip_name is None:
        pip_name = import_name
    try:
        return __import__(import_name)
    except ImportError:
        print(f"[AGRILENS] Missing '{pip_name}'. Auto-installing for {sys.executable}...")
        for cmd in [
            [sys.executable, "-m", "pip", "install", pip_name, "--break-system-packages"],
            [sys.executable, "-m", "pip", "install", pip_name],
        ]:
            try:
                subprocess.check_call(cmd)
                print(f"[AGRILENS] Successfully installed '{pip_name}'.")
                return __import__(import_name)
            except Exception:
                pass
        return None

# Resilient Pillow & ImageTk import (supports Pillow 7.x through 13.x+, Windows & Raspberry Pi OS)
try:
    from PIL import Image, ImageOps, ImageDraw, ImageEnhance
except ImportError:
    _auto_install_package("PIL", "pillow")
    try:
        from PIL import Image, ImageOps, ImageDraw, ImageEnhance
    except ImportError:
        raise SystemExit(
            "Pillow is missing!\n"
            "PC / Windows: Tools -> Manage packages... -> install 'pillow' (or pip install pillow)\n"
            "Raspberry Pi: sudo apt install -y python3-pil python3-pil.imagetk"
        )

# Resampling compatibility across all Pillow versions (<9.1, 9.x, 10+, 13+)
_RESAMPLE_ENUM = getattr(Image, "Resampling", Image)
RESAMPLE_BILINEAR = getattr(_RESAMPLE_ENUM, "BILINEAR", getattr(Image, "BILINEAR", 2))
RESAMPLE_LANCZOS = getattr(_RESAMPLE_ENUM, "LANCZOS", getattr(Image, "ANTIALIAS", 1))
RESAMPLE = RESAMPLE_BILINEAR

# Resilient ImageTk wrapper with native Tkinter fallback (fixes missing _imagingtk C module on Linux)
try:
    from PIL import ImageTk as _PIL_ImageTk
    from PIL import _imagingtk  # noqa: F401
    _HAS_IMAGINGTK = True
except Exception:
    _PIL_ImageTk = None
    _HAS_IMAGINGTK = False


class ImageTk:
    """Drop-in replacement for PIL.ImageTk that works with or without the _imagingtk C module."""
    @staticmethod
    def PhotoImage(image=None, **kwargs):
        if _HAS_IMAGINGTK and _PIL_ImageTk is not None:
            try:
                return _PIL_ImageTk.PhotoImage(image, **kwargs)
            except Exception:
                pass
        if image is not None:
            bio = io.BytesIO()
            image.save(bio, format="PNG", compress_level=1)
            return tk.PhotoImage(data=bio.getvalue(), **kwargs)
        return tk.PhotoImage(**kwargs)

try:
    import numpy as np
except ImportError:
    _auto_install_package("numpy", "numpy")
    try:
        import numpy as np
    except ImportError:
        np = None

try:
    import cv2
except ImportError:
    cv2 = None

# =============================================================================
# 1. COLOR THEME (Dark Theme with Green, White & Red Accents)
# =============================================================================
# Dark Backgrounds
BG     = "#08100a"       # Obsidian forest dark background
PANEL  = "#0e1a12"       # Dark foliage slate panel
CARD   = "#15261a"       # Component card container
BORDER = "#213d29"       # Crisp dark green border

# Pure White & Crisp Text
WHITE  = "#ffffff"       # Crisp pure white
TEXT   = "#f8fafc"       # Clean off-white
MUTED  = "#94a3b8"       # Silver slate secondary text
DARK   = "#041208"       # Dark text on bright white or bright green buttons

# Green Theme Shades (Primary / Healthy / Confirm)
GREEN_PRIMARY = "#16a34a"   # Emerald Lush Green
GREEN_ACCENT  = "#22c55e"   # Bright vibrant leaf green
GREEN_GLOW    = "#4ade80"   # Light highlight green
GREEN_HOVER   = "#15803d"   # Darker green hover

# Red Accents (Disease Alert / Close / Critical)
RED_ALERT   = "#ef4444"     # Vivid disease warning & [CLOSE APPLICATION]
RED_HOVER   = "#dc2626"     # Deep red hover
RED_CARD    = "#2d1212"     # Subtle dark red card background

# Secondary & Status
AMBER_WARN  = "#f59e0b"     # Out-of-catalog warning & [RETAKE]
GREY_BTN    = "#283b2f"     # Subtle card buttons
WHITE_BTN   = "#ffffff"     # High-contrast white buttons

FONT = "Segoe UI" if platform.system() == "Windows" else "DejaVu Sans"

# Application Version & Build Information
APP_VERSION = "5.0.1"
BUILD_TIMESTAMP = "2026-11-17 (rollback of 5.0.0 to the 4.9.4 application and model)"
MODEL_SHA256 = "0b5bb7fb3916a7c1138f90cfc9abfdc130f06495a34282d474e52718b072ff80"
OTA_REPO_RAW_BASE = "https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi"


def _parse_version_tuple(v_str):
    """Parses a semantic version string like '4.8.2' into a comparable integer tuple (4, 8, 2)."""
    try:
        clean = str(v_str or "").strip().lstrip("vV")
        parts = []
        for p in clean.split("."):
            num = "".join(ch for ch in p if ch.isdigit())
            parts.append(int(num) if num else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def _extract_const_from_code(text_src, const_name):
    """Extracts a top-level string constant (e.g. APP_VERSION or MODEL_SHA256) from main.py source."""
    for line in str(text_src or "").splitlines():
        s = line.strip()
        if s.startswith(const_name) and "=" in s:
            lhs, rhs = s.split("=", 1)
            if lhs.strip() == const_name:
                val = rhs.split("#", 1)[0].strip().strip('"').strip("'")
                if val:
                    return val
    return ""


def _extract_version_from_code(text_src):
    """Extracts APP_VERSION = 'X.Y.Z' from a main.py source string."""
    return _extract_const_from_code(text_src, "APP_VERSION") or "0.0.0"

# Startup Splash & Inactivity Power-Save Timers
STARTUP_LOGO_SECONDS = 5.0
INACTIVITY_TIMEOUT_SECONDS = 180.0  # 3 minutes of inactivity before screensaver

# =============================================================================
# 2. PATH DISCOVERY & SETTINGS
# =============================================================================
CANDIDATE_MODEL_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "model") if "__file__" in globals() else "",
    os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "",
    os.path.join(os.getcwd(), "model"),
    os.getcwd(),
    r"C:\Users\Shreyance Engineer\.gemini\antigravity\scratch\agrilens_ui\model",
    r"G:\My Drive\EXPISCOR 2026",
    "/home/pi/agrilens_ui/model",
    "/home/pi/agrilens_ui",
]

def find_file(filename):
    for d in CANDIDATE_MODEL_DIRS:
        if d and os.path.exists(d):
            p = os.path.join(d, filename)
            if os.path.exists(p):
                return p
    return filename

MODEL_PATH = find_file("agrilens.onnx")
LABELS_PATH = find_file("labels.txt")

APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
LOGOS_DIR = os.path.join(APP_BASE_DIR, "logos")
CANDIDATE_LOGO_DIRS = [
    LOGOS_DIR,
    os.path.join(os.getcwd(), "logos"),
    os.path.join(os.path.dirname(APP_BASE_DIR), "logos"),
]


def find_logo_file(filename):
    """Resolves logo images exclusively from the dedicated logos/ folder."""
    try:
        os.makedirs(LOGOS_DIR, exist_ok=True)
    except Exception:
        pass
    for d in CANDIDATE_LOGO_DIRS:
        if d and os.path.exists(d):
            p = os.path.join(d, filename)
            if os.path.exists(p):
                return p
    return os.path.join(LOGOS_DIR, filename)


DIAGNOSIS_SAMPLES_DIR = os.path.join(APP_BASE_DIR, "diagnosis_samples")
DIAGNOSIS_SPECIES_FOLDERS = ("Apple", "Mango", "Potato", "Tomato")


def ensure_diagnosis_samples_dir():
    """Ensures the fixed folder structure diagnosis_samples/{Apple,Mango,Potato,Tomato} exists."""
    try:
        os.makedirs(DIAGNOSIS_SAMPLES_DIR, exist_ok=True)
        for sp in DIAGNOSIS_SPECIES_FOLDERS:
            os.makedirs(os.path.join(DIAGNOSIS_SAMPLES_DIR, sp), exist_ok=True)
    except Exception:
        pass
    return DIAGNOSIS_SAMPLES_DIR

# Calibrated confidence & Out-Of-Distribution (OOD) rejection thresholds (Tuned for Mobile Phone Screen & Field Leaves)
CONFIDENCE_THRESHOLD = 0.40  # Minimum positive identification threshold (40%)
OOD_MARGIN_THRESHOLD = 0.12  # Minimum gap between 1st and 2nd class (12%)
OOD_LOGIT_THRESHOLD  = 1.40  # Minimum raw logit activation for supported crops
SHARPNESS_MIN_THRESHOLD = 25.0  # Minimum spatial Laplacian focus sharpness variance

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk_config.json") if "__file__" in globals() else "kiosk_config.json"
USER_CONFIG_PATH = os.path.expanduser("~/.agrilens_kiosk_config.json")
DEFAULT_CONFIG = {
    "confidence_threshold": CONFIDENCE_THRESHOLD,
    "ood_margin": OOD_MARGIN_THRESHOLD,
    "ood_logit": OOD_LOGIT_THRESHOLD,
    "sharpness_min": SHARPNESS_MIN_THRESHOLD,
    "cam_contrast": 100,
    "cam_brightness": 0,
    "cam_saturation": 100,
    "cam_sharpness": 100,
    "cam_wb_temp": 0,
    "cam_zoom": 100,
    "cam_flip_h": False,
    "cam_flip_v": False,
    "cam_auto_exp": True,
    "cam_auto_wb": True,
    "language": "EN",
}

def _clamp_num(val, default, lo, hi, as_int=False):
    try:
        v = float(val)
        v = max(float(lo), min(float(hi), v))
        return int(round(v)) if as_int else v
    except Exception:
        return int(default) if as_int else float(default)


def load_kiosk_config():
    cfg = dict(DEFAULT_CONFIG)
    for path in (CONFIG_PATH, USER_CONFIG_PATH):
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cfg.update(data)
            except Exception as e:
                print(f"Notice: loading config from {path} ({e})")

    # Sanitize & clamp loaded parameters so corrupted JSON values never break startup
    cfg["confidence_threshold"] = _clamp_num(cfg.get("confidence_threshold"), CONFIDENCE_THRESHOLD, 0.30, 0.95)
    cfg["ood_margin"] = _clamp_num(cfg.get("ood_margin"), OOD_MARGIN_THRESHOLD, 0.10, 0.60)
    cfg["ood_logit"] = _clamp_num(cfg.get("ood_logit"), OOD_LOGIT_THRESHOLD, 1.00, 6.50)
    cfg["sharpness_min"] = _clamp_num(cfg.get("sharpness_min"), SHARPNESS_MIN_THRESHOLD, 20.0, 120.0)

    # Auto-migrate legacy stricter thresholds in ~/.agrilens_kiosk_config.json to mobile-screen-friendly defaults
    if cfg["ood_logit"] >= 1.80 and cfg["confidence_threshold"] >= 0.48:
        cfg["confidence_threshold"] = CONFIDENCE_THRESHOLD
        cfg["ood_margin"] = OOD_MARGIN_THRESHOLD
        cfg["ood_logit"] = OOD_LOGIT_THRESHOLD
        cfg["sharpness_min"] = SHARPNESS_MIN_THRESHOLD

    cfg["cam_contrast"] = _clamp_num(cfg.get("cam_contrast"), 100, 50, 200, as_int=True)
    cfg["cam_brightness"] = _clamp_num(cfg.get("cam_brightness"), 0, -50, 50, as_int=True)
    cfg["cam_saturation"] = _clamp_num(cfg.get("cam_saturation"), 100, 0, 200, as_int=True)
    cfg["cam_sharpness"] = _clamp_num(cfg.get("cam_sharpness"), 100, 50, 250, as_int=True)
    cfg["cam_wb_temp"] = _clamp_num(cfg.get("cam_wb_temp"), 0, -50, 50, as_int=True)
    cfg["cam_zoom"] = _clamp_num(cfg.get("cam_zoom"), 100, 100, 200, as_int=True)
    for bkey, bdef in (("cam_flip_h", False), ("cam_flip_v", False), ("cam_auto_exp", True), ("cam_auto_wb", True)):
        val = cfg.get(bkey, bdef)
        cfg[bkey] = val if isinstance(val, bool) else bdef
    cfg["language"] = "HI" if str(cfg.get("language", "EN")).upper() == "HI" else "EN"
    return cfg

def save_kiosk_config(cfg):
    for path in (USER_CONFIG_PATH, CONFIG_PATH):
        if not path:
            continue
        try:
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o666)
                except Exception:
                    pass
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
        except Exception as e:
            print(f"Notice: unable to save kiosk config to {path} ({e})")

def ensure_rpi_autostart():
    """
    Automatically registers AGRILENS to launch immediately on Raspberry Pi boot
    (zero-delay XDG + Wayfire/Labwc compositor autostart) to skip showing the home screen.
    If launched from a removable USB pendrive (/media or /mnt), automatically syncs
    the latest package to ~/AGRILENS_RaspberryPi on the Raspberry Pi SD card.
    """
    if platform.system() != "Linux" or "__file__" not in globals():
        return
    try:
        import shutil
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        if script_dir.startswith("/media/") or script_dir.startswith("/mnt/"):
            home_target = os.path.expanduser("~/AGRILENS_RaspberryPi")
            try:
                installed_main = os.path.join(home_target, "main.py")
                allow_copy = True
                if os.path.exists(installed_main):
                    with open(installed_main, "r", encoding="utf-8", errors="replace") as f_inst:
                        inst_ver = _extract_version_from_code(f_inst.read())
                    if _parse_version_tuple(APP_VERSION) < _parse_version_tuple(inst_ver):
                        # Never overwrite a newer installed version with an older USB copy
                        allow_copy = False
                if allow_copy:
                    shutil.copytree(script_dir, home_target, dirs_exist_ok=True)
                    # Remove legacy assets/ directory on Raspberry Pi SD card if present
                    legacy_assets = os.path.join(home_target, "assets")
                    if os.path.exists(legacy_assets):
                        shutil.rmtree(legacy_assets, ignore_errors=True)
                script_dir = home_target
                script_path = os.path.join(home_target, "main.py")
            except Exception:
                pass
        py_exe = sys.executable or "/usr/bin/python3"
        launch_cmd = f"/bin/sh -c \"cd '{script_dir}' && '{py_exe}' '{script_path}'\""

        # 1. XDG Autostart (launches automatically on desktop session start)
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_file = os.path.join(autostart_dir, "agrilens.desktop")
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=AGRILENS Kiosk\n"
            "Comment=AGRILENS AI Plant Health Kiosk Auto-Start\n"
            f"Exec={launch_cmd}\n"
            f"Path={script_dir}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        with open(desktop_file, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(desktop_file, 0o755)

        # Clean up any duplicate compositor autostart entries so only one instance launches on boot
        wf_ini = os.path.expanduser("~/.config/wayfire.ini")
        if os.path.exists(wf_ini):
            try:
                with open(wf_ini, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                cleaned = [ln for ln in lines if "agrilens_kiosk" not in ln]
                if len(cleaned) != len(lines):
                    with open(wf_ini, "w", encoding="utf-8") as f:
                        f.writelines(cleaned)
            except Exception:
                pass

        labwc_auto = os.path.expanduser("~/.config/labwc/autostart")
        if os.path.exists(labwc_auto):
            try:
                with open(labwc_auto, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                cleaned = [ln for ln in lines if script_path not in ln]
                if len(cleaned) != len(lines):
                    with open(labwc_auto, "w", encoding="utf-8") as f:
                        f.writelines(cleaned)
            except Exception:
                pass
    except Exception as e:
        print(f"Notice: autostart registration skipped ({e})")

ADMIN_PASSWORD = "AGRILENS"
PREVIEW_FPS = 25
RESAMPLE = RESAMPLE_BILINEAR

# =============================================================================
# 3. FARMER RECOMMENDATIONS DATABASE (Bilingual: English & Hindi)
# =============================================================================
DISCLAIMER = (
    "Agricultural advice only. Consult your local extension officer "
    "before applying chemical treatments."
)
DISCLAIMER_HI = (
    "यह केवल कृषि परामर्श है। रासायनिक उपचार करने से पहले अपने स्थानीय "
    "कृषि विस्तार अधिकारी से सलाह लें।"
)

CROP_HI_MAP = {
    "apple": "सेब (Apple)",
    "mango": "आम (Mango)",
    "potato": "आलू (Potato)",
    "tomato": "टमाटर (Tomato)",
}

CONDITION_HI_MAP = {
    "healthy": "स्वस्थ पत्ती (Healthy)",
    "rust": "रस्ट / किट्ट रोग (Rust)",
    "scab": "स्कैब / पपड़ी रोग (Scab)",
    "anthracnose": "एन्थ्रेक्नोज़ (Anthracnose)",
    "bacterial canker": "जीवाणु कैंकर (Bacterial Canker)",
    "cutting weevil": "कटिंग वीविल कीट (Cutting Weevil)",
    "die back": "डाई-बैक रोग (Die Back)",
    "gall midge": "गॉल मिज कीट (Gall Midge)",
    "powdery mildew": "चूर्णिल आसिता (Powdery Mildew)",
    "sooty mould": "सूटी मोल्ड / काली फफूंद (Sooty Mould)",
    "early blight": "अगेती झुलसा (Early Blight)",
    "late blight": "पछेती झुलसा (Late Blight)",
    "bacterial spot": "जीवाणु धब्बा रोग (Bacterial Spot)",
    "leaf mold": "पत्ती की फफूंद (Leaf Mold)",
    "septoria leaf spot": "सेप्टोरिया पत्ती धब्बा (Septoria Leaf Spot)",
    "spider mites two spotted spider mite": "लाल मकड़ी कीट (Spider Mites)",
    "target spot": "टारगेट स्पॉट (Target Spot)",
    "tomato yellowleaf curl virus": "पीला पत्ता मरोड़ वायरस (Yellow Leaf Curl Virus)",
    "tomato mosaic virus": "मोज़ेक वायरस (Mosaic Virus)",
}


def translate_crop_hi(crop_name):
    if not crop_name:
        return ""
    return CROP_HI_MAP.get(str(crop_name).strip().lower(), str(crop_name))


def translate_cond_hi(cond_name):
    if not cond_name:
        return ""
    low = str(cond_name).strip().lower()
    if low in CONDITION_HI_MAP:
        return CONDITION_HI_MAP[low]
    for k, v in CONDITION_HI_MAP.items():
        if k in low:
            return v
    return str(cond_name)


RECOMMENDATIONS = [
    (("healthy",), [
        "The crop shows healthy leaf tissue. No chemical spray is required.",
        "Water at the base early in the morning; keep the foliage dry.",
        "Inspect lower leaves weekly for early signs of spots or insects.",
        "Maintain clean soil borders and remove fallen debris from the bed.",
    ]),
    (("scab",), [
        "Remove and safely burn or bury infected leaves to stop fungal spores.",
        "Prune crowded branches to let sunlight and drying winds circulate.",
        "Apply recommended protective fungicide (e.g., Mancozeb or Captan).",
        "Avoid overhead watering that keeps leaves wet through the night.",
    ]),
    (("black rot",), [
        "Prune dead twigs and cankered branches 15 cm below infected margins.",
        "Collect and destroy all mummified fruit and infected leaf fall.",
        "Spray an approved protective fungicide from bud burst to petal fall.",
        "Always disinfect pruning shears with alcohol between every tree.",
    ]),
    (("rust", "cedar apple rust"), [
        "Check and remove any wild juniper/cedar host bushes within 500 m.",
        "Apply recommended fungicides at the pink-bud and petal-fall stages.",
        "Rake and destroy fallen autumn foliage to prevent winter carryover.",
    ]),
    (("bacterial spot",), [
        "Immediately pick and dispose of spotted foliage; never work while wet.",
        "Apply copper-based bactericide sprays as directed by local guidelines.",
        "Use drip irrigation to prevent water splashing spores onto foliage.",
        "Practice crop rotation with non-solanaceous crops for 2-3 years.",
    ]),
    (("early blight",), [
        "Prune lower infected leaves; burn or bury them (do not compost).",
        "Apply clean organic mulch to prevent rain splashing spores from soil.",
        "Spray recommended fungicide (e.g., Mancozeb or Chlorothalonil).",
        "Rotate fields next season; avoid planting tomato after potato.",
    ]),
    (("late blight",), [
        "URGENT: Highly contagious blight that spreads rapidly in cool damp air.",
        "Immediately uproot and destroy severely infected tomato plants.",
        "Apply systemic fungicide immediately to protect adjacent healthy plants.",
        "Stop all overhead sprinkler irrigation immediately.",
    ]),
    (("leaf mold",), [
        "Increase spacing between plants and prune lower suckers for airflow.",
        "Ventilate field or greenhouse thoroughly to lower relative humidity.",
        "Spray approved protective copper or sulfur fungicide if spread continues.",
    ]),
    (("septoria",), [
        "Pinch off infected lower leaves as soon as circular spots appear.",
        "Keep ground mulched and keep overhead water away from leaves.",
        "Apply protective fungicide sprays on a 7 to 10 day schedule.",
    ]),
    (("spider mite",), [
        "Spray undersides of leaves with a forceful jet of clean water.",
        "Apply organic neem oil extract or insecticidal soap every 5-7 days.",
        "Maintain regular irrigation; spider mites thrive in dry dusty heat.",
    ]),
    (("target spot",), [
        "Remove lower infected foliage to reduce fungal spore pressure.",
        "Improve plant spacing and stake vines to boost canopy airflow.",
        "Apply recommended protective fungicide (e.g., Chlorothalonil or Mancozeb).",
        "Use drip irrigation and mulch to prevent soil splash onto lower leaves.",
    ]),
    (("yellow leaf curl",), [
        "Viral infection transmitted by whiteflies. Plants cannot be cured.",
        "Uproot and bag diseased plants immediately to protect neighbors.",
        "Install yellow sticky traps and reflective mulch to deter whiteflies.",
        "Select certified TYLCV-resistant seedlings for your next cycle.",
    ]),
    (("mosaic",), [
        "Viral disease. Remove and safely dispose of infected plants.",
        "Disinfect hands and tools with soap and water after handling plants.",
        "Do not allow smoking or tobacco handling near tomato crops.",
    ]),
    (("anthracnose",), [
        "Prune dead twigs, diseased leaves, and dry inflorescences.",
        "Spray Copper Oxychloride (0.3%) before flowering and after harvest.",
        "Prune the tree canopy to allow sun to penetrate internal branches.",
    ]),
    (("powdery mildew",), [
        "Spray wettable sulfur (0.2%) or Hexaconazole at panicle emergence.",
        "Prune overcrowded shoots to lower internal canopy humidity.",
        "Collect and burn fallen infested flower panicles.",
    ]),
    (("die back", "dieback"), [
        "Cut infected twigs 8-10 cm below the visible margin of dried wood.",
        "Immediately paint cut surfaces with fresh Bordeaux paste.",
        "Maintain balanced tree nutrition with recommended NPK and zinc.",
    ]),
    (("bacterial canker",), [
        "Prune cankered branches and treat wound surfaces with copper spray.",
        "Spray Streptocycline (100 ppm) combined with copper oxychloride.",
        "Plant protective windbreaks to prevent wind-borne leaf abrasions.",
    ]),
    (("sooty mo",), [
        "Black fungus grows on sweet honeydew secreted by hoppers or mealybugs.",
        "Spray 2% dilute starch solution or neem oil to flake off soot layer.",
        "Treat the underlying sucking pests (mango hoppers or scale insects).",
    ]),
    (("cutting weevil", "gall midge"), [
        "Collect and safely dispose of clipped or deformed gall-bearing leaves.",
        "Spray approved botanical or neem-based insecticide at new leaf flush.",
        "Plow the soil beneath the canopy to expose overwintering pupae.",
    ]),
]

RECOMMENDATIONS_HI = [
    (("healthy",), [
        "फसल की पत्ती पूरी तरह स्वस्थ है। किसी रासायनिक छिड़काव की आवश्यकता नहीं है।",
        "सुबह जल्दी पौधे की जड़ में पानी दें; पत्तियों को सूखा रखें।",
        "धब्बों या कीटों के शुरुआती लक्षणों के लिए हर सप्ताह निचली पत्तियों की जाँच करें।",
        "खेत की मेड़ों को साफ़ रखें और गिरी हुई सूखी पत्तियों को हटा दें।",
    ]),
    (("scab",), [
        "फफूंद के बीजाणुओं को रोकने के लिए संक्रमित पत्तियों को हटाकर नष्ट कर दें।",
        "धूप और हवा के प्रवाह के लिए घनी शाखाओं की छंटाई करें।",
        "अनुशंसित कवकनाशी (जैसे मैंकोज़ेब या कैप्टान) का छिड़काव करें।",
        "रात के समय पत्तियों को गीला रखने वाली ऊपरी सिंचाई से बचें।",
    ]),
    (("black rot",), [
        "संक्रमित हिस्से से 15 सेमी नीचे से सूखी और रोगग्रस्त टहनियों को काटें।",
        "सभी सड़े हुए फलों और गिरी हुई संक्रमित पत्तियों को इकट्ठा करके नष्ट करें।",
        "कली निकलने से लेकर फूल आने तक अनुमोदित सुरक्षात्मक कवकनाशी का छिड़काव करें।",
        "प्रत्येक पेड़ की छंटाई के बाद कैंची को अल्कोहल से कीटाणुरहित करें।",
    ]),
    (("rust", "cedar apple rust"), [
        "500 मीटर के दायरे में जंगली जुनिपर/देवदार की झाड़ियों की जाँच करें और हटाएं।",
        "कली बनने और पंखुड़ी गिरने की अवस्था में अनुशंसित कवकनाशी का छिड़काव करें।",
        "सर्दियों में रोग को फैलने से रोकने के लिए गिरी हुई पत्तियों को नष्ट करें।",
    ]),
    (("bacterial spot",), [
        "धब्बेदार पत्तियों को तुरंत तोड़कर नष्ट करें; गीली फसल में काम न करें।",
        "स्थानीय कृषि दिशानिर्देशों के अनुसार कॉपर-आधारित जीवाणुनाशक का छिड़काव करें।",
        "पानी के छींटों से संक्रमण रोकने के लिए ड्रिप सिंचाई का उपयोग करें।",
        "2-3 वर्षों तक गैर-सोलेनेसी फसलों के साथ फसल चक्र अपनाएं।",
    ]),
    (("early blight",), [
        "निचली संक्रमित पत्तियों को काटकर जला दें या मिट्टी में दबा दें (कम्पोस्ट न बनाएं)।",
        "मिट्टी से फफूंद के छींटे रोकने के लिए साफ़ जैविक पलवार (मल्च) बिछाएं।",
        "अनुशंसित कवकनाशी (जैसे मैंकोज़ेब या क्लोरोथालोनिल) का छिड़काव करें।",
        "अगले सीजन में फसल चक्र अपनाएं; आलू के बाद टमाटर न लगाएं।",
    ]),
    (("late blight",), [
        "अति आवश्यक: यह संक्रामक झुलसा रोग ठंडी और नमी वाली हवा में तेज़ी से फैलता है।",
        "गंभीर रूप से संक्रमित पौधों को तुरंत उखाड़कर नष्ट कर दें।",
        "आस-पास के स्वस्थ पौधों को बचाने के लिए तुरंत सिस्टेमिक कवकनाशी का छिड़काव करें।",
        "फव्वारा (स्प्रिंकलर) सिंचाई तुरंत बंद कर दें।",
    ]),
    (("leaf mold",), [
        "हवा के प्रवाह के लिए पौधों के बीच की दूरी बढ़ाएं और निचली शाखाओं की छंटाई करें।",
        "नमी कम करने के लिए खेत या पॉलीहाउस में हवा का उचित वेंटिलेशन रखें।",
        "यदि संक्रमण बढ़ता है, तो अनुमोदित कॉपर या सल्फर कवकनाशी का छिड़काव करें।",
    ]),
    (("septoria",), [
        "गोल धब्बे दिखते ही निचली संक्रमित पत्तियों को तोड़कर हटा दें।",
        "जमीन पर पलवार (मल्च) रखें और पत्तियों के ऊपर से पानी न डालें।",
        "7 से 10 दिनों के अंतराल पर सुरक्षात्मक कवकनाशी का छिड़काव करें।",
    ]),
    (("spider mite",), [
        "पत्तियों के निचले हिस्से पर साफ़ पानी की तेज़ धार से छिड़काव करें।",
        "हर 5-7 दिनों में नीम के तेल (Neem Oil) या कीटनाशक साबुन का छिड़काव करें।",
        "नियमित सिंचाई बनाए रखें; लाल मकड़ी कीट सूखे और गर्म मौसम में तेजी से बढ़ते हैं।",
    ]),
    (("target spot",), [
        "फफूंद के दबाव को कम करने के लिए निचली संक्रमित पत्तियों को हटा दें।",
        "हवा के बेहतर प्रवाह के लिए पौधों को सहारा (स्टेकिंग) दें और दूरी बनाए रखें।",
        "अनुशंसित कवकनाशी (जैसे क्लोरोथालोनिल या मैंकोज़ेब) का छिड़काव करें।",
        "निचली पत्तियों पर मिट्टी के छींटे रोकने के लिए ड्रिप सिंचाई और मल्च का प्रयोग करें।",
    ]),
    (("yellow leaf curl",), [
        "यह सफेद मक्खी (Whitefly) से फैलने वाला वायरस रोग है; संक्रमित पौधा ठीक नहीं हो सकता।",
        "पड़ोसी पौधों को बचाने के लिए रोगग्रस्त पौधों को तुरंत उखाड़कर नष्ट करें।",
        "सफेद मक्खी को नियंत्रित करने के लिए पीले चिपचिपे ट्रैप (Yellow Sticky Traps) लगाएं।",
        "अगली फसल के लिए प्रमाणित रोग-प्रतिरोधी (TYLCV-resistant) किस्म के पौधे चुनें।",
    ]),
    (("mosaic",), [
        "यह एक विषाणु (वायरस) जनित रोग है। संक्रमित पौधों को उखाड़कर सुरक्षित रूप से नष्ट करें।",
        "पौधों को छूने के बाद हाथों और औजारों को साबुन और पानी से अच्छी तरह धोएं।",
        "टमाटर की फसल के पास धूम्रपान या तंबाकू के उपयोग से सख़्त परहेज करें।",
    ]),
    (("anthracnose",), [
        "सूखी टहनियों, रोगग्रस्त पत्तियों और सूखे फूलों के गुच्छों की छंटाई करें।",
        "फूल आने से पहले और तुड़ाई के बाद कॉपर ऑक्सीक्लोराइड (0.3%) का छिड़काव करें।",
        "पेड़ के भीतरी हिस्सों में धूप पहुँचाने के लिए घनी शाखाओं की छंटाई करें।",
    ]),
    (("powdery mildew",), [
        "मंजरी निकलते समय घुलनशील सल्फर (0.2%) या हेक्साकोनाज़ोल का छिड़काव करें।",
        "नमी कम करने के लिए घनी टहनियों की छंटाई करें।",
        "नीचे गिरे हुए संक्रमित फूलों के गुच्छों को इकट्ठा करके जला दें।",
    ]),
    (("die back", "dieback"), [
        "सूखी लकड़ी के दिखने वाले हिस्से से 8-10 सेमी नीचे से संक्रमित टहनियों को काटें।",
        "कटे हुए हिस्सों पर तुरंत ताज़ा बोर्डो पेस्ट (Bordeaux paste) लगाएं।",
        "अनुशंसित NPK और जिंक के साथ पेड़ का संतुलित पोषण बनाए रखें।",
    ]),
    (("bacterial canker",), [
        "कैंकर वाली शाखाओं की छंटाई करें और घावों पर कॉपर स्प्रे का उपचार करें।",
        "कॉपर ऑक्सीक्लोराइड के साथ स्ट्रेप्टोसाइक्लिन (100 ppm) का छिड़काव करें।",
        "तेज़ हवा से पत्तियों को होने वाली रगड़ से बचाने के लिए वायुरोधक पेड़ लगाएं।",
    ]),
    (("sooty mo",), [
        "यह काली फफूंद फुदका (Hoppers) या मिलीबग द्वारा छोड़े गए मीठे चिपचिपे पदार्थ पर पनपती है।",
        "काली परत को हटाने के लिए 2% स्टार्च घोल या नीम के तेल का छिड़काव करें।",
        "रस चूसने वाले मुख्य कीटों (मैंगो हॉपर या स्केल कीट) का उपचार करें।",
    ]),
    (("cutting weevil", "gall midge"), [
        "कटी हुई या गांठ (गॉल) वाली विकृत पत्तियों को इकट्ठा करके नष्ट कर दें।",
        "नई पत्तियां निकलते समय अनुमोदित वानस्पतिक या नीम-आधारित कीटनाशक का छिड़काव करें।",
        "मिट्टी में छिपे प्यूपा को नष्ट करने के लिए पेड़ के नीचे की मिट्टी की जुताई करें।",
    ]),
]

UNSURE_STEPS = [
    "Check the Image Quality rating shown below the camera view.",
    "Hold one single leaf flat and fully centered inside the green box.",
    "Make sure lighting is even and there is no harsh direct glare or shadow.",
    "Auto mode is in Beta Production. Tap 'SELECT CROP' to focus on your crop.",
]

UNSURE_STEPS_HI = [
    "कैमरा दृश्य के नीचे दिखाई गई 'पत्ती गुणवत्ता (Image Quality)' रेटिंग की जाँच करें।",
    "एक पत्ती को सीधा रखें और हरे बॉक्स के बिल्कुल बीच में रखें।",
    "सुनिश्चित करें कि रोशनी समान हो और पत्ती पर सीधी चमक या गहरी छाया न हो।",
    "बेहतर सटीकता के लिए ऊपर 'फसल चुनें' बटन दबाकर अपनी फसल निर्धारित करें।",
]

OOD_STEPS = [
    "This leaf does not match features of supported crops (Apple, Mango, Potato, Tomato).",
    "Non-target plants (e.g. money plant, ornamental flora, weeds) are outside catalog.",
    "If diagnosing a supported crop, tap 'SELECT CROP' to lock your target crop.",
    "To support this plant species, add it to the dataset and retrain the model.",
]

OOD_STEPS_HI = [
    "यह पत्ती समर्थित फसलों (सेब, आम, आलू, टमाटर) के लक्षणों से मेल नहीं खाती है।",
    "अन्य पौधे (जैसे सजावटी पौधे, खरपतवार आदि) वर्तमान सूची से बाहर हैं।",
    "यदि आप समर्थित फसल की जाँच कर रहे हैं, तो ऊपर 'फसल चुनें' दबाकर फसल लॉक करें।",
    "केवल सेब, आम, आलू या टमाटर की स्पष्ट पत्ती को कैमरे के सामने रखें।",
]

DEFAULT_STEPS = [
    "Possible crop condition observed on this specimen.",
    "Isolate this plant to prevent potential spread to adjacent rows.",
    "Bring this leaf sample to your local agricultural office for inspection.",
    "Avoid overhead watering to minimize standing leaf moisture.",
]

DEFAULT_STEPS_HI = [
    "इस पत्ती के नमूने में फसल रोग के संभावित लक्षण देखे गए हैं।",
    "संक्रमण को आस-पास के पौधों में फैलने से रोकने के लिए इस पौधे को अलग रखें।",
    "निरीक्षण के लिए इस पत्ती के नमूने को अपने स्थानीय कृषि कार्यालय में दिखाएं।",
    "पत्तियों पर नमी कम करने के लिए ऊपर से पानी छिड़कने से बचें।",
]

def get_recommendation(crop, condition, lang="EN"):
    text = f"{crop} {condition}".lower()
    db = RECOMMENDATIONS_HI if str(lang).upper() == "HI" else RECOMMENDATIONS
    for keys, steps in db:
        if any(k in text for k in keys):
            return steps
    return DEFAULT_STEPS_HI if str(lang).upper() == "HI" else DEFAULT_STEPS


def parse_label(label):
    clean = label.strip()
    while "__" in clean:
        clean = clean.replace("__", "_")
    healthy = "healthy" in clean.lower()
    if ("other" in clean.lower()) or ("background" in clean.lower()):
        return "", clean.replace("_", " ").title(), False
    for sep in (" - ", ": ", "_"):
        if sep in clean:
            parts = clean.split(sep, 1)
            crop = parts[0].replace("_", " ").title().strip()
            cond = parts[1].replace("_", " ").title().strip()
            return crop, cond, healthy
    return "", clean.replace("_", " ").title(), healthy


# =============================================================================
# 4. LEAF IMAGE QUALITY AI (Sharpness, Lighting & Foliage Validator)
# =============================================================================
class LeafQualityAI:
    """
    Evaluates leaf image quality for field disease diagnostics:
    1. Sharpness / Focus (Motion blur & focus detection via spatial high-freq gradients)
    2. Lighting & Exposure (Luminance distribution & specular glare / darkness check)
    3. Foliage & Leaf Presence (Excess Green Index & central leaf coverage check)
    """
    @staticmethod
    def assess(pil_image, min_sharpness=55.0, lang="EN"):
        is_hi = (str(lang).upper() == "HI")
        if np is None or pil_image is None:
            return (
                80,
                "GOOD",
                "पत्ती गुणवत्ता: उपयुक्त" if is_hi else "Image Quality: Acceptable",
                GREEN_ACCENT,
            )

        try:
            # Resize thumbnail for fast 1ms evaluation
            thumb = pil_image.resize((224, 224), RESAMPLE)
            arr = np.asarray(thumb.convert("RGB"), dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

            # 1. Luminance & Exposure check
            gray = 0.299 * r + 0.587 * g + 0.114 * b
            mean_lum = float(np.mean(gray))

            if mean_lum < 36.0:
                exposure_score = max(10, int(mean_lum * 1.5))
                lighting_status = "कम रोशनी (रोशनी बढ़ाएं)" if is_hi else "Too Dark (Increase Phone Brightness)"
            elif mean_lum > 238.0:
                exposure_score = max(15, int((255 - mean_lum) * 2.5))
                lighting_status = "अधिक चमक / ग्लेयर (थोड़ा झुकाएं)" if is_hi else "Screen Glare / Too Bright (Tilt Phone Slightly)"
            else:
                exposure_score = min(100, int(100 - abs(mean_lum - 135) * 0.38))
                lighting_status = "अच्छी रोशनी" if is_hi else "Good Lighting"

            # 2. Sharpness / Blur check (Spatial Laplacian variance)
            lap = (
                gray[1:-1, :-2] + gray[1:-1, 2:] +
                gray[:-2, 1:-1] + gray[2:, 1:-1] -
                4.0 * gray[1:-1, 1:-1]
            )
            sharp_var = float(np.var(lap))

            # Calibrated sharpness scoring relative to min_sharpness
            base_s = max(10.0, float(min_sharpness))
            if sharp_var > (base_s * 4.0):
                sharpness_score = 98
                sharp_status = "साफ़ और स्पष्ट फ़ोकस" if is_hi else "Sharp & In Focus"
            elif sharp_var > (base_s * 2.0):
                sharpness_score = int(70 + (sharp_var - base_s * 2.0) * (28.0 / (base_s * 2.0)))
                sharp_status = "अच्छा फ़ोकस" if is_hi else "Good Focus"
            elif sharp_var >= base_s:
                sharpness_score = int(45 + (sharp_var - base_s) * (25.0 / base_s))
                sharp_status = "हल्का धुंधला" if is_hi else "Slightly Blurry"
            else:
                sharpness_score = max(10, int(sharp_var * (45.0 / base_s)))
                sharp_status = "धुंधला चित्र (Blurry)" if is_hi else "Blurry (Motion Blur)"

            # 3. Leaf Presence (Center Box Coverage via Excess Green Index: 2G - R - B)
            h, w = arr.shape[:2]
            y0, y1 = int(h * 0.2), int(h * 0.8)
            x0, x1 = int(w * 0.2), int(w * 0.8)
            center_g = g[y0:y1, x0:x1]
            center_r = r[y0:y1, x0:x1]
            center_b = b[y0:y1, x0:x1]

            exg = 2.0 * center_g - center_r - center_b
            leaf_pixels = np.mean((exg > 4.0) | ((center_g >= center_r * 0.90) & (center_g > 28.0)))

            if leaf_pixels > 0.35:
                presence_score = 95
                presence_status = "पत्ती केंद्र में है" if is_hi else "Leaf Centered"
            elif leaf_pixels > 0.18:
                presence_score = 75
                presence_status = "आंशिक पत्ती" if is_hi else "Partial Leaf"
            else:
                presence_score = 30
                presence_status = "बॉक्स में पत्ती नहीं है" if is_hi else "No Leaf in Box"

            # Composite Quality Score (0 - 100%)
            overall_score = int(0.40 * sharpness_score + 0.30 * exposure_score + 0.30 * presence_score)
            overall_score = max(5, min(99, overall_score))

            # Verdict & Color
            if overall_score >= 75 and sharpness_score >= 60 and exposure_score >= 50:
                rating = "EXCELLENT"
                msg = (
                    f"गुणवत्ता: {overall_score}% (साफ़ और स्पष्ट - जाँच के लिए तैयार)"
                    if is_hi else
                    f"Quality: {overall_score}% (Sharp & Clear - Ready to Diagnose)"
                )
                color = GREEN_ACCENT
            elif overall_score >= 50:
                rating = "GOOD"
                msg = f"गुणवत्ता: {overall_score}% ({sharp_status})" if is_hi else f"Quality: {overall_score}% ({sharp_status})"
                color = GREEN_PRIMARY
            elif sharpness_score < 45:
                rating = "POOR"
                msg = (
                    f"गुणवत्ता: {overall_score}% ({sharp_status} — स्थिर रखें और फिर से फोटो लें)"
                    if is_hi else
                    f"Quality: {overall_score}% ({sharp_status} — Hold still & Retake)"
                )
                color = AMBER_WARN
            elif exposure_score < 45:
                rating = "POOR"
                msg = (
                    f"गुणवत्ता: {overall_score}% ({lighting_status} — रोशनी ठीक करें)"
                    if is_hi else
                    f"Quality: {overall_score}% ({lighting_status} — Adjust Light)"
                )
                color = AMBER_WARN
            else:
                rating = "POOR"
                msg = (
                    f"गुणवत्ता: {overall_score}% ({presence_status} — पत्ती को बॉक्स के बीच में रखें)"
                    if is_hi else
                    f"Quality: {overall_score}% ({presence_status} — Center Leaf in Box)"
                )
                color = RED_ALERT

            return overall_score, rating, msg, color

        except Exception as e:
            return 75, "GOOD", (f"गुणवत्ता: तैयार ({e})" if is_hi else f"Quality: Ready ({e})"), GREEN_ACCENT


# =============================================================================
# 5. WEBCAM INTERFACE (Multi-Backend, High-Speed Video Capture)
# =============================================================================
class Camera:
    def __init__(self, auto_detect=True):
        self._lock = threading.Lock()
        self.cap = None
        self.cv2 = None
        self.kind = "none"
        self.port = -1
        self.last_working_port = -1
        self.backend = "none"
        self.width = 640
        self.height = 480
        self.device_name = "USB Camera"
        self.fail_count = 0

        # USB Hardware + ISP Parameters
        self.contrast = 100      # 50% to 200% (100% = neutral)
        self.brightness = 0      # -50% to +50% (0% = neutral)
        self.saturation = 100    # 0% to 200% (100% = neutral)
        self.sharpness = 100     # 50% to 250% (100% = neutral)
        self.wb_temp = 0         # -50 (Cool) to +50 (Warm) (0 = neutral)
        self.zoom = 100          # 100% (1.0x) to 200% (2.0x Macro Zoom)
        self.flip_h = False      # Mirror horizontally
        self.flip_v = False      # Flip vertically (180 deg)
        self.auto_exp = True     # USB UVC Auto-Exposure + Backlight Compensation
        self.auto_wb = True      # USB UVC Auto White Balance
        self.focus_peaking = False  # Neon edge highlight for Manual Focus Mod

        # Silence noisy OpenCV C++ backend/obsensor log spam
        try:
            import cv2
            self.cv2 = cv2
            self.cv2.utils.logging.setLogLevel(self.cv2.utils.logging.LOG_LEVEL_ERROR)
        except Exception:
            pass

        if auto_detect:
            self.detect_webcam()

    def _fetch_friendly_names_async(self):
        """Discovers friendly hardware device names in background without blocking the UI."""
        def worker():
            names = []
            if sys.platform.startswith("win"):
                try:
                    cmd = ["powershell", "-NoProfile", "-Command",
                           "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    for line in res.stdout.splitlines():
                        clean = line.strip()
                        if clean and clean not in names:
                            names.append(clean)
                except Exception:
                    pass
            elif sys.platform.startswith("linux"):
                for p in sorted(glob.glob("/sys/class/video4linux/video*/name")):
                    try:
                        with open(p, "r") as f:
                            n = f.read().strip()
                            if n and n not in names:
                                names.append(n)
                    except Exception:
                        pass
            if names and self.kind != "none":
                dev = names[self.port] if (0 <= self.port < len(names)) else names[0]
                self.device_name = dev
                self.kind = f"{dev} (Port {self.port}, {self.backend}, {self.width}x{self.height})"
        threading.Thread(target=worker, daemon=True).start()

    def detect_webcam(self):
        """
        Fast, high-robustness camera scanner using prioritized platform backends:
        - Windows: DirectShow (CAP_DSHOW) -> Default (CAP_ANY)
        - Linux/RPi: Video4Linux2 (CAP_V4L2) -> Default (CAP_ANY)
        Configures resolution, buffersize, and warm-up reads before locking connection.
        """
        with self._lock:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

            if self.cv2 is None:
                try:
                    import cv2
                    self.cv2 = cv2
                    self.cv2.utils.logging.setLogLevel(self.cv2.utils.logging.LOG_LEVEL_ERROR)
                except ImportError:
                    self.kind = "none"
                    return False, "OpenCV (cv2) is not installed."

            # Build prioritized backend list
            if sys.platform.startswith("win"):
                backends = [
                    ("DirectShow", self.cv2.CAP_DSHOW),
                    ("Default", self.cv2.CAP_ANY)
                ]
            elif sys.platform.startswith("linux"):
                backends = [
                    ("V4L2", self.cv2.CAP_V4L2),
                    ("Default", self.cv2.CAP_ANY)
                ]
            else:
                backends = [("Default", self.cv2.CAP_ANY)]

            # Probe ports with cascading backends (prioritize last working port for instant wake-up)
            ports_order = (
                [self.last_working_port] + [p for p in range(3) if p != self.last_working_port]
                if self.last_working_port >= 0 else list(range(3))
            )
            for b_name, b_id in backends:
                for port in ports_order:
                    try:
                        c = self.cv2.VideoCapture(port, b_id)
                        if not c.isOpened():
                            continue

                        # Configure 640x480 resolution & single-frame buffer before reading
                        c.set(self.cv2.CAP_PROP_FRAME_WIDTH, 640)
                        c.set(self.cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        try:
                            c.set(self.cv2.CAP_PROP_BUFFERSIZE, 1)
                        except Exception:
                            pass

                        # Multi-frame warmup: Allow auto-exposure (AEC) and auto-gain (AGC) to stabilize
                        ok, frame = False, None
                        for _ in range(4):
                            ok, frame = c.read()
                            if ok and frame is not None and frame.size > 0:
                                break
                            time.sleep(0.025)

                        if ok and frame is not None and frame.size > 0:
                            h, w = frame.shape[:2]
                            self.cap = c
                            self.port = port
                            self.last_working_port = port
                            self.backend = b_name
                            self.width = w
                            self.height = h
                            self.device_name = "USB Camera"
                            self.kind = f"USB Camera (Port {port}, {b_name}, {w}x{h})"
                            self.fail_count = 0
                            break

                        c.release()
                    except Exception:
                        pass
                if self.cap is not None:
                    break

            if self.cap is None:
                self.kind = "none"
                self.port = -1
                self.backend = "none"
                return False, "No active webcam found. Please plug in USB camera and click DETECT WEBCAM."

        # Apply USB hardware controls & query friendly model name outside the lock
        self.apply_hardware_controls()
        self._fetch_friendly_names_async()
        return True, f"Connected: {self.kind}"

    def apply_hardware_controls(self):
        """Pushes UVC hardware parameters (Auto-Exposure, 50Hz Anti-Flicker, Auto-WB) over USB."""
        if not self.cap or self.cv2 is None:
            return
        port = self.port
        auto_exp = self.auto_exp
        auto_wb = self.auto_wb
        wb_kelvin = int(4500 + self.wb_temp * 34)

        def _hw_worker():
            with self._lock:
                if self.cap and self.cap.isOpened() and self.cv2 is not None:
                    try:
                        if hasattr(self.cv2, "CAP_PROP_AUTO_EXPOSURE"):
                            # V4L2 UVC: 3 = Aperture Priority (Auto), 1 = Manual
                            self.cap.set(self.cv2.CAP_PROP_AUTO_EXPOSURE, 3 if auto_exp else 1)
                        if hasattr(self.cv2, "CAP_PROP_BACKLIGHT"):
                            self.cap.set(self.cv2.CAP_PROP_BACKLIGHT, 1 if auto_exp else 0)
                        if hasattr(self.cv2, "CAP_PROP_AUTO_WB"):
                            self.cap.set(self.cv2.CAP_PROP_AUTO_WB, 1 if auto_wb else 0)
                        if not auto_wb and hasattr(self.cv2, "CAP_PROP_WB_TEMPERATURE"):
                            self.cap.set(self.cv2.CAP_PROP_WB_TEMPERATURE, wb_kelvin)
                    except Exception:
                        pass

            if sys.platform.startswith("linux") and port >= 0:
                dev = f"/dev/video{port}"
                exp_val = 3 if auto_exp else 1
                bl_val = 1 if auto_exp else 0
                awb_val = 1 if auto_wb else 0
                cmds = [
                    ["v4l2-ctl", "-d", dev, "-c", f"power_line_frequency=1,exposure_auto={exp_val},backlight_compensation={bl_val},white_balance_temperature_auto={awb_val}"],
                ]
                if not auto_wb:
                    cmds.append(["v4l2-ctl", "-d", dev, "-c", f"white_balance_temperature={wb_kelvin}"])
                for cmd in cmds:
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                    except Exception:
                        pass

        threading.Thread(target=_hw_worker, daemon=True).start()

    def _apply_isp(self, img):
        """Real-time Image Signal Processing (ISP) pipeline for USB frames."""
        try:
            # 1. Orientation Flips (Mirror / 180 Vertical Flip)
            if self.flip_h:
                img = img.transpose(getattr(Image, "Transpose", Image).FLIP_LEFT_RIGHT)
            if self.flip_v:
                img = img.transpose(getattr(Image, "Transpose", Image).FLIP_TOP_BOTTOM)

            # 2. Macro Digital Zoom (100% = 1.0x to 200% = 2.0x center crop)
            if self.zoom > 102:
                w, h = img.size
                zf = max(1.0, min(2.0, self.zoom / 100.0))
                cw, ch = max(16, int(w / zf)), max(16, int(h / zf))
                x0 = (w - cw) // 2
                y0 = (h - ch) // 2
                img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), RESAMPLE)

            # 3. White Balance Warmth Tint (-50 Cool to +50 Warm)
            if abs(self.wb_temp) >= 2 and np is not None:
                arr = np.asarray(img, dtype=np.int16)
                shift = int(self.wb_temp * 0.9)
                arr[:, :, 0] = np.clip(arr[:, :, 0] + shift, 0, 255)   # Red warmth
                arr[:, :, 2] = np.clip(arr[:, :, 2] - shift, 0, 255)   # Blue coolness
                img = Image.fromarray(arr.astype(np.uint8))

            # 4. Brightness (-50% to +50% -> factor 0.50 to 1.50)
            if abs(self.brightness) >= 1:
                bf = max(0.3, 1.0 + (self.brightness / 100.0))
                img = ImageEnhance.Brightness(img).enhance(bf)

            # 5. Contrast (50% to 200% -> factor 0.50 to 2.00)
            if abs(self.contrast - 100) >= 1:
                cf = max(0.3, self.contrast / 100.0)
                img = ImageEnhance.Contrast(img).enhance(cf)

            # 6. Saturation / Color Vibrancy (0% to 200% -> factor 0.00 to 2.00)
            if abs(self.saturation - 100) >= 1:
                sf = max(0.0, self.saturation / 100.0)
                img = ImageEnhance.Color(img).enhance(sf)

            # 7. Sharpness / Leaf Vein Detail (50% to 250% -> factor 0.50 to 2.50)
            if abs(self.sharpness - 100) >= 2:
                shf = max(0.2, self.sharpness / 100.0)
                img = ImageEnhance.Sharpness(img).enhance(shf)
        except Exception:
            pass
        return img

    def compute_focus_metric(self, img):
        """Computes real-time focus sharpness (0-100%) for calibrating the manual focus ring."""
        if np is None or img is None:
            return 75, 50.0
        try:
            small = img.resize((240, 180), RESAMPLE)
            arr = np.asarray(small, dtype=np.float32)
            gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            h, w = gray.shape
            c = gray[int(h * 0.15):int(h * 0.85), int(w * 0.15):int(w * 0.85)]
            lap = (
                -4.0 * c[1:-1, 1:-1]
                + c[:-2, 1:-1] + c[2:, 1:-1]
                + c[1:-1, :-2] + c[1:-1, 2:]
            )
            lap_var = float(np.var(lap))
            pct = int(max(5, min(100, (lap_var / 140.0) * 100.0)))
            return pct, lap_var
        except Exception:
            return 70, 50.0

    def render_focus_peaking(self, img):
        """Highlights razor-sharp leaf veins/edges in neon green when twisting the manual focus ring."""
        if not self.focus_peaking or np is None or img is None:
            return img
        try:
            arr = np.asarray(img, dtype=np.uint8).copy()
            gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
            gx = np.abs(gray[:, 2:] - gray[:, :-2])[1:-1, :]
            gy = np.abs(gray[2:, :] - gray[:-2, :])[:, 1:-1]
            mag = gx + gy
            mask = mag > 42.0
            sub = arr[1:-1, 1:-1]
            sub[mask] = [0, 255, 110]
            return Image.fromarray(arr)
        except Exception:
            return img

    def read(self):
        """Reads the latest camera frame, applies ISP controls, and handles dropped signals."""
        with self._lock:
            if not self.cap or not self.cap.isOpened():
                return None
            try:
                ok, frame = self.cap.read()
                if ok and frame is not None and frame.size > 0:
                    self.fail_count = 0
                    rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
                else:
                    self.fail_count += 1
                    if self.fail_count > 30:  # ~1 second of continuous frame drops
                        try:
                            self.cap.release()
                        except Exception:
                            pass
                        self.cap = None
                        self.kind = "none"
                    return None
            except Exception:
                self.fail_count += 1
                if self.fail_count > 30:
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    self.cap = None
                    self.kind = "none"
                return None
        pil_img = Image.fromarray(rgb)
        return self._apply_isp(pil_img)

    def close(self):
        """Safely releases and powers down the hardware camera handle."""
        with self._lock:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            self.kind = "none"
            self.port = -1


# =============================================================================
# 6. AI CLASSIFIER (MobileNetV4 ONNX Engine)
# =============================================================================
class Classifier:
    def __init__(self, model_file, labels_file):
        self.model_path = model_file
        self.labels_path = labels_file
        self.mode = "DEMO"
        self.error_reason = ""
        self.labels = self._load_labels()
        self.session = None
        self.input_name = None
        self.input_shape = [1, 3, 224, 224]
        self.layout = "NCHW"
        self.w, self.h = 224, 224

        self._init_engine()

    def _load_labels(self):
        if os.path.exists(self.labels_path):
            try:
                with open(self.labels_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    clean = []
                    for line in lines:
                        parts = line.split(maxsplit=1)
                        lbl = parts[1] if (len(parts) == 2 and parts[0].isdigit()) else line
                        while "__" in lbl:
                            lbl = lbl.replace("__", "_")
                        clean.append(lbl)
                    if clean:
                        return clean
            except Exception as e:
                print("Labels load error:", e)

        return [
            "Apple_Rust", "Apple_Scab", "Apple_healthy",
            "Mango_Anthracnose", "Mango_Bacterial_Canker", "Mango_Cutting_Weevil",
            "Mango_Die_Back", "Mango_Gall_Midge", "Mango_Healthy",
            "Mango_Powdery_Mildew", "Mango_Sooty_Mould",
            "Potato_Early_blight", "Potato_Late_blight", "Potato_healthy",
            "Tomato_Bacterial_spot", "Tomato_Early_blight", "Tomato_Late_blight",
            "Tomato_Leaf_Mold", "Tomato_Septoria_leaf_spot",
            "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato_Target_Spot",
            "Tomato_Tomato_YellowLeaf_Curl_Virus", "Tomato_Tomato_mosaic_virus", "Tomato_healthy"
        ]

    def _init_engine(self):
        if not os.path.exists(self.model_path):
            self.mode = "DEMO"
            self.error_reason = "Model file not found"
            return

        if np is None:
            self.mode = "DEMO"
            self.error_reason = "numpy not installed"
            return

        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            self.session = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
            inp = self.session.get_inputs()[0]
            self.input_name = inp.name

            shape = []
            for d in inp.shape:
                try:
                    shape.append(int(d))
                except (ValueError, TypeError):
                    shape.append(1)
            self.input_shape = shape

            if len(shape) == 4 and shape[1] in (1, 3):
                self.layout, self.h, self.w = "NCHW", shape[2], shape[3]
            else:
                self.layout, self.h, self.w = "NHWC", shape[1], shape[2]

            self.mode = "ONNX (98.31%)"
            self.error_reason = ""
        except ImportError:
            _auto_install_package("onnxruntime", "onnxruntime")
            try:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 4
                self.session = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
                inp = self.session.get_inputs()[0]
                self.input_name = inp.name
                shape = []
                for d in inp.shape:
                    try:
                        shape.append(int(d))
                    except (ValueError, TypeError):
                        shape.append(1)
                self.input_shape = shape
                if len(shape) == 4 and shape[1] in (1, 3):
                    self.layout, self.h, self.w = "NCHW", shape[2], shape[3]
                else:
                    self.layout, self.h, self.w = "NHWC", shape[1], shape[2]
                self.mode = "ONNX (98.31%)"
                self.error_reason = ""
            except Exception as e_retry:
                self.mode = "DEMO"
                self.error_reason = f"onnxruntime not installed ({e_retry})"
        except Exception as e:
            self.mode = "DEMO"
            self.error_reason = str(e)

    def _prep_tensor(self, rgb_img):
        img = rgb_img.resize((self.w, self.h), RESAMPLE_BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        if self.layout == "NCHW":
            arr = np.transpose(arr, (2, 0, 1))
        return arr

    def _prep_val_crop(self, rgb_img):
        """
        Exact replica of the PyTorch validation transform in train_mobilenetv4.py:
        transforms.Resize(256) (shorter edge = 256, bilinear) -> transforms.CenterCrop(224).
        """
        iw, ih = rgb_img.size
        target_short = int(round(max(self.w, self.h) * (256.0 / 224.0)))
        if iw <= 0 or ih <= 0:
            return rgb_img.resize((self.w, self.h), RESAMPLE_BILINEAR)
        if iw < ih:
            nw, nh = target_short, int(round(ih * (target_short / iw)))
        else:
            nh, nw = target_short, int(round(iw * (target_short / ih)))
        resized = rgb_img.resize((nw, nh), RESAMPLE_BILINEAR)
        x0 = max(0, (nw - self.w) // 2)
        y0 = max(0, (nh - self.h) // 2)
        return resized.crop((x0, y0, x0 + self.w, y0 + self.h))

    @staticmethod
    def _enhance_mobile_screen(pil_img):
        """
        Optimizes webcam captures of leaves displayed on mobile phone screens (OLED/LCD):
        1. Suppresses high-frequency RGB pixel-grid Moire patterns via subtle Gaussian anti-aliasing.
        2. Removes lifted black levels (ambient room reflection/glare on phone glass).
        3. Neutralizes blue OLED/LCD backlight cast while preserving the leaf's true R:G ratio.
        4. Restores contrast and leaf vein edge definition.
        """
        if np is None or pil_img is None:
            return pil_img
        try:
            arr = np.asarray(pil_img.convert("RGB"), dtype=np.float32)
            if cv2 is not None and min(arr.shape[:2]) >= 140:
                arr = cv2.GaussianBlur(arr, (3, 3), 0.65)
            h, w = arr.shape[:2]
            inner = arr[int(h * 0.10):int(h * 0.90), int(w * 0.10):int(w * 0.90)]
            if inner.size == 0:
                inner = arr
            p_low = np.percentile(inner, 2.0, axis=(0, 1))
            rg_floor = max(0.0, min(float(p_low[0]), float(p_low[1])) - 8.0) * 0.85
            b_floor = max(rg_floor, (float(p_low[2]) - 6.0) * 0.90)
            floor_vec = np.array([rg_floor, rg_floor, b_floor], dtype=np.float32)

            shifted = np.maximum(0.0, arr - floor_vec)
            inner_shifted = np.maximum(0.0, inner - floor_vec)

            p_high_ch = np.percentile(inner_shifted, 99.0, axis=(0, 1))
            rg_high = max(float(p_high_ch[0]), float(p_high_ch[1]), 45.0)
            if float(p_high_ch[2]) > rg_high * 1.02:
                shifted[:, :, 2] *= (rg_high / float(p_high_ch[2]))

            scale = min(1.60, 248.0 / rg_high)
            out = np.clip(shifted * scale, 0, 255).astype(np.uint8)
            img = Image.fromarray(out)
            return ImageEnhance.Sharpness(img).enhance(1.20)
        except Exception:
            return pil_img

    def predict(self, pil_image):
        t0 = time.perf_counter()

        # If running in DEMO mode because of missing onnxruntime
        if self.session is None or np is None:
            time.sleep(0.05)
            n = len(self.labels)
            probs = [1.0 / n] * n
            return probs, (time.perf_counter() - t0) * 1000, None

        rgb = pil_image.convert("RGB")
        scr = self._enhance_mobile_screen(rgb)

        # Evaluate strictly on the user-selected cropped leaf area in both Natural RGB and
        # Mobile-Screen-Restored RGB (anti-glare, de-moire, blue-backlight neutralized):
        # 1-2. Complete cropped selection resized to 224x224 (100% of selected area)
        # 3-4. 1:1 aspect-ratio preserving square center fit of the selected area
        # 5-6. Validation crop (Resize(256) -> CenterCrop(224)) of the selected area
        views = [
            rgb,
            scr,
            ImageOps.fit(rgb, (self.w, self.h), RESAMPLE_BILINEAR),
            ImageOps.fit(scr, (self.w, self.h), RESAMPLE_BILINEAR),
            self._prep_val_crop(rgb),
            self._prep_val_crop(scr),
        ]

        batch_tensors = np.stack([self._prep_tensor(v) for v in views], axis=0)

        try:
            batch_out = self.session.run(None, {self.input_name: batch_tensors})[0]
        except Exception:
            batch_out = np.stack(
                [self.session.run(None, {self.input_name: batch_tensors[i:i+1]})[0][0] for i in range(len(views))],
                axis=0
            )

        # Compare Natural ensemble vs Mobile-Screen-Restored ensemble + individual views
        nat_logits = 0.45 * batch_out[0] + 0.35 * batch_out[2] + 0.20 * batch_out[4]
        scr_logits = 0.45 * batch_out[1] + 0.35 * batch_out[3] + 0.20 * batch_out[5]
        candidates = [nat_logits, scr_logits] + [batch_out[i] for i in range(len(batch_out))]

        best_probs = None
        best_raw = None
        best_score = -1e9

        for idx, r_out in enumerate(candidates):
            exps = np.exp(r_out - np.max(r_out))
            p_vec = exps / np.sum(exps)
            top_p = float(np.max(p_vec))
            top_l = float(np.max(r_out))
            ensemble_bonus = 0.04 if idx < 2 else 0.0
            score = top_p + 0.06 * min(8.0, max(0.0, top_l)) + ensemble_bonus
            if score > best_score:
                best_score = score
                best_probs = p_vec.tolist()
                best_raw = r_out

        ms = (time.perf_counter() - t0) * 1000
        return best_probs, ms, best_raw


# =============================================================================
# 7. INTERACTIVE UI COMPONENTS (Rounded Buttons & Tooltips)
# =============================================================================
class RoundedButton(tk.Canvas):
    """
    Anti-aliased pill-shaped rounded button.
    Renders with 3x supersampled Pillow graphics for smooth curves on dark background.
    Supports hover, press, disable states and standard config() updates.
    """
    _cache = {}

    def __init__(self, parent, text, command, bg_color=GREEN_PRIMARY, fg_color=WHITE,
                 hover_bg=None, width=None, height=38, radius=None, font=None,
                 border_color=None, border_width=1, parent_bg=PANEL, state="normal"):
        self.parent = parent
        self.text = text
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.parent_bg = parent_bg
        self.state = state
        self.border_color = border_color
        self.border_width = border_width
        self.hover_bg = hover_bg or self._tint(bg_color, 1.15)
        self.active_bg = self._tint(bg_color, 0.85)

        self.font = font or (FONT, 11, "bold")
        self.height = max(24, int(height))
        self.radius = radius if radius is not None else (self.height // 2)

        if width is None:
            w = self._measure_text_width(text) + 28
        elif width <= 35:
            w = max(int(width * 10 + 20), self._measure_text_width(text) + 24)
        else:
            w = int(width)
        self.width = max(32, w)

        super().__init__(parent, width=self.width, height=self.height, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2" if state != "disabled" else "arrow")

        self.normal_img = self._get_img(self.bg_color)
        self.hover_img = self._get_img(self.hover_bg)
        self.active_img = self._get_img(self.active_bg)
        self.disabled_img = self._get_img(GREY_BTN)

        img = self.disabled_img if self.state == "disabled" else self.normal_img
        self.img_item = self.create_image(self.width // 2, self.height // 2, image=img)
        self.text_item = self.create_text(
            self.width // 2, self.height // 2, text=self.text,
            fill=MUTED if self.state == "disabled" else self.fg_color,
            font=self.font
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _measure_text_width(self, text):
        try:
            if isinstance(self.font, tuple):
                f = tkFont.Font(family=self.font[0], size=self.font[1], weight=self.font[2] if len(self.font) > 2 else "normal")
            else:
                f = tkFont.nametofont(self.font)
            return f.measure(text)
        except Exception:
            return len(text) * 9

    def _tint(self, hex_color, factor):
        try:
            hex_color = hex_color.lstrip("#")
            r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = min(255, max(0, int(r * factor)))
            g = min(255, max(0, int(g * factor)))
            b = min(255, max(0, int(b * factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _get_img(self, fill):
        key = (self.width, self.height, self.radius, fill, self.border_color, self.border_width, self.parent_bg)
        if key in self._cache:
            return self._cache[key]
        if len(self._cache) > 256:
            self._cache.clear()
        scale = 3
        sw, sh, sr = self.width * scale, self.height * scale, self.radius * scale
        im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=fill,
                            outline=self.border_color, width=self.border_width * scale if self.border_color else 0)
        res = im.resize((self.width, self.height), RESAMPLE_LANCZOS)
        photo = ImageTk.PhotoImage(res)
        self._cache[key] = photo
        return photo

    def _on_enter(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.hover_img)

    def _on_leave(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.normal_img)

    def _on_press(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.active_img)

    def _on_release(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.hover_img)
            if self.command:
                self.command()

    def config(self, **kwargs):
        redraw = False
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            self.itemconfig(self.text_item, text=self.text)
        if "fg" in kwargs:
            self.fg_color = kwargs.pop("fg")
            self.itemconfig(self.text_item, fill=self.fg_color)
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
            self.hover_bg = self._tint(self.bg_color, 1.15)
            self.active_bg = self._tint(self.bg_color, 0.85)
            redraw = True
        if "border" in kwargs:
            self.border_color = kwargs.pop("border")
            redraw = True
        if "state" in kwargs:
            self.state = kwargs.pop("state")
            if self.state == "disabled":
                super().config(cursor="arrow")
                self.itemconfig(self.img_item, image=self.disabled_img)
                self.itemconfig(self.text_item, fill=MUTED)
            else:
                super().config(cursor="hand2")
                self.itemconfig(self.img_item, image=self.normal_img)
                self.itemconfig(self.text_item, fill=self.fg_color)
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if redraw:
            self.normal_img = self._get_img(self.bg_color)
            self.hover_img = self._get_img(self.hover_bg)
            self.active_img = self._get_img(self.active_bg)
            self.itemconfig(self.img_item, image=self.normal_img)
            self.itemconfig(self.text_item, fill=self.fg_color)
        if kwargs:
            super().config(**kwargs)

    configure = config

    def cget(self, key):
        if key == "text":
            return self.text
        elif key == "bg":
            return self.bg_color
        elif key == "fg":
            return self.fg_color
        elif key == "state":
            return self.state
        return super().cget(key)


class ToolTip:
    """
    Floating glassmorphic tooltip with accent border for mouse-over (i) badges.
    Supports both mouse-over (<Enter>/<Leave>) and touchscreen tap (<Button-1>).
    """
    def __init__(self, widget, title, text, font_family=FONT, enter_cb=None, leave_cb=None):
        self.widget = widget
        self.title = title
        self.text = text
        self.font_family = font_family
        self.enter_cb = enter_cb
        self.leave_cb = leave_cb
        self.tip_window = None

        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<Button-1>", self.toggle_tip)

    def show_tip(self, event=None):
        if self.enter_cb:
            self.enter_cb(self.title, self.text)

        if self.tip_window or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + 26
            y = self.widget.winfo_rooty() - 12
        except Exception:
            return

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass

        frame = tk.Frame(
            tw, bg=CARD, highlightbackground=GREEN_ACCENT,
            highlightthickness=1, padx=12, pady=10
        )
        frame.pack()

        tk.Label(
            frame, text=f"ⓘ  {self.title}",
            font=(self.font_family, 10, "bold"),
            fg=GREEN_ACCENT, bg=CARD, anchor="w"
        ).pack(fill="x", pady=(0, 4))

        tk.Label(
            frame, text=self.text,
            font=(self.font_family, 9),
            fg=TEXT, bg=CARD, justify="left", wraplength=280
        ).pack(fill="x")

        tw.wm_geometry(f"+{x}+{y}")

    def hide_tip(self, event=None):
        if self.leave_cb:
            self.leave_cb()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def toggle_tip(self, event=None):
        if self.tip_window:
            self.hide_tip()
        else:
            self.show_tip()


# =============================================================================
# 8. APPLICATION USER INTERFACE
# =============================================================================
class AgriLensApp:
    def __init__(self, root):
        self.root = root
        self.running = True
        self.paused = False
        self.latest_frame = None
        self.captured_frame = None
        self.crop_box = None
        self._img_disp_rect = (0, 0, 640, 480)
        self._crop_drag_mode = None
        self._crop_drag_start = (0, 0)
        self._crop_box_start = None

        cfg = load_kiosk_config()
        self.threshold = float(cfg.get("confidence_threshold", CONFIDENCE_THRESHOLD))
        self.ood_margin = float(cfg.get("ood_margin", OOD_MARGIN_THRESHOLD))
        self.ood_logit = float(cfg.get("ood_logit", OOD_LOGIT_THRESHOLD))
        self.sharpness_min = float(cfg.get("sharpness_min", SHARPNESS_MIN_THRESHOLD))

        self.selected_plant = None
        self.lang = "HI" if str(cfg.get("language", "EN")).upper() == "HI" else "EN"
        self.last_file_short_name = ""
        self.input_mode = "LIVE"  # Default: "LIVE" (if camera connected), auto-falls back to "FILE" if no camera
        self.startup_splash_active = True
        self.startup_start_ts = time.monotonic()
        self.bootstrap_done = False
        self.standby_active = False
        self._waking_from_standby = False
        self._wake_guard_until = 0.0
        self._file_dialog_open = False
        self.last_activity_ts = time.monotonic()
        self.splash_logo_img = None
        self.last_probs = None
        self.last_raw_out = None
        self.latency_ms = 0.0

        self.entered_password = ""
        self.camera = Camera(auto_detect=False)
        self.camera.contrast = int(cfg.get("cam_contrast", 100))
        self.camera.brightness = int(cfg.get("cam_brightness", 0))
        self.camera.saturation = int(cfg.get("cam_saturation", 100))
        self.camera.sharpness = int(cfg.get("cam_sharpness", 100))
        self.camera.wb_temp = int(cfg.get("cam_wb_temp", 0))
        self.camera.zoom = int(cfg.get("cam_zoom", 100))
        self.camera.flip_h = bool(cfg.get("cam_flip_h", False))
        self.camera.flip_v = bool(cfg.get("cam_flip_v", False))
        self.camera.auto_exp = bool(cfg.get("cam_auto_exp", True))
        self.camera.auto_wb = bool(cfg.get("cam_auto_wb", True))

        self.classifier = None
        self.plants = ["Apple", "Mango", "Potato", "Tomato"]
        self.crops = []
        self.parsed = []
        self.sliders = {}
        self.slider_badges = {}
        self.cam_sliders = {}
        self.cam_slider_badges = {}

        self._setup_window()
        self._build_top_bar()
        self._build_body()
        self._build_plant_picker()
        self._build_password_screen()
        self._build_admin_panel()
        self._build_camera_panel()
        self._build_screensaver_overlay()

        # Load and display full-screen AGRILENS screensaver on startup (deactivates after 5s or on touch/click)
        self.splash_logo_img = self._load_splash_logo()
        self._refresh_language_ui()
        self._show_fullscreen_screensaver(is_startup=True)
        self._update_stats_bar()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", self._on_escape_key)
        self.root.bind("<space>", self._on_space_key)
        self.root.bind("<Key>", self._on_key_press)
        self.root.bind_all("<ButtonPress>", self._on_global_user_activity, add="+")
        self.root.bind_all("<B1-Motion>", self._on_global_user_activity, add="+")
        self.root.bind_all("<ButtonRelease>", self._on_global_user_activity, add="+")
        self.root.bind_all("<KeyPress>", self._on_global_user_activity, add="+")

        # Non-blocking async bootstrap: window paints immediately in <0.1s
        self.root.after(30, self._start_async_bootstrap)

    def _any_overlay_open(self):
        for attr in ("picker", "pwd_screen", "admin", "cam_panel", "mode_dropdown"):
            w = getattr(self, attr, None)
            if w is not None and w.winfo_ismapped():
                return True
        return False

    def _on_escape_key(self, event=None):
        if self._any_overlay_open():
            self.close_overlays()
        else:
            self.close()

    def _on_space_key(self, event=None):
        if not self._any_overlay_open():
            self.handle_capture_or_retake()

    def _on_key_press(self, event=None):
        if hasattr(self, "pwd_screen") and self.pwd_screen.winfo_ismapped() and event is not None:
            ks = getattr(event, "keysym", "")
            ch = getattr(event, "char", "")
            if ks == "BackSpace":
                self._pwd_backspace()
            elif ks in ("Return", "KP_Enter"):
                self._pwd_submit()
            elif ch and len(ch) == 1 and ch.isalnum():
                self._pwd_key_press(ch.upper())

    def _setup_window(self):
        ensure_rpi_autostart()
        # Lock Tkinter font DPI scaling to standard 96 DPI (1.3333) so small 7" physical
        # screen dimensions in EDID never inflate font sizes on Raspberry Pi / Waveshare.
        try:
            self.root.tk.call("tk", "scaling", 96.0 / 72.0)
        except Exception:
            pass
        self.root.title("")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.update_idletasks()
        self.root.update()

        sw = self.root.winfo_width()
        sh = self.root.winfo_height()
        if sw < 400 or sh < 300:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

        # On Raspberry Pi + Waveshare 7" (1024x600 native, 1920x1080 max EDID),
        # clamp to 1024x600 so early-boot 1920x1080 EDID never enlarges the UI.
        if platform.system() == "Linux" and (sw > 1024 or sh > 600):
            sw, sh = 1024, 600

        self.W = sw if sw > 0 else 1024
        self.H = sh if sh > 0 else 600
        self.root.geometry(f"{self.W}x{self.H}+0+0")
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            if platform.system() == "Windows":
                import ctypes
                self.root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            self.root.after(400, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass
        self.root.after(100, lambda: self.root.attributes("-fullscreen", True))

        self.S = min(self.W / 1024, self.H / 600)
        self.TOP_H = self.px(60)

    def px(self, val):
        return max(1, round(val * self.S))

    def f(self, size, bold=False):
        return (FONT, max(9, round(size * self.S)), "bold" if bold else "normal")

    def _button(self, parent, text, bg, cmd, width=None, height=None, size=12, fg=None, radius=None, border=None, parent_bg=None):
        if fg is None:
            fg = DARK if bg in (WHITE, GREEN_ACCENT, GREEN_GLOW) else WHITE
        if height is None:
            height = self.px(44)
        if parent_bg is None:
            try:
                parent_bg = parent.cget("bg")
            except Exception:
                parent_bg = PANEL

        return RoundedButton(
            parent, text=text, command=cmd,
            bg_color=bg, fg_color=fg,
            width=width, height=height, radius=radius,
            font=self.f(size, True),
            border_color=border,
            parent_bg=parent_bg
        )

    # ---- 1. Top Bar with Brand, Crop Filter, Admin & Gundecha Academy Logo ----
    def _load_splash_logo(self):
        """Loads the AGRILENS full-screen screensaver logo from the dedicated logos/ folder."""
        for candidate in ("agrilens_logo.jpg", "agrilens_logo.png", "agrilens_splash.jpg"):
            logo_path = find_logo_file(candidate)
            if logo_path and os.path.exists(logo_path):
                try:
                    with Image.open(logo_path) as raw_im:
                        return raw_im.convert("RGB")
                except Exception as e:
                    print("Notice: splash logo load error:", e)
        return None

    def _build_screensaver_overlay(self):
        """Builds the full-screen AGRILENS logo screensaver overlay covering the complete screen (self.W x self.H)."""
        self.screensaver_frame = tk.Frame(self.root, bg="#010603", width=self.W, height=self.H)
        self.screensaver_canvas = tk.Canvas(
            self.screensaver_frame, width=self.W, height=self.H,
            bg="#010603", highlightthickness=0, cursor="hand2"
        )
        self.screensaver_canvas.pack(fill="both", expand=True)
        self.screensaver_img_item = self.screensaver_canvas.create_image(
            self.W // 2, self.H // 2, anchor="center"
        )
        self.screensaver_hint_item = self.screensaver_canvas.create_text(
            self.W // 2, self.H - self.px(16), anchor="s",
            fill=GREEN_ACCENT, font=self.f(10, True),
            text="TOUCH OR CLICK ANYWHERE TO CONTINUE"
        )
        self.screensaver_canvas.bind("<ButtonPress-1>", self._on_screensaver_touch)
        self.screensaver_frame.bind("<ButtonPress-1>", self._on_screensaver_touch)

    def _show_fullscreen_screensaver(self, is_startup=True):
        """Displays the AGRILENS logo as a full-screen screensaver over the complete screen (never inside the camera box)."""
        if not hasattr(self, "screensaver_frame"):
            return
        if self.splash_logo_img is not None:
            iw, ih = self.splash_logo_img.size
            scale = min(self.W / max(1, iw), self.H / max(1, ih))
            nw = max(1, int(round(iw * scale)))
            nh = max(1, int(round(ih * scale)))
            resized = self.splash_logo_img.resize((nw, nh), RESAMPLE_LANCZOS)
            full_im = Image.new("RGB", (self.W, self.H), (1, 6, 3))
            full_im.paste(resized, ((self.W - nw) // 2, (self.H - nh) // 2))
            self._screensaver_photo = ImageTk.PhotoImage(full_im)
            self.screensaver_canvas.itemconfig(self.screensaver_img_item, image=self._screensaver_photo)
        else:
            self._screensaver_photo = None
            self.screensaver_canvas.itemconfig(self.screensaver_img_item, image="")

        hint_txt = (
            "TOUCH OR CLICK ANYWHERE TO START"
            if is_startup else
            "SCREENSAVER ACTIVE (CAMERA OFF)  •  TOUCH OR CLICK ANYWHERE TO WAKE"
        )
        self.screensaver_canvas.itemconfig(self.screensaver_hint_item, text=hint_txt)
        self.screensaver_frame.place(x=0, y=0, width=self.W, height=self.H)
        self.screensaver_frame.lift()

    def _hide_fullscreen_screensaver(self):
        """Hides the full-screen screensaver overlay immediately."""
        if hasattr(self, "screensaver_frame") and self.screensaver_frame.winfo_ismapped():
            self.screensaver_frame.place_forget()

    def _on_screensaver_touch(self, event=None):
        """Deactivates the full-screen screensaver immediately on touch or click."""
        self.last_activity_ts = time.monotonic()
        self._wake_guard_until = time.monotonic() + 0.35
        if self.startup_splash_active:
            self._finish_startup_splash()
            return "break"
        if self.standby_active:
            self._wake_from_standby()
            return "break"
        self._hide_fullscreen_screensaver()
        return "break"

    def _on_global_user_activity(self, event=None):
        """Tracks user touch/mouse/keyboard activity and deactivates full-screen screensaver on touch/click/key."""
        self.last_activity_ts = time.monotonic()
        ev_type = str(getattr(event, "type", ""))
        is_press = ev_type in ("4", "ButtonPress", "2", "KeyPress")
        if self.startup_splash_active and is_press:
            self._wake_guard_until = time.monotonic() + 0.35
            self._finish_startup_splash()
            return
        if self.standby_active and not self._waking_from_standby:
            if is_press or event is not None:
                self._wake_from_standby()

    def _enter_inactivity_standby(self):
        """Triggered after 3 minutes of inactivity: activates full-screen logo screensaver and turns off camera."""
        if self.standby_active or self.startup_splash_active:
            return
        self.standby_active = True
        self.paused = False
        self.captured_frame = None
        self.last_probs = None
        self.last_raw_out = None
        self.close_overlays()
        if self.camera:
            self.camera.close()
        self._show_fullscreen_screensaver(is_startup=False)
        self._update_stats_bar()

    def _wake_from_standby(self):
        """Deactivates the full-screen screensaver, turns on the camera, and switches back to Live Mode."""
        if not self.standby_active or self._waking_from_standby:
            self._hide_fullscreen_screensaver()
            return
        self.standby_active = False
        self._waking_from_standby = True
        self._wake_guard_until = time.monotonic() + 0.45
        self.last_activity_ts = time.monotonic()

        # Hide full-screen screensaver immediately on touch/click
        self._hide_fullscreen_screensaver()

        self.canvas.itemconfig(self.live_badge, text="TURNING ON CAMERA...", fill=GREEN_ACCENT)
        self.banner_frame.config(bg=GREEN_PRIMARY)
        self.banner.config(text="TURNING ON CAMERA — SWITCHING TO LIVE MODE...", bg=GREEN_PRIMARY, fg=WHITE)
        self.quality_lbl.config(text="Turning on camera and resuming Live Mode...", fg=GREEN_ACCENT)
        self.root.update_idletasks()

        q = queue.Queue()
        def wake_worker():
            ok, msg = self.camera.detect_webcam()
            q.put((ok, msg))

        threading.Thread(target=wake_worker, daemon=True).start()

        def poll_wake():
            try:
                ok, _ = q.get_nowait()
                self._waking_from_standby = False
                self.last_activity_ts = time.monotonic()
                if ok and self._has_camera():
                    self.set_input_mode("LIVE", browse_on_file=False)
                else:
                    self.set_input_mode("FILE", browse_on_file=False)
                return
            except queue.Empty:
                pass
            if self.running:
                self.root.after(30, poll_wake)

        poll_wake()

    def _build_school_logo(self, parent):
        px = self.px
        logo_path = find_logo_file("gundecha_logo.png")

        if os.path.exists(logo_path):
            try:
                raw_logo = Image.open(logo_path)
                lh = px(44)
                aspect = raw_logo.width / max(1, raw_logo.height)
                lw = max(1, int(lh * aspect))
                resized = raw_logo.resize((lw, lh), RESAMPLE)

                pad_x, pad_y = px(5), px(3)
                bw, bh = lw + 2 * pad_x, lh + 2 * pad_y
                scale = 2
                badge_im = Image.new("RGBA", (bw * scale, bh * scale), (0, 0, 0, 0))
                d = ImageDraw.Draw(badge_im)
                d.rounded_rectangle(
                    [0, 0, bw * scale - 1, bh * scale - 1],
                    radius=px(12) * scale,
                    fill=(255, 255, 255, 248),
                    outline=(210, 220, 215, 255),
                    width=scale
                )
                badge_im = badge_im.resize((bw, bh), RESAMPLE)
                badge_im.paste(resized, (pad_x, pad_y), resized)

                self._school_logo_photo = ImageTk.PhotoImage(badge_im)
                logo_lbl = tk.Label(
                    parent, image=self._school_logo_photo, bg=PANEL, cursor="hand2", bd=0
                )
                logo_lbl.pack(side="right", padx=(px(6), px(12)), pady=px(5))
                logo_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://www.gundechaedu.org/"))
                ToolTip(logo_lbl, "Gundecha Education Academy", "Official Partner Institution\nClick to open official portal: gundechaedu.org", font_family=FONT)
                return
            except Exception as e:
                print("Notice: logo load error:", e)

        school_box = tk.Frame(parent, bg=WHITE, padx=px(8), pady=px(4))
        school_box.pack(side="right", padx=(px(6), px(12)), pady=px(10))
        tk.Label(school_box, text="GEA", font=self.f(12, True), fg=DARK, bg=WHITE).pack()

    def _build_top_bar(self):
        px = self.px
        top = tk.Frame(
            self.root, bg=PANEL, height=self.TOP_H,
            highlightbackground=BORDER, highlightthickness=max(1, px(1))
        )
        top.pack(side="top", fill="x")
        top.pack_propagate(False)

        # 1. Left: Brand Header Title (AGRILENS + Subtitle)
        title_box = tk.Frame(top, bg=PANEL)
        title_box.pack(side="left", padx=(px(12), px(6)))
        lbl_brand = tk.Label(title_box, text="AGRILENS", font=self.f(17, True), fg=WHITE, bg=PANEL, cursor="hand2")
        lbl_brand.pack(anchor="w")
        ToolTip(lbl_brand, "AGRILENS Edge Vision Kiosk", f"Version: v{APP_VERSION}\nBuild: {BUILD_TIMESTAMP}\nModel: MobileNetV4 ONNX (24 Classes)", font_family=FONT)
        self.brand_sub_lbl = tk.Label(
            title_box, text="AI Agricultural Health Diagnostics",
            font=self.f(9, True), fg=GREEN_ACCENT, bg=PANEL
        )
        self.brand_sub_lbl.pack(anchor="w")

        # 2. Far Right: Official Gundecha Education Academy Logo
        self._build_school_logo(top)

        # 3. Unified Top Selection & Control Bar (All 4 buttons grouped & aligned together)
        self.top_btn_bar = tk.Frame(top, bg=PANEL)
        self.top_btn_bar.pack(side="right", padx=(px(4), px(6)), pady=px(7))

        top_btn_h = px(44)
        top_btn_r = px(14)

        # Button A: Crop Filter Button (Auto - Beta)
        self.plant_btn = self._button(
            self.top_btn_bar, "🌱 CROP: AUTO (ALL)", CARD, self.open_plant_picker,
            width=px(192), height=top_btn_h, size=11, radius=top_btn_r,
            fg=WHITE, border=GREEN_ACCENT, parent_bg=PANEL
        )
        self.plant_btn.pack(side="left", padx=px(4))

        # Button B: Mode Selector Dropdown Button (Live Mode vs File Mode)
        self.mode_btn = self._button(
            self.top_btn_bar, "📷 MODE: LIVE ▾", CARD, self.toggle_mode_dropdown,
            width=px(176), height=top_btn_h, size=11, radius=top_btn_r,
            fg=WHITE, border=GREEN_ACCENT, parent_bg=PANEL
        )
        self.mode_btn.pack(side="left", padx=px(4))

        # Button C: Language Toggle Button (Hindi / English — Main Screen Only)
        self.lang_btn = self._button(
            self.top_btn_bar, "🌐 हिंदी / EN", CARD, self.toggle_language,
            width=px(142), height=top_btn_h, size=11, radius=top_btn_r,
            fg=WHITE, border=GREEN_ACCENT, parent_bg=PANEL
        )
        self.lang_btn.pack(side="left", padx=px(4))

        # Button D: Admin Console Button
        self.admin_btn = self._button(
            self.top_btn_bar, "⚙ ADMIN", CARD, self.open_admin_panel,
            width=px(114), height=top_btn_h, size=11, radius=top_btn_r,
            fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.admin_btn.pack(side="left", padx=px(4))

        self._build_mode_dropdown()

    def toggle_language(self):
        """Toggles Main Screen language between English (EN) and Hindi (HI)."""
        self._hide_mode_dropdown()
        self.lang = "HI" if self.lang == "EN" else "EN"
        self._save_current_settings()
        self._refresh_language_ui()

    def _refresh_language_ui(self):
        """Updates all Main Screen static and dynamic UI text in the selected language (Hindi / English)."""
        is_hi = (self.lang == "HI")
        if hasattr(self, "lang_btn"):
            if is_hi:
                self.lang_btn.config(text="🌐 भाषा: हिंदी", bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE)
            else:
                self.lang_btn.config(text="🌐 हिंदी / EN", bg=CARD, border=GREEN_ACCENT, fg=WHITE)

        if hasattr(self, "brand_sub_lbl"):
            self.brand_sub_lbl.config(
                text="एआई कृषि स्वास्थ्य निदान" if is_hi else "AI Agricultural Health Diagnostics"
            )

        if hasattr(self, "plant_btn"):
            if self.selected_plant is None:
                self.plant_btn.config(
                    text=("🌱 फसल: ऑटो (सभी)" if is_hi else "🌱 CROP: AUTO (ALL)"),
                    bg=CARD, border=GREEN_ACCENT, fg=WHITE
                )
            else:
                p_txt = translate_crop_hi(self.selected_plant) if is_hi else self.selected_plant.upper()
                self.plant_btn.config(
                    text=(f"🌱 फसल: {p_txt}" if is_hi else f"🌱 CROP: {p_txt}"),
                    bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE
                )

        if hasattr(self, "rec_hdr_lbl"):
            self.rec_hdr_lbl.config(
                text="किसानों के लिए सुझाए गए उपाय" if is_hi else "RECOMMENDED FARMER ACTIONS"
            )

        if hasattr(self, "disclaimer_lbl"):
            self.disclaimer_lbl.config(text=DISCLAIMER_HI if is_hi else DISCLAIMER)

        if hasattr(self, "crop_info_badge"):
            self.canvas.itemconfig(
                self.crop_info_badge,
                text="पत्ती क्रॉप करने हेतु हैंडल खींचें  •  डबल-टैप: पूर्ण" if is_hi else "DRAG HANDLES TO CROP LEAF  •  DOUBLE-TAP: FULL"
            )

        if hasattr(self, "picker_title_lbl"):
            self.picker_title_lbl.config(text="जांच के लिए फसल चुनें" if is_hi else "SELECT CROP TO DIAGNOSE")
        if hasattr(self, "picker_sub_lbl"):
            self.picker_sub_lbl.config(
                text="ऑटो-डिटेक्शन मोड सभी समर्थित फसलों की स्वचालित रूप से पहचान करता है"
                if is_hi else "Auto-detection mode automatically identifies all supported plant species"
            )
        if hasattr(self, "picker_back_btn"):
            self.picker_back_btn.config(text="← स्कैनर पर वापस जाएं" if is_hi else "← REVERT TO SCANNER")

        self._refresh_mode_ui()

        # Re-render active main-screen state in the selected language
        if self.paused and self.captured_frame is not None:
            is_live = self._is_live_mode()
            cropped = self._get_cropped_leaf_image()
            px0, py0, px1, py1 = self._get_crop_pixel_bounds()
            pw, ph = max(1, px1 - px0), max(1, py1 - py0)
            score, rating, q_msg, q_color = LeafQualityAI.assess(cropped, self.sharpness_min, lang=self.lang)
            if self.last_probs is not None:
                self.quality_lbl.config(
                    text=(f"चयनित भाग ({pw}×{ph} px) | {q_msg}" if is_hi else f"Diagnosed Crop ({pw}×{ph} px) | {q_msg}"),
                    fg=q_color
                )
                if is_live:
                    self.capture_btn.config(text="↺  पुनः फोटो लें" if is_hi else "↺  RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)
                    self.canvas.itemconfig(
                        self.live_badge,
                        text="फोटो ली गई — क्रॉप करने हेतु हैंडल खींचें" if is_hi else "CAPTURED — DRAG HANDLES TO CROP",
                        fill=GREEN_ACCENT
                    )
                else:
                    self.capture_btn.config(text="📂  फाइल से चुनें" if is_hi else "📂  PICK FROM FILE", bg=AMBER_WARN, fg=WHITE)
                    fn = self.last_file_short_name or "Sample"
                    self.canvas.itemconfig(
                        self.live_badge,
                        text=(f"फाइल: {fn} (क्रॉप समायोजित करें)" if is_hi else f"FILE: {fn} (ADJUST CROP)"),
                        fill=GREEN_ACCENT
                    )
                self._render_diagnosis(self.last_probs, self.last_raw_out)
            else:
                if is_live:
                    self.quality_lbl.config(
                        text=(f"पत्ती का भाग चुनने के लिए हैंडल खींचें | {q_msg}" if is_hi else f"Drag handles to select leaf area | {q_msg}"),
                        fg=q_color
                    )
                    self.capture_btn.config(text="↺  पुनः फोटो लें" if is_hi else "↺  RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)
                    self.canvas.itemconfig(
                        self.live_badge,
                        text="फोटो ली गई — क्रॉप करने हेतु हैंडल खींचें" if is_hi else "CAPTURED — DRAG HANDLES TO CROP",
                        fill=GREEN_ACCENT
                    )
                else:
                    fn = self.last_file_short_name or "Sample"
                    self.quality_lbl.config(
                        text=(f"पत्ती क्रॉप करने के लिए हैंडल खींचें ({fn}) | {q_msg}" if is_hi else f"Drag handles to crop leaf ({fn}) | {q_msg}"),
                        fg=q_color
                    )
                    self.capture_btn.config(text="📂  फाइल से चुनें" if is_hi else "📂  PICK FROM FILE", bg=AMBER_WARN, fg=WHITE)
                    self.canvas.itemconfig(
                        self.live_badge,
                        text=(f"फाइल: {fn} (क्रॉप समायोजित करें)" if is_hi else f"FILE: {fn} (ADJUST CROP)"),
                        fill=GREEN_ACCENT
                    )
                self.banner_frame.config(bg=GREEN_PRIMARY)
                self.banner.config(
                    text=("क्रॉप हैंडल समायोजित करें -> अभी जांचें दबाएं" if is_hi else "ADJUST CROP HANDLES -> TAP DIAGNOSE NOW"),
                    bg=GREEN_PRIMARY, fg=WHITE
                )
                self.disease_lbl.config(
                    text=(
                        "सटीक पत्ती क्षेत्र चुनने के लिए हरे हैंडल खींचें, फिर 'अभी जांचें' दबाएं।"
                        if is_hi else
                        "Drag green handles to select exact leaf area, then tap DIAGNOSE NOW."
                    )
                )
                self.diagnose_btn.config(text="🔍  अभी जांचें" if is_hi else "🔍  DIAGNOSE NOW", bg=GREEN_PRIMARY, fg=WHITE)
        else:
            self._reset_panel()

    def _build_mode_dropdown(self):
        px = self.px
        self.mode_dropdown = tk.Frame(
            self.root, bg=PANEL,
            highlightbackground=GREEN_ACCENT, highlightthickness=max(1, px(2)),
            padx=px(12), pady=px(12)
        )
        self.mode_dd_hdr = tk.Label(
            self.mode_dropdown, text="SELECT INPUT MODE",
            font=self.f(10, True), fg=MUTED, bg=PANEL, anchor="w"
        )
        self.mode_dd_hdr.pack(fill="x", pady=(0, px(8)))

        self.mode_opt_live = self._button(
            self.mode_dropdown, "●  LIVE MODE (Camera)", GREEN_PRIMARY,
            lambda: self._on_mode_dropdown_select("LIVE"),
            width=px(250), height=px(50), size=11, fg=WHITE, radius=px(14),
            border=GREEN_ACCENT, parent_bg=PANEL
        )
        self.mode_opt_live.pack(pady=(0, px(8)))

        self.mode_opt_file = self._button(
            self.mode_dropdown, "○  FILE MODE (Sample Files)", CARD,
            lambda: self._on_mode_dropdown_select("FILE"),
            width=px(250), height=px(50), size=11, fg=WHITE, radius=px(14),
            border=BORDER, parent_bg=PANEL
        )
        self.mode_opt_file.pack()

    def _hide_mode_dropdown(self):
        if hasattr(self, "mode_dropdown") and self.mode_dropdown.winfo_ismapped():
            self.mode_dropdown.place_forget()

    def _refresh_mode_ui(self):
        is_live = (self.input_mode == "LIVE")
        is_hi = (getattr(self, "lang", "EN") == "HI")
        if hasattr(self, "mode_dd_hdr"):
            self.mode_dd_hdr.config(text="इनपुट मोड चुनें" if is_hi else "SELECT INPUT MODE")
        if hasattr(self, "mode_btn"):
            if is_live:
                self.mode_btn.config(
                    text=("📷 मोड: लाइव ▾" if is_hi else "📷 MODE: LIVE ▾"),
                    bg=CARD, border=GREEN_ACCENT, fg=WHITE
                )
            else:
                self.mode_btn.config(
                    text=("📂 मोड: फाइल ▾" if is_hi else "📂 MODE: FILE ▾"),
                    bg=CARD, border=AMBER_WARN, fg=AMBER_WARN
                )
        if hasattr(self, "mode_opt_live") and hasattr(self, "mode_opt_file"):
            live_lbl_on = "●  लाइव मोड (कैमरा)" if is_hi else "●  LIVE MODE (Camera)"
            live_lbl_off = "○  लाइव मोड (कैमरा)" if is_hi else "○  LIVE MODE (Camera)"
            file_lbl_on = "●  फाइल मोड (सैंपल फाइलें)" if is_hi else "●  FILE MODE (Sample Files)"
            file_lbl_off = "○  फाइल मोड (सैंपल फाइलें)" if is_hi else "○  FILE MODE (Sample Files)"
            if is_live:
                self.mode_opt_live.config(
                    text=live_lbl_on, bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE
                )
                self.mode_opt_file.config(
                    text=file_lbl_off, bg=CARD, border=BORDER, fg=WHITE
                )
            else:
                self.mode_opt_live.config(
                    text=live_lbl_off, bg=CARD, border=BORDER, fg=WHITE
                )
                self.mode_opt_file.config(
                    text=file_lbl_on, bg=AMBER_WARN, border=AMBER_WARN, fg=WHITE
                )

    def toggle_mode_dropdown(self):
        if hasattr(self, "mode_dropdown") and self.mode_dropdown.winfo_ismapped():
            self._hide_mode_dropdown()
            return
        self._refresh_mode_ui()
        self.root.update_idletasks()
        bx = self.mode_btn.winfo_rootx() - self.root.winfo_rootx()
        max_x = max(self.px(10), self.W - self.px(280))
        bx = max(self.px(10), min(bx, max_x))
        by = self.TOP_H + self.px(2)
        self.mode_dropdown.place(x=bx, y=by)
        self.mode_dropdown.lift()

    def _on_mode_dropdown_select(self, mode):
        self._hide_mode_dropdown()
        self.set_input_mode(mode, browse_on_file=(mode == "FILE"))

    def set_input_mode(self, mode, browse_on_file=False):
        mode = "LIVE" if str(mode).upper() == "LIVE" else "FILE"
        is_hi = (getattr(self, "lang", "EN") == "HI")
        if mode == "LIVE" and not self._has_camera():
            # Camera is not connected — automatically default/fallback to File Mode
            self.input_mode = "FILE"
            self.paused = False
            self.captured_frame = None
            self.last_probs = None
            self.last_raw_out = None
            self._hide_crop_selection()
            self._refresh_mode_ui()
            self._reset_panel()
            self._update_stats_bar()
            self.quality_lbl.config(
                text=(
                    "कोई कैमरा जुड़ा नहीं है — स्वचालित रूप से फाइल मोड चुना गया (diagnosis_samples/)"
                    if is_hi else
                    "No camera connected — Automatically defaulted to File Mode (diagnosis_samples/)"
                ),
                fg=AMBER_WARN
            )
            return

        self.input_mode = mode
        self.paused = False
        self.captured_frame = None
        self.last_probs = None
        self.last_raw_out = None
        self._hide_crop_selection()
        if mode == "FILE":
            self._photo = None
            self.canvas.itemconfig(self.img_item, image="")
        self._refresh_mode_ui()
        self._reset_panel()
        self._update_stats_bar()
        if mode == "FILE" and browse_on_file:
            self.root.after(40, self.pick_image_from_file)

    # ---- 2. Split Screen Body ----
    def _build_body(self):
        px = self.px
        pad = px(6)
        body_h = self.H - self.TOP_H

        body = tk.Frame(self.root, bg=BG, width=self.W, height=body_h)
        body.pack(side="top", fill="both", expand=True)
        body.pack_propagate(False)

        # Allocate 56.5% width to the Camera Panel so the full 4:3 (640x480) FoV displays large & uncropped on 1024x600
        left_w = int(self.W * 0.565)
        right_w = self.W - left_w

        # LEFT SIDE - Full-FoV Camera Window + Quality AI Bar + Action Buttons
        left = tk.Frame(body, bg=BG, width=left_w, height=body_h)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        self.CAM_W = left_w - 2 * pad - 4
        half_btn_w = self.CAM_W // 2 - px(5)
        btn_h = px(52)

        # 1. BOTTOM: SEPARATE ACTION BUTTONS BAR ([CAPTURE LEAF / PICK FROM FILE] and [DIAGNOSE LEAF])
        btn_box = tk.Frame(left, bg=BG)
        btn_box.pack(side="bottom", fill="x", padx=pad + 2, pady=(0, pad))

        # Button 1: CAPTURE (swaps to RETAKE when frozen, or PICK FROM FILE when no camera)
        self.capture_btn = self._button(
            btn_box, "📸  CAPTURE LEAF", GREEN_PRIMARY, self.handle_capture_or_retake,
            width=half_btn_w, height=btn_h, size=13, fg=WHITE, radius=px(18), parent_bg=BG
        )
        self.capture_btn.pack(side="left", padx=(0, px(4)))

        # Button 2: DIAGNOSE (Runs AI Inference)
        self.diagnose_btn = self._button(
            btn_box, "🔍  DIAGNOSE LEAF", CARD, self.handle_diagnose,
            width=half_btn_w, height=btn_h, size=13, fg=WHITE, border=GREEN_ACCENT, radius=px(18), parent_bg=BG
        )
        self.diagnose_btn.pack(side="right", padx=(px(4), 0))

        # 2. DIRECTLY ABOVE BUTTONS: IMAGE QUALITY AI STATUS BAR
        quality_frame = tk.Frame(
            left, bg=PANEL, padx=px(8), pady=px(5),
            highlightbackground=BORDER, highlightthickness=max(1, px(1))
        )
        quality_frame.pack(side="bottom", fill="x", padx=pad + 2, pady=(0, px(5)))

        self.quality_lbl = tk.Label(
            quality_frame, text="Leaf Quality AI: Align leaf inside box",
            font=self.f(10, True), fg=MUTED, bg=PANEL, anchor="center",
            wraplength=self.CAM_W - px(14)
        )
        self.quality_lbl.pack(fill="x")

        # 3. LARGE 4:3 FULL-FOV CAMERA OUTPUT DISPLAY (Matches 640x480 webcam aspect ratio so 100% FoV is visible)
        avail_cam_h = max(px(240), body_h - btn_h - px(54))
        fov_4_3_h = int(round(self.CAM_W * 3 / 4))
        self.CAM_H = min(avail_cam_h, fov_4_3_h)

        self.cam_border = tk.Frame(left, bg=CARD, padx=2, pady=2)
        self.cam_border.pack(side="top", pady=(pad, px(3)), expand=True)

        # Clean Camera Canvas with interactive crop selection handles
        self.canvas = tk.Canvas(self.cam_border, width=self.CAM_W, height=self.CAM_H,
                                bg="#050a07", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)

        cw, ch = self.CAM_W, self.CAM_H
        self._img_disp_rect = (0, 0, cw, ch)
        self.img_item = self.canvas.create_image(cw // 2, ch // 2, anchor="center")

        # Leaf Alignment Targeting Box - Covers complete Full-FoV image area in live mode
        margin = px(3)
        self.guide = self.canvas.create_rectangle(
            margin, margin, cw - margin, ch - margin,
            outline=GREEN_ACCENT, width=px(2), dash=(8, 5)
        )

        # Interactive Manual Crop Selection Overlay (visible when image is captured or loaded)
        self.crop_scrim_top = self.canvas.create_rectangle(
            0, 0, 0, 0, fill="#020503", stipple="gray50", width=0, state="hidden", tags=("crop_ui", "crop_scrim")
        )
        self.crop_scrim_bottom = self.canvas.create_rectangle(
            0, 0, 0, 0, fill="#020503", stipple="gray50", width=0, state="hidden", tags=("crop_ui", "crop_scrim")
        )
        self.crop_scrim_left = self.canvas.create_rectangle(
            0, 0, 0, 0, fill="#020503", stipple="gray50", width=0, state="hidden", tags=("crop_ui", "crop_scrim")
        )
        self.crop_scrim_right = self.canvas.create_rectangle(
            0, 0, 0, 0, fill="#020503", stipple="gray50", width=0, state="hidden", tags=("crop_ui", "crop_scrim")
        )

        self.crop_grid_lines = [
            self.canvas.create_line(0, 0, 0, 0, fill=GREEN_GLOW, dash=(4, 4), width=1, state="hidden", tags=("crop_ui", "crop_grid"))
            for _ in range(4)
        ]

        self.crop_rect = self.canvas.create_rectangle(
            0, 0, 0, 0, outline=GREEN_ACCENT, width=px(2), state="hidden", tags=("crop_ui",)
        )

        self.crop_handles = {}
        for h_key in ("nw", "n", "ne", "e", "se", "s", "sw", "w"):
            self.crop_handles[h_key] = self.canvas.create_rectangle(
                0, 0, 0, 0, fill=GREEN_ACCENT, outline=WHITE, width=max(1, px(2)),
                state="hidden", tags=("crop_ui", f"handle_{h_key}")
            )

        self.crop_info_badge = self.canvas.create_text(
            cw - px(10), ch - px(8), anchor="se", fill=WHITE, font=self.f(9, True),
            text="DRAG HANDLES TO CROP LEAF  •  DOUBLE-TAP: FULL", state="hidden", tags=("crop_ui",)
        )

        # Live webcam / File Mode indicator overlay (left-aligned so longer labels never clip)
        self.live_badge = self.canvas.create_text(
            px(10), px(8), anchor="nw", fill=GREEN_ACCENT, font=self.f(10, True),
            text="LIVE WEBCAM"
        )

        self.msg_txt = self.canvas.create_text(
            cw // 2, ch // 2, fill=MUTED, font=self.f(12, True),
            justify="center", text="Connecting to webcam..."
        )

        # RIGHT SIDE - Farmer Diagnosis & Recommendations (Arranged cleanly for 7" 1024x600 screen)
        right = tk.Frame(
            body, bg=PANEL, width=right_w - pad, height=body_h - 2 * pad,
            highlightbackground=BORDER, highlightthickness=max(1, px(1))
        )
        right.pack(side="left", fill="both", expand=True, padx=(0, pad), pady=pad)
        right.pack_propagate(False)
        rp = px(12)
        wrap = right_w - pad - 2 * rp - px(8)

        self.banner_frame = tk.Frame(right, bg=GREY_BTN, padx=px(10), pady=px(6))
        self.banner_frame.pack(fill="x")

        self.banner = tk.Label(
            self.banner_frame, text="READY — AIM LEAF AT CAMERA", font=self.f(13, True),
            bg=GREY_BTN, fg=WHITE, pady=px(2), wraplength=wrap
        )
        self.banner.pack(fill="x")

        info = tk.Frame(right, bg=PANEL)
        info.pack(fill="x", padx=rp, pady=(px(7), 0))

        self.plant_lbl = tk.Label(info, text="Mode: Auto-Detect (Beta Production)", font=self.f(11, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w")
        self.plant_lbl.pack(fill="x")

        self.disease_lbl = tk.Label(
            info, text="Aim leaf inside box -> Tap CAPTURE -> Tap DIAGNOSE",
            font=self.f(13, True), fg=WHITE, bg=PANEL, anchor="w",
            justify="left", wraplength=wrap
        )
        self.disease_lbl.pack(fill="x", pady=(px(2), 0))

        # Confidence Bar
        self.BAR_W, self.BAR_H = wrap, px(22)
        self.bar = tk.Canvas(info, width=self.BAR_W, height=self.BAR_H, bg=CARD, highlightthickness=0)
        self.bar.pack(anchor="w", pady=(px(6), 0))

        tk.Frame(right, bg=BORDER, height=max(1, px(1))).pack(fill="x", padx=rp, pady=(px(8), px(5)))

        self.rec_hdr_lbl = tk.Label(
            right, text="RECOMMENDED FARMER ACTIONS", font=self.f(11, True),
            fg=GREEN_ACCENT, bg=PANEL, anchor="w"
        )
        self.rec_hdr_lbl.pack(fill="x", padx=rp, pady=(0, px(5)))

        # Bottom Hardware / Latency Strip
        self.stats_lbl = tk.Label(
            right, text=f"AGRILENS v{APP_VERSION}", font=self.f(8, True), fg=MUTED, bg=PANEL,
            anchor="w", justify="left", wraplength=wrap
        )
        self.stats_lbl.pack(side="bottom", fill="x", padx=rp, pady=(0, px(4)))

        self.disclaimer_lbl = tk.Label(
            right, text=DISCLAIMER, font=self.f(8), fg=MUTED, bg=PANEL,
            anchor="w", justify="left", wraplength=wrap
        )
        self.disclaimer_lbl.pack(side="bottom", fill="x", padx=rp, pady=(0, px(2)))

        # Numbered recommendation rows
        steps_box = tk.Frame(right, bg=PANEL)
        steps_box.pack(fill="both", expand=True, padx=rp)

        self.step_rows = []
        for i in range(4):
            row = tk.Frame(steps_box, bg=CARD, padx=px(6), pady=px(4), highlightbackground=BORDER, highlightthickness=1)
            num = tk.Label(
                row, text=str(i + 1), font=self.f(10, True),
                bg=GREEN_PRIMARY, fg=WHITE, width=2, pady=px(1)
            )
            num.pack(side="left", anchor="n", padx=(0, px(8)), pady=(px(1), 0))
            txt = tk.Label(
                row, text="", font=self.f(10), fg=WHITE, bg=CARD,
                anchor="w", justify="left", wraplength=wrap - px(46)
            )
            txt.pack(side="left", fill="x", expand=True)
            self.step_rows.append((row, num, txt))

        self._draw_bar(0, GREY_BTN, "")

    # ---- 3. Plant Picker Dialog ----
    def _build_plant_picker(self):
        px = self.px
        self.picker = tk.Frame(self.root, bg=BG)
        self.picker_title_lbl = tk.Label(self.picker, text="SELECT CROP TO DIAGNOSE", font=self.f(22, True), fg=WHITE, bg=BG)
        self.picker_title_lbl.pack(pady=(px(26), px(4)))
        self.picker_sub_lbl = tk.Label(
            self.picker, text="Auto-detection mode automatically identifies all supported plant species",
            font=self.f(11), fg=MUTED, bg=BG
        )
        self.picker_sub_lbl.pack()

        self.picker_grid = tk.Frame(self.picker, bg=BG)
        self.picker_grid.pack(expand=True)

        self.picker_back_btn = self._button(
            self.picker, "← REVERT TO SCANNER", GREY_BTN, self.close_overlays,
            width=px(260), height=px(56), size=12, radius=px(18), fg=WHITE, border=BORDER, parent_bg=BG
        )
        self.picker_back_btn.pack(pady=(0, px(24)))

    def _fill_plant_picker(self):
        for w in self.picker_grid.winfo_children():
            w.destroy()
        is_hi = (getattr(self, "lang", "EN") == "HI")
        if is_hi:
            options = [("🌱 सभी फसलें (ऑटो - बीटा)", None)] + [(f"🌿 {translate_crop_hi(p)} ({p.upper()})", p) for p in self.plants]
        else:
            options = [("🌱 ALL PLANTS (AUTO - BETA)", None)] + [(f"🌿 {p.upper()}", p) for p in self.plants]
        cols = 3 if len(options) > 4 else 2
        for i, (text, value) in enumerate(options):
            color = GREEN_PRIMARY if value == self.selected_plant else CARD
            border = GREEN_ACCENT if value == self.selected_plant else BORDER
            b = self._button(
                self.picker_grid, text, color,
                lambda v=value: self.select_plant(v),
                width=self.px(250), height=self.px(66), size=12, fg=WHITE,
                border=border, radius=self.px(18), parent_bg=BG
            )
            b.grid(row=i // cols, column=i % cols, padx=self.px(12), pady=self.px(12))

    def open_plant_picker(self):
        self._hide_mode_dropdown()
        self._fill_plant_picker()
        self.picker.place(x=0, y=0, relwidth=1, relheight=1)
        self.picker.lift()

    def select_plant(self, plant):
        self.selected_plant = plant
        is_hi = (getattr(self, "lang", "EN") == "HI")
        if plant is None:
            self.plant_btn.config(
                text=("🌱 फसल: ऑटो (सभी)" if is_hi else "🌱 CROP: AUTO (ALL)"),
                bg=CARD, border=GREEN_ACCENT, fg=WHITE
            )
        else:
            p_txt = translate_crop_hi(plant) if is_hi else plant.upper()
            self.plant_btn.config(
                text=(f"🌱 फसल: {p_txt}" if is_hi else f"🌱 CROP: {p_txt}"),
                bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE
            )

        if self.paused and self.last_probs:
            self._render_diagnosis(self.last_probs, self.last_raw_out)
        elif not self.paused:
            self._reset_panel()
        self.close_overlays()

    # ---- 4. Security Lock & Touch Keyboard ----
    def _build_password_screen(self):
        px = self.px
        self.pwd_screen = tk.Frame(self.root, bg=BG)

        head = tk.Frame(self.pwd_screen, bg=PANEL, height=self.TOP_H)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(head, text="ADMIN SECURITY LOCK", font=self.f(16, True), fg=WHITE, bg=PANEL).pack(side="left", padx=px(16))
        self._button(head, "REVERT", GREY_BTN, self.close_overlays, width=px(96), height=px(38), size=10, radius=px(10), fg=WHITE, parent_bg=PANEL).pack(side="right", padx=px(10), pady=px(6))

        # Centered container so the keyboard & display box have clean, un-stretched proportions
        center_wrap = tk.Frame(self.pwd_screen, bg=BG)
        center_wrap.pack(expand=True)

        disp_box = tk.Frame(center_wrap, bg=PANEL, padx=px(18), pady=px(10), highlightbackground=BORDER, highlightthickness=1)
        disp_box.pack(pady=(px(6), px(12)))

        self.pwd_display_lbl = tk.Label(
            disp_box, text="", font=(FONT, max(16, round(22 * self.S)), "bold"),
            fg=WHITE, bg=CARD, width=14, pady=px(6), relief="flat", bd=0
        )
        self.pwd_display_lbl.pack(pady=(0, px(6)))

        self.pwd_status_lbl = tk.Label(
            disp_box, text="ENTER SYSTEM PASSWORD", font=self.f(10, True), fg=MUTED, bg=PANEL
        )
        self.pwd_status_lbl.pack()

        # Large Square-Proportioned Touch Keyboard (Un-stretched, Easy Finger Tap)
        kb_frame = tk.Frame(center_wrap, bg=BG)
        kb_frame.pack(pady=(0, px(6)))

        rows = [
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
            ["CLEAR", "Z", "X", "C", "V", "B", "N", "M", "BACKSPACE"],
            ["ENTER"]
        ]

        key_w = px(72)
        key_h = px(66)
        action_w = px(108)

        for row in rows:
            r_frame = tk.Frame(kb_frame, bg=BG)
            r_frame.pack(pady=px(5))
            for key in row:
                if key == "ENTER":
                    btn = self._button(
                        r_frame, "✓  ENTER PASSWORD", GREEN_PRIMARY, self._pwd_submit,
                        width=px(240), height=px(62), size=14, fg=WHITE, radius=px(16), parent_bg=BG
                    )
                elif key == "CLEAR":
                    btn = self._button(
                        r_frame, "CLEAR", RED_ALERT, self._pwd_clear,
                        width=action_w, height=key_h, size=12, fg=WHITE, radius=px(14), parent_bg=BG
                    )
                elif key == "BACKSPACE":
                    btn = self._button(
                        r_frame, "⌫ BACK", GREY_BTN, self._pwd_backspace,
                        width=action_w, height=key_h, size=12, fg=WHITE, radius=px(14), parent_bg=BG
                    )
                else:
                    btn = self._button(
                        r_frame, key, CARD, lambda k=key: self._pwd_key_press(k),
                        width=key_w, height=key_h, size=16, fg=WHITE, radius=px(14), border=BORDER, parent_bg=BG
                    )
                btn.pack(side="left", padx=px(4))

    def open_password_screen(self):
        # Direct entry to Admin Panel (password disabled)
        self.open_admin_panel()

    def _pwd_key_press(self, key):
        if len(self.entered_password) < 16:
            self.entered_password += key.upper()
            self._update_pwd_display()

    def _pwd_backspace(self):
        self.entered_password = self.entered_password[:-1]
        self._update_pwd_display()

    def _pwd_clear(self):
        self.entered_password = ""
        self._update_pwd_display()

    def _update_pwd_display(self):
        self.pwd_display_lbl.config(text=self.entered_password if self.entered_password else "--------")

    def _pwd_submit(self):
        if self.entered_password == ADMIN_PASSWORD:
            self.pwd_screen.place_forget()
            self.open_admin_panel()
        else:
            self.pwd_status_lbl.config(text="INCORRECT PASSWORD! TRY AGAIN", fg=RED_ALERT)
            self.entered_password = ""
            self._update_pwd_display()

    # ---- 5. Admin Panel (AI Diagnostics Parameters & Hardware Controls) ----
    def _build_admin_panel(self):
        px = self.px
        self.admin = tk.Frame(self.root, bg=BG)

        head = tk.Frame(self.admin, bg=PANEL, height=self.TOP_H)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(head, text="ADMIN CONSOLE & AI PARAMETERS", font=self.f(16, True), fg=WHITE, bg=PANEL).pack(side="left", padx=px(16))
        self._button(head, "REVERT", GREY_BTN, self.close_overlays, width=px(96), height=px(38), size=10, radius=px(10), fg=WHITE, parent_bg=PANEL).pack(side="right", padx=px(10), pady=px(6))

        # Balanced Split Screen Container (53% Left / 47% Right so neither side looks stretched)
        pad_x = px(14)
        pad_y = px(12)
        body_w = self.W - 2 * pad_x
        body_h = self.H - self.TOP_H - 2 * pad_y

        body = tk.Frame(self.admin, bg=BG, width=body_w, height=body_h)
        body.pack(side="top", fill="both", expand=True, padx=pad_x, pady=pad_y)
        body.pack_propagate(False)

        left_w = int(body_w * 0.53)
        right_w = body_w - left_w - px(12)

        # LEFT CARD: AI Diagnostic Sliders & Guidelines (Proportional 53% width)
        card_ai = tk.Frame(body, bg=PANEL, padx=px(16), pady=px(12), width=left_w, height=body_h)
        card_ai.pack(side="left", fill="y", expand=False)
        card_ai.pack_propagate(False)

        tk.Label(card_ai, text="AI DIAGNOSTIC PARAMETERS", font=self.f(12, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_ai, text="Fine-tune confidence, out-of-scope gating & focus thresholds", font=self.f(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))
        tk.Frame(card_ai, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(10)))

        # Bottom Guide Card & Reset Button anchored neatly at bottom of card_ai
        self.guide_card = tk.Frame(card_ai, bg=CARD, padx=px(10), pady=px(8), height=px(86), highlightbackground=BORDER, highlightthickness=1)
        self.guide_card.pack(side="bottom", fill="x", pady=(px(6), 0))
        self.guide_card.pack_propagate(False)

        self.guide_title_lbl = tk.Label(
            self.guide_card, text="ⓘ  PARAMETER GUIDE",
            font=self.f(9, True), fg=GREEN_ACCENT, bg=CARD, anchor="w"
        )
        self.guide_title_lbl.pack(fill="x")

        self.guide_desc_lbl = tk.Label(
            self.guide_card,
            text="Hover or tap any ⓘ icon to view the meaning and impact of each setting.",
            font=self.f(8), fg=MUTED, bg=CARD, justify="left", anchor="w",
            wraplength=left_w - px(56)
        )
        self.guide_desc_lbl.pack(fill="x", pady=(px(3), 0))

        btn_row = tk.Frame(card_ai, bg=PANEL)
        btn_row.pack(side="bottom", fill="x", pady=(px(4), px(4)))
        self._button(
            btn_row, "↺ RESET DEFAULTS", CARD, self._reset_slider_defaults,
            width=px(176), height=px(42), size=10, radius=px(12), fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        ).pack(side="left")

        self.sliders = {}
        self.slider_badges = {}

        slider_specs = [
            {
                "key": "confidence_threshold",
                "name": "Confidence Threshold",
                "min": 30, "max": 95, "step": 1,
                "get_initial": lambda: int(round(self.threshold * 100)),
                "format": lambda v: f"{int(v)}%",
                "to_param": lambda v: float(v) / 100.0,
                "attr": "threshold",
                "info_title": "Confidence Acceptance Threshold",
                "info_text": "Minimum model certainty required to accept a diagnosis. Lower values allow diagnoses in difficult lighting; higher values trigger 'NOT SURE' to avoid false alarms."
            },
            {
                "key": "ood_margin",
                "name": "OOD Ambiguity Margin",
                "min": 10, "max": 60, "step": 1,
                "get_initial": lambda: int(round(self.ood_margin * 100)),
                "format": lambda v: f"{int(v)}%",
                "to_param": lambda v: float(v) / 100.0,
                "attr": "ood_margin",
                "info_title": "Out-of-Scope Ambiguity Gap",
                "info_text": "Minimum probability lead of the #1 diagnosis over the #2 runner-up. If the model is torn between two classes, this margin rejects the specimen as an ambiguous or unknown plant."
            },
            {
                "key": "ood_logit",
                "name": "Neural Logit Energy Gate",
                "min": 10, "max": 65, "step": 1,
                "get_initial": lambda: int(round(self.ood_logit * 10)),
                "format": lambda v: f"{float(v) / 10.0:.2f}",
                "to_param": lambda v: round(float(v) / 10.0, 2),
                "attr": "ood_logit",
                "info_title": "Neural Logit Energy Gate",
                "info_text": "Raw unnormalized neural activation filter. Real leaves from trained species generate strong logit spikes (>2.4). Uncataloged leaves (e.g. money plants) produce low logits and are safely rejected."
            },
            {
                "key": "sharpness_min",
                "name": "Sharpness Quality Gate",
                "min": 20, "max": 120, "step": 5,
                "get_initial": lambda: int(round(self.sharpness_min)),
                "format": lambda v: f"{int(v)}",
                "to_param": lambda v: float(v),
                "attr": "sharpness_min",
                "info_title": "Sharpness & Focus Quality Gate",
                "info_text": "Spatial Laplacian variance threshold for motion blur detection. Lower settings allow softer webcams to pass; higher settings enforce crisp focus before permitting diagnosis."
            },
        ]

        for spec in slider_specs:
            row = tk.Frame(card_ai, bg=PANEL)
            row.pack(fill="x", padx=px(4), pady=(0, px(8)))

            hdr = tk.Frame(row, bg=PANEL)
            hdr.pack(fill="x", pady=(0, px(2)))

            tk.Label(hdr, text=spec["name"], font=self.f(10, True), fg=WHITE, bg=PANEL).pack(side="left")

            i_btn = tk.Label(
                hdr, text=" ⓘ ", font=self.f(9, True),
                fg=GREEN_ACCENT, bg=CARD, cursor="hand2", padx=px(3), pady=0
            )
            i_btn.pack(side="left", padx=px(6))

            init_val = spec["get_initial"]()
            val_lbl = tk.Label(
                hdr, text=spec["format"](init_val), font=self.f(10, True),
                fg=GREEN_ACCENT, bg=CARD, padx=px(8), pady=px(2)
            )
            val_lbl.pack(side="right")
            self.slider_badges[spec["key"]] = (val_lbl, spec["format"])

            ToolTip(
                i_btn,
                spec["info_title"],
                spec["info_text"],
                font_family=FONT,
                enter_cb=lambda t=spec["info_title"], d=spec["info_text"]: self._update_inline_guide(t, d),
                leave_cb=self._revert_inline_guide
            )

            slider = tk.Scale(
                row,
                from_=spec["min"],
                to=spec["max"],
                resolution=spec["step"],
                orient="horizontal",
                showvalue=False,
                width=px(18),
                sliderlength=px(34),
                bg=PANEL,
                troughcolor=BG,
                activebackground=GREEN_ACCENT,
                highlightthickness=0,
                bd=0,
                cursor="hand2"
            )
            slider.set(init_val)
            slider.pack(fill="x")
            self.sliders[spec["key"]] = (slider, spec)

        # Flush pending initial slider set() events before attaching command callbacks
        self.root.update_idletasks()
        for key, (slider, spec) in self.sliders.items():
            slider.config(command=lambda val, s=spec: self._on_slider_change(s, val))

        # RIGHT CARD: Hardware & System (Balanced 47% width)
        card_sys = tk.Frame(body, bg=PANEL, padx=px(18), pady=px(12), width=right_w, height=body_h)
        card_sys.pack(side="right", fill="y", expand=False)
        card_sys.pack_propagate(False)

        tk.Label(card_sys, text="HARDWARE & SYSTEM", font=self.f(12, True), fg=WHITE, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_sys, text="Peripherals & application runtime", font=self.f(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))
        tk.Frame(card_sys, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(12)))

        # Bottom-anchored CLOSE APPLICATION section so card_sys distributes cleanly
        exit_box = tk.Frame(card_sys, bg=PANEL)
        exit_box.pack(side="bottom", fill="x", pady=(px(2), px(2)))

        tk.Frame(exit_box, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(8)))

        self.exit_btn = self._button(
            exit_box, "✕ CLOSE APPLICATION", RED_ALERT, self.close,
            width=px(220), height=px(46), size=10, radius=px(14), fg=WHITE, parent_bg=PANEL
        )
        self.exit_btn.pack(pady=(0, px(3)))

        tk.Label(
            exit_box, text="Safely exit the kiosk and return to desktop",
            font=self.f(8), fg=MUTED, bg=PANEL
        ).pack()

        # Upper/Middle sections: Camera Status + Detect Webcam + Camera Panel + OTA Update
        cam_box = tk.Frame(card_sys, bg=CARD, padx=px(12), pady=px(8), highlightbackground=BORDER, highlightthickness=1)
        cam_box.pack(fill="x", pady=(0, px(8)))

        self.webcam_status_lbl = tk.Label(
            cam_box, text="Checking camera...", font=self.f(9, True), fg=MUTED, bg=CARD, justify="center", wraplength=right_w - px(64)
        )
        self.webcam_status_lbl.pack(pady=(0, px(6)))

        self.detect_btn = self._button(
            cam_box, "🔍 DETECT WEBCAM", GREEN_PRIMARY, self._trigger_detect_webcam,
            width=px(220), height=px(44), size=10, radius=px(14), fg=WHITE, parent_bg=CARD
        )
        self.detect_btn.pack(pady=(0, px(4)))

        self.detect_msg_lbl = tk.Label(
            cam_box, text="Click to scan and connect USB webcam", font=self.f(8), fg=MUTED, bg=CARD, justify="center", wraplength=right_w - px(64)
        )
        self.detect_msg_lbl.pack()

        # CAMERA CONTROL PANEL + OTA SOFTWARE UPDATE BUTTONS
        cam_tab_box = tk.Frame(card_sys, bg=PANEL)
        cam_tab_box.pack(fill="x", pady=(px(2), 0))

        self.cam_ctrl_btn = self._button(
            cam_tab_box, "📷 CAMERA CONTROL PANEL", CARD, self.open_camera_panel,
            width=px(240), height=px(44), size=10, radius=px(14), fg=GREEN_ACCENT, border=GREEN_ACCENT, parent_bg=PANEL
        )
        self.cam_ctrl_btn.pack(pady=(0, px(6)))

        self.ota_btn = self._button(
            cam_tab_box, "☁ OTA UPDATE (INTERNET)", CARD, self._trigger_ota_update,
            width=px(240), height=px(44), size=10, radius=px(14), fg=AMBER_WARN, border=AMBER_WARN, parent_bg=PANEL
        )
        self.ota_btn.pack(pady=(0, px(4)))

        self.ota_status_lbl = tk.Label(
            cam_tab_box, text=f"AGRILENS v{APP_VERSION} • Pull latest OTA update from GitHub",
            font=self.f(8), fg=MUTED, bg=PANEL, justify="center", wraplength=right_w - px(36)
        )
        self.ota_status_lbl.pack()

    # ---- 5B. Camera Control Panel Tab ----
    def _build_camera_panel(self):
        px = self.px
        self.cam_panel = tk.Frame(self.root, bg=BG)

        head = tk.Frame(self.cam_panel, bg=PANEL, height=self.TOP_H)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(
            head, text="CAMERA CONTROL PANEL",
            font=self.f(15, True), fg=WHITE, bg=PANEL
        ).pack(side="left", padx=px(16))

        self._button(
            head, "REVERT", GREY_BTN, self.close_overlays,
            width=px(96), height=px(38), size=10, radius=px(10), fg=WHITE, parent_bg=PANEL
        ).pack(side="right", padx=(px(4), px(10)), pady=px(6))

        self._button(
            head, "← ADMIN PANEL", CARD, self._back_to_admin_from_camera,
            width=px(136), height=px(38), size=10, radius=px(10), fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        ).pack(side="right", padx=px(4), pady=px(6))

        pad_x = px(14)
        pad_y = px(10)
        body_w = self.W - 2 * pad_x
        body_h = self.H - self.TOP_H - 2 * pad_y

        body = tk.Frame(self.cam_panel, bg=BG, width=body_w, height=body_h)
        body.pack(side="top", fill="both", expand=True, padx=pad_x, pady=pad_y)
        body.pack_propagate(False)

        left_w = int(body_w * 0.47)
        right_w = body_w - left_w - px(12)

        # LEFT CARD: Live Preview + Focus Calibration Meter + Orientation Toggles
        card_prev = tk.Frame(body, bg=PANEL, padx=px(14), pady=px(10), width=left_w, height=body_h)
        card_prev.pack(side="left", fill="y", expand=False)
        card_prev.pack_propagate(False)

        tk.Label(card_prev, text="LIVE FEED & FOCUS HELPER", font=self.f(11, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_prev, text="Adjust focus until the Focus Sharpness Bar peaks in green", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))

        # Bottom 2x2 Quick Action Toggle Grid
        toggles_box = tk.Frame(card_prev, bg=PANEL)
        toggles_box.pack(side="bottom", fill="x", pady=(px(4), 0))

        half_tw = (left_w - px(38)) // 2
        row_t1 = tk.Frame(toggles_box, bg=PANEL)
        row_t1.pack(fill="x", pady=(0, px(6)))

        self.peaking_btn = self._button(
            row_t1, "PEAKING: OFF", CARD, self._toggle_focus_peaking,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.peaking_btn.pack(side="left")

        self.flip_h_btn = self._button(
            row_t1, "MIRROR H: OFF", CARD, self._toggle_flip_h,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.flip_h_btn.pack(side="right")

        row_t2 = tk.Frame(toggles_box, bg=PANEL)
        row_t2.pack(fill="x")

        self.flip_v_btn = self._button(
            row_t2, "FLIP 180°: OFF", CARD, self._toggle_flip_v,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.flip_v_btn.pack(side="left")

        self.reset_cam_btn = self._button(
            row_t2, "↺ RESET CAMERA", CARD, self._reset_camera_defaults,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        )
        self.reset_cam_btn.pack(side="right")

        # Manual Focus Sharpness Meter Bar (directly above toggles)
        focus_box = tk.Frame(card_prev, bg=CARD, padx=px(8), pady=px(6), highlightbackground=BORDER, highlightthickness=1)
        focus_box.pack(side="bottom", fill="x", pady=(px(4), px(6)))

        self.focus_lbl = tk.Label(
            focus_box, text="Focus Sharpness: --%",
            font=self.f(9, True), fg=WHITE, bg=CARD, anchor="w"
        )
        self.focus_lbl.pack(fill="x", pady=(0, px(3)))

        self.FOCUS_BAR_W = left_w - px(48)
        self.FOCUS_BAR_H = px(14)
        self.focus_bar = tk.Canvas(
            focus_box, width=self.FOCUS_BAR_W, height=self.FOCUS_BAR_H,
            bg=BG, highlightthickness=0
        )
        self.focus_bar.pack(anchor="w")

        # Live Camera Preview Canvas (fills remaining upper space of card_prev)
        self.CAM_CTRL_W = left_w - px(32)
        self.CAM_CTRL_H = max(px(160), body_h - px(215))

        prev_border = tk.Frame(card_prev, bg=CARD, padx=2, pady=2)
        prev_border.pack(side="top", expand=True)

        self.cam_ctrl_canvas = tk.Canvas(
            prev_border, width=self.CAM_CTRL_W, height=self.CAM_CTRL_H,
            bg="#000000", highlightthickness=0
        )
        self.cam_ctrl_canvas.pack()
        self.cam_ctrl_img_item = self.cam_ctrl_canvas.create_image(
            self.CAM_CTRL_W // 2, self.CAM_CTRL_H // 2, anchor="center"
        )
        self.cam_ctrl_msg = self.cam_ctrl_canvas.create_text(
            self.CAM_CTRL_W // 2, self.CAM_CTRL_H // 2,
            fill=MUTED, font=self.f(10), justify="center",
            text="Live Camera Preview"
        )

        # RIGHT CARD: 6 Camera Sliders + Hardware Toggles
        card_ctrl = tk.Frame(body, bg=PANEL, padx=px(16), pady=px(10), width=right_w, height=body_h)
        card_ctrl.pack(side="right", fill="y", expand=False)
        card_ctrl.pack_propagate(False)

        tk.Label(card_ctrl, text="CAMERA & IMAGE CONTROLS", font=self.f(11, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_ctrl, text="Real-time contrast, lighting, white balance & macro zoom", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(4)))
        tk.Frame(card_ctrl, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(6)))

        # Bottom USB Hardware Mode Toggles (Auto-Exposure & Auto White Balance)
        usb_hw_box = tk.Frame(card_ctrl, bg=PANEL)
        usb_hw_box.pack(side="bottom", fill="x", pady=(px(4), 0))

        half_uw = (right_w - px(42)) // 2
        self.auto_exp_btn = self._button(
            usb_hw_box, "USB AUTO-EXP: ON", GREEN_PRIMARY, self._toggle_auto_exp,
            width=half_uw, height=px(40), size=9, radius=px(12), fg=WHITE, parent_bg=PANEL
        )
        self.auto_exp_btn.pack(side="left")

        self.auto_wb_btn = self._button(
            usb_hw_box, "USB AUTO-WB: ON", GREEN_PRIMARY, self._toggle_auto_wb,
            width=half_uw, height=px(40), size=9, radius=px(12), fg=WHITE, parent_bg=PANEL
        )
        self.auto_wb_btn.pack(side="right")

        self.cam_sliders = {}
        self.cam_slider_badges = {}

        cam_specs = [
            {
                "key": "cam_contrast",
                "name": "Contrast Control",
                "min": 50, "max": 200, "step": 2,
                "get_initial": lambda: int(self.camera.contrast),
                "format": lambda v: f"{int(v)}%",
                "attr": "contrast",
                "hw": False
            },
            {
                "key": "cam_brightness",
                "name": "Brightness Offset",
                "min": -50, "max": 50, "step": 2,
                "get_initial": lambda: int(self.camera.brightness),
                "format": lambda v: f"{int(v):+d}%",
                "attr": "brightness",
                "hw": False
            },
            {
                "key": "cam_saturation",
                "name": "Color Saturation",
                "min": 0, "max": 200, "step": 5,
                "get_initial": lambda: int(self.camera.saturation),
                "format": lambda v: f"{int(v)}%",
                "attr": "saturation",
                "hw": False
            },
            {
                "key": "cam_sharpness",
                "name": "Sharpness & Vein Crisping",
                "min": 50, "max": 250, "step": 5,
                "get_initial": lambda: int(self.camera.sharpness),
                "format": lambda v: f"{int(v)}%",
                "attr": "sharpness",
                "hw": False
            },
            {
                "key": "cam_wb_temp",
                "name": "White Balance (Cool ↔ Warm)",
                "min": -50, "max": 50, "step": 2,
                "get_initial": lambda: int(self.camera.wb_temp),
                "format": lambda v: "Neutral (0)" if int(v) == 0 else (f"Warm +{int(v)}" if int(v) > 0 else f"Cool {int(v)}"),
                "attr": "wb_temp",
                "hw": True
            },
            {
                "key": "cam_zoom",
                "name": "Macro Digital Zoom",
                "min": 100, "max": 200, "step": 5,
                "get_initial": lambda: int(self.camera.zoom),
                "format": lambda v: f"{float(v) / 100.0:.2f}x",
                "attr": "zoom",
                "hw": False
            },
        ]

        for spec in cam_specs:
            row = tk.Frame(card_ctrl, bg=PANEL)
            row.pack(fill="x", padx=px(2), pady=(0, px(4)))

            hdr = tk.Frame(row, bg=PANEL)
            hdr.pack(fill="x", pady=(0, px(1)))

            tk.Label(hdr, text=spec["name"], font=self.f(9, True), fg=WHITE, bg=PANEL).pack(side="left")

            init_val = spec["get_initial"]()
            val_lbl = tk.Label(
                hdr, text=spec["format"](init_val), font=self.f(9, True),
                fg=GREEN_ACCENT, bg=CARD, padx=px(7), pady=px(1)
            )
            val_lbl.pack(side="right")
            self.cam_slider_badges[spec["key"]] = (val_lbl, spec["format"])

            slider = tk.Scale(
                row,
                from_=spec["min"],
                to=spec["max"],
                resolution=spec["step"],
                orient="horizontal",
                showvalue=False,
                width=px(14),
                sliderlength=px(30),
                bg=PANEL,
                troughcolor=BG,
                activebackground=GREEN_ACCENT,
                highlightthickness=0,
                bd=0,
                cursor="hand2"
            )
            slider.set(init_val)
            slider.pack(fill="x")
            self.cam_sliders[spec["key"]] = (slider, spec)

        self.root.update_idletasks()
        for key, (slider, spec) in self.cam_sliders.items():
            slider.config(command=lambda val, s=spec: self._on_cam_slider_change(s, val))
        self._refresh_cam_toggle_buttons()

    def _on_cam_slider_change(self, spec, val):
        v_int = int(round(float(val)))
        if spec["key"] in self.cam_slider_badges:
            lbl, fmt = self.cam_slider_badges[spec["key"]]
            lbl.config(text=fmt(v_int))
        setattr(self.camera, spec["attr"], v_int)
        if spec.get("hw"):
            self.camera.apply_hardware_controls()
        self._save_current_settings()

    def _refresh_cam_toggle_buttons(self):
        if hasattr(self, "peaking_btn"):
            on = self.camera.focus_peaking
            self.peaking_btn.config(
                text=f"PEAKING: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "flip_h_btn"):
            on = self.camera.flip_h
            self.flip_h_btn.config(
                text=f"MIRROR H: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "flip_v_btn"):
            on = self.camera.flip_v
            self.flip_v_btn.config(
                text=f"FLIP 180°: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "auto_exp_btn"):
            on = self.camera.auto_exp
            self.auto_exp_btn.config(
                text=f"USB AUTO-EXP: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "auto_wb_btn"):
            on = self.camera.auto_wb
            self.auto_wb_btn.config(
                text=f"USB AUTO-WB: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )

    def _toggle_focus_peaking(self):
        self.camera.focus_peaking = not self.camera.focus_peaking
        self._refresh_cam_toggle_buttons()

    def _toggle_flip_h(self):
        self.camera.flip_h = not self.camera.flip_h
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _toggle_flip_v(self):
        self.camera.flip_v = not self.camera.flip_v
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _toggle_auto_exp(self):
        self.camera.auto_exp = not self.camera.auto_exp
        self.camera.apply_hardware_controls()
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _toggle_auto_wb(self):
        self.camera.auto_wb = not self.camera.auto_wb
        self.camera.apply_hardware_controls()
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _reset_camera_defaults(self):
        self.camera.contrast = 100
        self.camera.brightness = 0
        self.camera.saturation = 100
        self.camera.sharpness = 100
        self.camera.wb_temp = 0
        self.camera.zoom = 100
        self.camera.flip_h = False
        self.camera.flip_v = False
        self.camera.auto_exp = True
        self.camera.auto_wb = True
        self.camera.focus_peaking = False
        self.camera.apply_hardware_controls()
        self._sync_cam_panel_widgets()
        self._save_current_settings()

    def _sync_cam_panel_widgets(self):
        for key, (slider, spec) in getattr(self, "cam_sliders", {}).items():
            init_val = spec["get_initial"]()
            slider.config(command="")
            slider.set(init_val)
            if key in self.cam_slider_badges:
                lbl, fmt = self.cam_slider_badges[key]
                lbl.config(text=fmt(init_val))
        self.root.update_idletasks()
        for key, (slider, spec) in getattr(self, "cam_sliders", {}).items():
            slider.config(command=lambda val, s=spec: self._on_cam_slider_change(s, val))
        self._refresh_cam_toggle_buttons()

    def open_camera_panel(self):
        self._sync_cam_panel_widgets()
        self.cam_panel.place(x=0, y=0, relwidth=1, relheight=1)
        self.cam_panel.lift()

    def _back_to_admin_from_camera(self):
        self._sync_sliders_to_attributes()
        self._save_current_settings()
        self.cam_panel.place_forget()
        self.open_admin_panel()

    def _update_camera_panel_preview(self, frame):
        if not hasattr(self, "cam_panel") or not self.cam_panel.winfo_ismapped():
            return
        if frame is None:
            self.cam_ctrl_canvas.itemconfig(
                self.cam_ctrl_msg,
                text="No webcam connected.\nUse Admin -> DETECT WEBCAM."
            )
            return

        # Update Focus Sharpness Meter
        pct, raw_lap = self.camera.compute_focus_metric(frame)
        if pct >= 68:
            f_col = GREEN_ACCENT
            f_tag = "PEAK FOCUS — LOCK RING"
        elif pct >= 42:
            f_col = AMBER_WARN
            f_tag = "GOOD — FINE-TUNE RING"
        else:
            f_col = RED_ALERT
            f_tag = "BLURRY — TWIST FOCUS RING"

        self.focus_lbl.config(
            text=f"Focus Sharpness: {pct}% ({f_tag})",
            fg=f_col
        )
        self.focus_bar.delete("all")
        fill_w = max(4, int(self.FOCUS_BAR_W * (pct / 100.0)))
        self.focus_bar.create_rectangle(0, 0, fill_w, self.FOCUS_BAR_H, fill=f_col, width=0)

        # Render live preview showing 100% of camera FoV (with optional neon Focus Peaking overlay)
        prev_img = self.camera.render_focus_peaking(frame) if self.camera.focus_peaking else frame
        disp = self._render_full_fov(prev_img, self.CAM_CTRL_W, self.CAM_CTRL_H)
        self._cam_ctrl_photo = ImageTk.PhotoImage(disp)
        self.cam_ctrl_canvas.itemconfig(self.cam_ctrl_img_item, image=self._cam_ctrl_photo)
        self.cam_ctrl_canvas.itemconfig(self.cam_ctrl_msg, text="")

    def _update_inline_guide(self, title, desc):
        if hasattr(self, "guide_title_lbl") and hasattr(self, "guide_desc_lbl"):
            self.guide_title_lbl.config(text=f"ⓘ  {title.upper()}")
            self.guide_desc_lbl.config(text=desc, fg=TEXT)

    def _revert_inline_guide(self):
        if hasattr(self, "guide_title_lbl") and hasattr(self, "guide_desc_lbl"):
            self.guide_title_lbl.config(text="ⓘ  PARAMETER GUIDE")
            self.guide_desc_lbl.config(
                text="Hover or tap any ⓘ icon to view the meaning and impact of each setting.",
                fg=MUTED
            )

    def _on_slider_change(self, spec, val):
        val_float = float(val)
        if spec["key"] in self.slider_badges:
            lbl, fmt = self.slider_badges[spec["key"]]
            lbl.config(text=fmt(val_float))

        param_val = spec["to_param"](val_float)
        setattr(self, spec["attr"], param_val)
        self._update_inline_guide(spec["info_title"], spec["info_text"])
        self._save_current_settings()

    def _save_current_settings(self):
        cfg = {
            "confidence_threshold": round(self.threshold, 3),
            "ood_margin": round(self.ood_margin, 3),
            "ood_logit": round(self.ood_logit, 2),
            "sharpness_min": round(self.sharpness_min, 1),
            "cam_contrast": int(self.camera.contrast),
            "cam_brightness": int(self.camera.brightness),
            "cam_saturation": int(self.camera.saturation),
            "cam_sharpness": int(self.camera.sharpness),
            "cam_wb_temp": int(self.camera.wb_temp),
            "cam_zoom": int(self.camera.zoom),
            "cam_flip_h": bool(self.camera.flip_h),
            "cam_flip_v": bool(self.camera.flip_v),
            "cam_auto_exp": bool(self.camera.auto_exp),
            "cam_auto_wb": bool(self.camera.auto_wb),
            "language": getattr(self, "lang", "EN"),
        }
        save_kiosk_config(cfg)

    def _reset_slider_defaults(self):
        defaults = {
            "confidence_threshold": int(CONFIDENCE_THRESHOLD * 100),
            "ood_margin": int(OOD_MARGIN_THRESHOLD * 100),
            "ood_logit": int(OOD_LOGIT_THRESHOLD * 10),
            "sharpness_min": int(SHARPNESS_MIN_THRESHOLD)
        }
        for key, (slider, spec) in self.sliders.items():
            if key in defaults:
                slider.set(defaults[key])
                val_float = float(defaults[key])
                if key in self.slider_badges:
                    lbl, fmt = self.slider_badges[key]
                    lbl.config(text=fmt(val_float))
                param_val = spec["to_param"](val_float)
                setattr(self, spec["attr"], param_val)

        self._save_current_settings()
        self._update_inline_guide(
            "RESET DEFAULTS COMPLETE",
            "All AI diagnostic and quality parameters have been restored to factory recommended calibration defaults."
        )

    def _sync_sliders_to_attributes(self):
        for key, (slider, spec) in getattr(self, "sliders", {}).items():
            try:
                val_float = float(slider.get())
                param_val = spec["to_param"](val_float)
                setattr(self, spec["attr"], param_val)
            except Exception:
                pass
        for key, (slider, spec) in getattr(self, "cam_sliders", {}).items():
            try:
                v_int = int(round(float(slider.get())))
                setattr(self.camera, spec["attr"], v_int)
            except Exception:
                pass

    def open_admin_panel(self):
        self._hide_mode_dropdown()
        for key, (slider, spec) in getattr(self, "sliders", {}).items():
            init_val = spec["get_initial"]()
            slider.config(command="")
            slider.set(init_val)
            if key in self.slider_badges:
                lbl, fmt = self.slider_badges[key]
                lbl.config(text=fmt(init_val))
        self.root.update_idletasks()
        for key, (slider, spec) in getattr(self, "sliders", {}).items():
            slider.config(command=lambda val, s=spec: self._on_slider_change(s, val))

        is_conn = (self.camera and self.camera.kind != "none")
        cam_text = self.camera.kind if is_conn else "No Webcam Connected"
        color = GREEN_PRIMARY if is_conn else RED_ALERT
        self.webcam_status_lbl.config(text=f"Current Status:\n{cam_text}", fg=color)
        self.detect_msg_lbl.config(text="Click DETECT WEBCAM to scan USB ports", fg=MUTED)
        self._revert_inline_guide()
        self.admin.place(x=0, y=0, relwidth=1, relheight=1)
        self.admin.lift()

    def _trigger_detect_webcam(self):
        self.detect_btn.config(state="disabled", text="SCANNING...")
        self.detect_msg_lbl.config(text="Scanning USB ports for video devices...", fg=MUTED)
        self.root.update_idletasks()

        q = queue.Queue()
        def scan_worker():
            ok, msg = self.camera.detect_webcam()
            q.put((ok, msg))

        threading.Thread(target=scan_worker, daemon=True).start()

        def poll_scan():
            try:
                ok, msg = q.get_nowait()
                self._on_detect_webcam_finished(ok, msg)
                return
            except queue.Empty:
                pass
            if self.running:
                self.root.after(40, poll_scan)

        poll_scan()

    def _trigger_ota_update(self, silent_boot=False):
        """
        Pulls the latest software & logos over the internet from GitHub immediately on event:
        - Automatically on boot/startup (silent_boot=True)
        - Manually when '☁ OTA UPDATE (INTERNET)' is tapped in Admin Console (silent_boot=False)
        """
        if getattr(self, "_ota_in_progress", False):
            if not silent_boot and hasattr(self, "ota_status_lbl"):
                self.ota_status_lbl.config(text="OTA check already in progress...", fg=AMBER_WARN)
            return
        self._ota_in_progress = True

        if not silent_boot:
            if hasattr(self, "ota_btn"):
                self.ota_btn.config(state="disabled", text="☁ CHECKING OTA...")
            if hasattr(self, "ota_status_lbl"):
                self.ota_status_lbl.config(text="Connecting to GitHub over internet for immediate OTA update...", fg=AMBER_WARN)
            self.root.update_idletasks()

        q = queue.Queue()

        def ota_worker():
            import hashlib
            import py_compile
            import shutil
            import urllib.request

            ota_files = [
                ("main.py", os.path.join(APP_BASE_DIR, "main.py")),
                ("labels.txt", os.path.join(APP_BASE_DIR, "labels.txt")),
                ("logos/agrilens_logo.jpg", os.path.join(LOGOS_DIR, "agrilens_logo.jpg")),
                ("logos/gundecha_logo.png", os.path.join(LOGOS_DIR, "gundecha_logo.png")),
                ("HOW_TO_RUN_ON_RASPBERRY_PI.md", os.path.join(APP_BASE_DIR, "HOW_TO_RUN_ON_RASPBERRY_PI.md")),
                ("setup_rpi.sh", os.path.join(APP_BASE_DIR, "setup_rpi.sh")),
                ("run_agrilens.sh", os.path.join(APP_BASE_DIR, "run_agrilens.sh")),
                ("ota_update.sh", os.path.join(APP_BASE_DIR, "ota_update.sh")),
                ("setup_remote_ota.sh", os.path.join(APP_BASE_DIR, "setup_remote_ota.sh")),
            ]

            try:
                os.makedirs(LOGOS_DIR, exist_ok=True)
                legacy_assets = os.path.join(APP_BASE_DIR, "assets")
                if os.path.exists(legacy_assets):
                    shutil.rmtree(legacy_assets, ignore_errors=True)
                ts = int(time.time())
                updated_count = 0
                remote_ver = APP_VERSION

                for rel_url, dest_path in ota_files:
                    url = f"{OTA_REPO_RAW_BASE}/{rel_url}?t={ts}"
                    req = urllib.request.Request(
                        url,
                        headers={
                            "User-Agent": f"AGRILENS-Kiosk/{APP_VERSION}",
                            "Cache-Control": "no-cache",
                        }
                    )
                    data = None
                    last_err = None
                    # On fresh reboot Wi-Fi may take a few seconds to come online; retry main.py briefly on boot
                    attempts = 4 if (silent_boot and rel_url == "main.py") else 1
                    for attempt in range(attempts):
                        try:
                            with urllib.request.urlopen(req, timeout=12) as resp:
                                data = resp.read()
                            break
                        except Exception as e_file:
                            last_err = e_file
                            if attempt + 1 < attempts:
                                time.sleep(2.5)
                    if data is None:
                        if rel_url == "main.py":
                            raise RuntimeError(f"Internet/GitHub unreachable: {last_err}")
                        continue

                    if not data:
                        continue

                    if rel_url == "main.py":
                        text_src = data.decode("utf-8", errors="replace")
                        remote_ver = _extract_version_from_code(text_src)
                        remote_model_sha = _extract_const_from_code(text_src, "MODEL_SHA256").lower()
                        local_tuple = _parse_version_tuple(APP_VERSION)
                        remote_tuple = _parse_version_tuple(remote_ver)
                        if remote_tuple < local_tuple:
                            q.put((
                                "up_to_date",
                                f"Downgrade blocked: Local v{APP_VERSION} is newer than remote v{remote_ver}."
                            ))
                            return
                        if silent_boot and remote_tuple == local_tuple:
                            q.put((
                                "up_to_date",
                                f"Up to date! Running latest version (v{APP_VERSION})."
                            ))
                            return

                        # Check if trained ONNX model (agrilens.onnx) changed on GitHub via MODEL_SHA256
                        model_dest = os.path.join(APP_BASE_DIR, "agrilens.onnx")
                        local_model_sha = ""
                        if os.path.exists(model_dest):
                            try:
                                with open(model_dest, "rb") as f_m:
                                    local_model_sha = hashlib.sha256(f_m.read()).hexdigest().lower()
                            except Exception:
                                local_model_sha = ""
                        if not os.path.exists(model_dest) or (remote_model_sha and local_model_sha != remote_model_sha):
                            model_url = f"{OTA_REPO_RAW_BASE}/agrilens.onnx?t={ts}"
                            m_req = urllib.request.Request(
                                model_url,
                                headers={
                                    "User-Agent": f"AGRILENS-Kiosk/{APP_VERSION}",
                                    "Cache-Control": "no-cache",
                                }
                            )
                            with urllib.request.urlopen(m_req, timeout=60) as m_resp:
                                m_data = m_resp.read()
                            if m_data and len(m_data) > 1_000_000:
                                dl_sha = hashlib.sha256(m_data).hexdigest().lower()
                                if not remote_model_sha or dl_sha == remote_model_sha:
                                    m_tmp = model_dest + ".ota_tmp"
                                    with open(m_tmp, "wb") as f_mout:
                                        f_mout.write(m_data)
                                    os.replace(m_tmp, model_dest)
                                    updated_count += 1

                    new_hash = hashlib.sha256(data).hexdigest()
                    old_hash = ""
                    if os.path.exists(dest_path):
                        try:
                            with open(dest_path, "rb") as f_old:
                                old_hash = hashlib.sha256(f_old.read()).hexdigest()
                        except Exception:
                            old_hash = ""

                    if new_hash != old_hash:
                        tmp_path = dest_path + ".ota_tmp"
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with open(tmp_path, "wb") as f_out:
                            f_out.write(data)
                        if rel_url == "main.py":
                            py_compile.compile(tmp_path, doraise=True)
                        os.replace(tmp_path, dest_path)
                        if dest_path.endswith(".sh") and platform.system() == "Linux":
                            try:
                                os.chmod(dest_path, 0o755)
                            except Exception:
                                pass
                        updated_count += 1

                if updated_count > 0:
                    q.put(("updated", f"OTA Updated to v{remote_ver} ({updated_count} file(s))! Restarting now..."))
                else:
                    q.put(("up_to_date", f"Up to date! Running latest GitHub build (v{remote_ver})."))
            except Exception as err:
                q.put(("error", f"OTA Update failed: {err}"))

        threading.Thread(target=ota_worker, daemon=True).start()

        def poll_ota():
            try:
                status, msg = q.get_nowait()
                self._ota_in_progress = False
                if status == "updated":
                    if hasattr(self, "ota_status_lbl"):
                        self.ota_status_lbl.config(text=msg, fg=GREEN_ACCENT)
                    if hasattr(self, "ota_btn"):
                        self.ota_btn.config(text="✓ UPDATED — RESTARTING", bg=GREEN_PRIMARY, fg=WHITE)
                    self.splash_logo_img = self._load_splash_logo()
                    self.root.after(150, self._restart_application)
                elif status == "up_to_date":
                    if hasattr(self, "ota_status_lbl"):
                        self.ota_status_lbl.config(text=msg, fg=GREEN_ACCENT)
                    if hasattr(self, "ota_btn"):
                        self.ota_btn.config(state="normal", text="☁ OTA UPDATE (INTERNET)")
                    self.splash_logo_img = self._load_splash_logo()
                else:
                    if not silent_boot and hasattr(self, "ota_status_lbl"):
                        self.ota_status_lbl.config(text=msg, fg=RED_ALERT)
                    if hasattr(self, "ota_btn"):
                        self.ota_btn.config(state="normal", text="☁ OTA UPDATE (INTERNET)")
                return
            except queue.Empty:
                pass
            if self.running:
                self.root.after(50, poll_ota)

        poll_ota()

    def _restart_application(self):
        """Cleanly saves settings, releases the camera, and restarts the kiosk process after OTA update."""
        self.running = False
        try:
            self._sync_sliders_to_attributes()
            self._save_current_settings()
        except Exception:
            pass
        try:
            if self.camera:
                self.camera.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=APP_BASE_DIR)
        sys.exit(0)

    def _has_camera(self):
        return bool(self.camera and self.camera.kind != "none")

    def _is_live_mode(self):
        return bool(self.input_mode == "LIVE" and self._has_camera())

    def _on_detect_webcam_finished(self, ok, msg):
        if ok:
            self.set_input_mode("LIVE", browse_on_file=False)
            self.webcam_status_lbl.config(text=f"Connected:\n{self.camera.kind}", fg=GREEN_PRIMARY)
            self.detect_msg_lbl.config(text="SUCCESS: Webcam connected — Live Mode active!", fg=GREEN_PRIMARY)
            self.canvas.itemconfig(self.msg_txt, text="")
            self.detect_btn.config(state="normal", text="DETECT WEBCAM")
            self.root.after(750, self.close_overlays)
        else:
            self.set_input_mode("FILE", browse_on_file=False)
            self.webcam_status_lbl.config(text="Current Status: No Webcam Found (File Mode Active)", fg=AMBER_WARN)
            self.detect_msg_lbl.config(text=f"{msg} — Defaulted to File Mode.", fg=AMBER_WARN)
            self.detect_btn.config(state="normal", text="DETECT WEBCAM")

    def close_overlays(self):
        self._hide_mode_dropdown()
        was_admin = (hasattr(self, "admin") and self.admin.winfo_ismapped()) or (hasattr(self, "cam_panel") and self.cam_panel.winfo_ismapped())
        if was_admin:
            self._sync_sliders_to_attributes()
            self._save_current_settings()
        self.picker.place_forget()
        self.pwd_screen.place_forget()
        self.admin.place_forget()
        if hasattr(self, "cam_panel"):
            self.cam_panel.place_forget()
        if was_admin and self.paused and self.last_probs:
            self._render_diagnosis(self.last_probs, self.last_raw_out)

    # ---- 6. Live Camera Loop & AI Pipeline (Non-Blocking Async Bootstrap) ----
    def _start_async_bootstrap(self):
        # Force initial paint so the UI is visible, responsive, and avoids "Not Responding"
        ensure_diagnosis_samples_dir()
        self.root.update_idletasks()
        self._init_queue = queue.Queue()

        def worker():
            classifier = Classifier(MODEL_PATH, LABELS_PATH)
            parsed = [parse_label(l) for l in classifier.labels]
            crops = [p[0] for p in parsed]
            plants = list(dict.fromkeys(c for c in crops if c))
            self.camera.detect_webcam()
            self._init_queue.put((classifier, parsed, crops, plants))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_init_queue()
        # Trigger immediate non-blocking OTA check on boot/startup
        self.root.after(200, lambda: self._trigger_ota_update(silent_boot=True))

    def _poll_init_queue(self):
        try:
            res = self._init_queue.get_nowait()
            self._on_bootstrap_complete(*res)
            return
        except queue.Empty:
            pass
        if self.running:
            self.root.after(40, self._poll_init_queue)

    def _on_bootstrap_complete(self, classifier, parsed, crops, plants):
        self.classifier = classifier
        self.parsed = parsed
        self.crops = crops
        self.plants = plants
        self.bootstrap_done = True

        # Keep the startup logo displayed in the image window for the full 5 seconds on startup
        elapsed = time.monotonic() - self.startup_start_ts
        rem_ms = max(10, int(round((STARTUP_LOGO_SECONDS - elapsed) * 1000)))
        self._update_stats_bar()
        self._preview_loop()
        self.root.after(rem_ms, self._finish_startup_splash)

    def _finish_startup_splash(self):
        if not self.running or not self.startup_splash_active:
            return
        self.startup_splash_active = False
        self.last_activity_ts = time.monotonic()
        self._hide_fullscreen_screensaver()
        # Default to LIVE mode when camera is connected; auto-default to FILE mode if not connected
        if self._has_camera():
            self.set_input_mode("LIVE", browse_on_file=False)
        else:
            self.set_input_mode("FILE", browse_on_file=False)

    def _preview_loop(self):
        if not self.running:
            return

        # 1. During 5-second startup full-screen screensaver: keep screensaver visible until timer or touch/click
        if self.startup_splash_active:
            self.root.after(int(1000 / PREVIEW_FPS), self._preview_loop)
            return

        # 2. Check for 3-minute inactivity -> activate full-screen logo screensaver and turn off camera
        if (
            not self.standby_active
            and not self._waking_from_standby
            and not self._file_dialog_open
            and (time.monotonic() - self.last_activity_ts) >= INACTIVITY_TIMEOUT_SECONDS
        ):
            self._enter_inactivity_standby()
            self.root.after(int(1000 / PREVIEW_FPS), self._preview_loop)
            return

        # 3. While in standby or waking camera: do not read camera frames
        if self.standby_active or self._waking_from_standby:
            self.root.after(int(1000 / PREVIEW_FPS), self._preview_loop)
            return

        cam_panel_open = hasattr(self, "cam_panel") and self.cam_panel.winfo_ismapped()
        live_active = self._is_live_mode() and not self.paused
        if (live_active or cam_panel_open) and self._has_camera():
            frame = self.camera.read()
            if frame is not None:
                if live_active:
                    self.latest_frame = frame
                    self._show_image(frame)
                if cam_panel_open:
                    self._update_camera_panel_preview(frame)
            elif not self._has_camera():
                # Camera disconnected mid-session -> automatically fall back to File Mode
                if self.input_mode == "LIVE":
                    self.set_input_mode("FILE", browse_on_file=False)
                if cam_panel_open:
                    self._update_camera_panel_preview(None)
                self._update_stats_bar()
        elif cam_panel_open:
            self._update_camera_panel_preview(None)
        self.root.after(int(1000 / PREVIEW_FPS), self._preview_loop)

    def _render_full_fov(self, img, target_w, target_h):
        """Scales image to display 100% of the complete Field of View (zero edge cropping)."""
        iw, ih = img.size
        if iw <= 0 or ih <= 0:
            return img.resize((target_w, target_h), RESAMPLE)
        scale = min(target_w / iw, target_h / ih)
        nw = max(1, int(round(iw * scale)))
        nh = max(1, int(round(ih * scale)))
        resized = img.resize((nw, nh), RESAMPLE)
        if nw == target_w and nh == target_h:
            return resized
        canvas_im = Image.new("RGB", (target_w, target_h), (5, 10, 7))
        canvas_im.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
        return canvas_im

    def _show_image(self, img):
        iw, ih = img.size
        if iw > 0 and ih > 0:
            scale = min(self.CAM_W / iw, self.CAM_H / ih)
            nw = max(1, int(round(iw * scale)))
            nh = max(1, int(round(ih * scale)))
            ox = (self.CAM_W - nw) // 2
            oy = (self.CAM_H - nh) // 2
            self._img_disp_rect = (ox, oy, ox + nw, oy + nh)
        else:
            self._img_disp_rect = (0, 0, self.CAM_W, self.CAM_H)

        disp = self._render_full_fov(img, self.CAM_W, self.CAM_H)
        self._photo = ImageTk.PhotoImage(disp)
        self.canvas.itemconfig(self.img_item, image=self._photo)
        self.canvas.itemconfig(self.msg_txt, text="")

    # ---- Interactive Manual Crop Selection Handle Methods ----
    def _init_crop_selection(self, full_default=False):
        ix0, iy0, ix1, iy1 = self._img_disp_rect
        dw = max(1, ix1 - ix0)
        dh = max(1, iy1 - iy0)
        if full_default:
            pad_x = self.px(4)
            pad_y = self.px(4)
        else:
            # Default 14% inset automatically excludes phone bezels & fingers when showing a mobile screen
            pad_x = max(self.px(20), int(round(dw * 0.14)))
            pad_y = max(self.px(20), int(round(dh * 0.14)))
        x0 = min(ix0 + dw // 3, ix0 + pad_x)
        y0 = min(iy0 + dh // 3, iy0 + pad_y)
        x1 = max(ix1 - dw // 3, ix1 - pad_x)
        y1 = max(iy1 - dh // 3, iy1 - pad_y)
        self.crop_box = (x0, y0, x1, y1)
        self.canvas.itemconfig("crop_ui", state="normal")
        self.canvas.tag_raise("crop_ui")
        self.canvas.tag_raise(self.live_badge)
        self._update_crop_overlay()

    def _hide_crop_selection(self):
        self.crop_box = None
        self._crop_drag_mode = None
        self.canvas.itemconfig("crop_ui", state="hidden")
        self.canvas.config(cursor="")

    def _get_handle_centers(self):
        if not self.crop_box:
            return {}
        x0, y0, x1, y1 = self.crop_box
        mx = (x0 + x1) // 2
        my = (y0 + y1) // 2
        return {
            "nw": (x0, y0),
            "n":  (mx, y0),
            "ne": (x1, y0),
            "e":  (x1, my),
            "se": (x1, y1),
            "s":  (mx, y1),
            "sw": (x0, y1),
            "w":  (x0, my),
        }

    def _update_crop_overlay(self):
        if not self.crop_box:
            return
        x0, y0, x1, y1 = self.crop_box
        cw, ch = self.CAM_W, self.CAM_H

        # 1. Outer dimmed scrim rectangles (top, bottom, left, right)
        self.canvas.coords(self.crop_scrim_top, 0, 0, cw, y0)
        self.canvas.coords(self.crop_scrim_bottom, 0, y1, cw, ch)
        self.canvas.coords(self.crop_scrim_left, 0, y0, x0, y1)
        self.canvas.coords(self.crop_scrim_right, x1, y0, cw, y1)

        # 2. Main crop rectangle border
        self.canvas.coords(self.crop_rect, x0, y0, x1, y1)

        # 3. Rule-of-thirds inner grid lines
        bw = x1 - x0
        bh = y1 - y0
        gx1, gx2 = x0 + bw // 3, x0 + (2 * bw) // 3
        gy1, gy2 = y0 + bh // 3, y0 + (2 * bh) // 3
        self.canvas.coords(self.crop_grid_lines[0], gx1, y0, gx1, y1)
        self.canvas.coords(self.crop_grid_lines[1], gx2, y0, gx2, y1)
        self.canvas.coords(self.crop_grid_lines[2], x0, gy1, x1, gy1)
        self.canvas.coords(self.crop_grid_lines[3], x0, gy2, x1, gy2)

        # 4. 8 Corner & Edge Midpoint Grab Handles
        hs = self.px(7)
        for h_key, (hx, hy) in self._get_handle_centers().items():
            self.canvas.coords(self.crop_handles[h_key], hx - hs, hy - hs, hx + hs, hy + hs)

        # 5. Update crop pixel resolution badge
        px0, py0, px1, py1 = self._get_crop_pixel_bounds()
        pw, ph = max(1, px1 - px0), max(1, py1 - py0)
        self.canvas.itemconfig(
            self.crop_info_badge,
            text=f"CROP: {pw}×{ph} px  •  DRAG HANDLES  •  DOUBLE-TAP: FULL"
        )

    def _get_crop_pixel_bounds(self):
        if self.captured_frame is None:
            return (0, 0, 224, 224)
        iw, ih = self.captured_frame.size
        if not self.crop_box:
            return (0, 0, iw, ih)
        ix0, iy0, ix1, iy1 = self._img_disp_rect
        dw = max(1, ix1 - ix0)
        dh = max(1, iy1 - iy0)
        cx0, cy0, cx1, cy1 = self.crop_box

        px0 = int(round((cx0 - ix0) * iw / dw))
        py0 = int(round((cy0 - iy0) * ih / dh))
        px1 = int(round((cx1 - ix0) * iw / dw))
        py1 = int(round((cy1 - iy0) * ih / dh))

        px0 = max(0, min(iw - 16, px0))
        py0 = max(0, min(ih - 16, py0))
        px1 = max(px0 + 16, min(iw, px1))
        py1 = max(py0 + 16, min(ih, py1))
        return (px0, py0, px1, py1)

    def _get_cropped_leaf_image(self):
        if self.captured_frame is None:
            return self.latest_frame
        if not self.crop_box:
            return self.captured_frame
        px0, py0, px1, py1 = self._get_crop_pixel_bounds()
        return self.captured_frame.crop((px0, py0, px1, py1))

    def _hit_test_crop_controls(self, x, y):
        if not self.crop_box:
            return None
        hit_r = self.px(22)
        best_h = None
        best_d2 = hit_r * hit_r
        for h_key, (hx, hy) in self._get_handle_centers().items():
            d2 = (x - hx) ** 2 + (y - hy) ** 2
            if d2 <= best_d2:
                best_d2 = d2
                best_h = h_key
        if best_h:
            return best_h

        x0, y0, x1, y1 = self.crop_box
        edge_tol = self.px(12)
        if y0 - edge_tol <= y <= y1 + edge_tol:
            if abs(x - x0) <= edge_tol:
                return "w"
            if abs(x - x1) <= edge_tol:
                return "e"
        if x0 - edge_tol <= x <= x1 + edge_tol:
            if abs(y - y0) <= edge_tol:
                return "n"
            if abs(y - y1) <= edge_tol:
                return "s"

        if x0 <= x <= x1 and y0 <= y <= y1:
            return "move"
        return "new"

    def _on_canvas_press(self, event):
        self._hide_mode_dropdown()
        if self.startup_splash_active or self.standby_active or self._waking_from_standby or time.monotonic() < self._wake_guard_until:
            return
        if not self.paused:
            self.handle_capture_or_retake()
            return
        if self.captured_frame is None:
            return
        if not self.crop_box:
            self._init_crop_selection()

        mode = self._hit_test_crop_controls(event.x, event.y)
        self._crop_drag_start = (event.x, event.y)
        if mode == "new":
            ix0, iy0, ix1, iy1 = self._img_disp_rect
            sx = max(ix0, min(ix1, event.x))
            sy = max(iy0, min(iy1, event.y))
            min_s = self.px(44)
            x0 = max(ix0, min(ix1 - min_s, sx - min_s // 2))
            y0 = max(iy0, min(iy1 - min_s, sy - min_s // 2))
            self.crop_box = (x0, y0, x0 + min_s, y0 + min_s)
            self._crop_drag_start = (x0, y0)
            self._crop_box_start = self.crop_box
            self._crop_drag_mode = "se"
            self._update_crop_overlay()
        else:
            self._crop_drag_mode = mode
            self._crop_box_start = self.crop_box

    def _on_canvas_drag(self, event):
        if not self.paused or not self._crop_drag_mode or not self._crop_box_start:
            return
        ix0, iy0, ix1, iy1 = self._img_disp_rect
        min_s = self.px(44)
        sx, sy = self._crop_drag_start
        dx = event.x - sx
        dy = event.y - sy
        bx0, by0, bx1, by1 = self._crop_box_start
        mode = self._crop_drag_mode

        if mode == "move":
            bw = bx1 - bx0
            bh = by1 - by0
            nx0 = max(ix0, min(ix1 - bw, bx0 + dx))
            ny0 = max(iy0, min(iy1 - bh, by0 + dy))
            self.crop_box = (nx0, ny0, nx0 + bw, ny0 + bh)
        else:
            x0, y0, x1, y1 = bx0, by0, bx1, by1
            if "w" in mode:
                x0 = max(ix0, min(x1 - min_s, bx0 + dx))
            if "e" in mode:
                x1 = min(ix1, max(x0 + min_s, bx1 + dx))
            if "n" in mode:
                y0 = max(iy0, min(y1 - min_s, by0 + dy))
            if "s" in mode:
                y1 = min(iy1, max(y0 + min_s, by1 + dy))
            self.crop_box = (x0, y0, x1, y1)

        self._update_crop_overlay()

    def _on_canvas_release(self, event):
        if not self.paused or not self._crop_drag_mode:
            return
        self._crop_drag_mode = None
        self._crop_box_start = None
        cropped = self._get_cropped_leaf_image()
        if cropped is not None:
            is_hi = (getattr(self, "lang", "EN") == "HI")
            px0, py0, px1, py1 = self._get_crop_pixel_bounds()
            pw, ph = max(1, px1 - px0), max(1, py1 - py0)
            score, rating, q_msg, q_color = LeafQualityAI.assess(cropped, self.sharpness_min, lang=self.lang)
            self.quality_lbl.config(
                text=(f"चयनित भाग ({pw}×{ph} px) | {q_msg}" if is_hi else f"Selected Crop ({pw}×{ph} px) | {q_msg}"),
                fg=q_color
            )
            if self.last_probs is not None:
                self.banner_frame.config(bg=GREEN_PRIMARY)
                self.banner.config(
                    text=("क्रॉप क्षेत्र बदला गया — अभी जांचें दबाएं" if is_hi else "CROP SELECTION ADJUSTED — TAP DIAGNOSE NOW"),
                    bg=GREEN_PRIMARY, fg=WHITE
                )
                self.diagnose_btn.config(text="🔍  अभी जांचें" if is_hi else "🔍  DIAGNOSE NOW", bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE)

    def _on_canvas_double_click(self, event):
        if self.paused and self.captured_frame is not None:
            is_hi = (getattr(self, "lang", "EN") == "HI")
            self._init_crop_selection(full_default=True)
            cropped = self._get_cropped_leaf_image()
            score, rating, q_msg, q_color = LeafQualityAI.assess(cropped, self.sharpness_min, lang=self.lang)
            self.quality_lbl.config(
                text=(f"पूर्ण चित्र चयनित | {q_msg}" if is_hi else f"Full Image Selected | {q_msg}"),
                fg=q_color
            )

    def _on_canvas_motion(self, event):
        if not self.paused or not self.crop_box:
            self.canvas.config(cursor="hand2")
            return
        mode = self._hit_test_crop_controls(event.x, event.y)
        cursor_map = {
            "nw": "top_left_corner",
            "ne": "top_right_corner",
            "sw": "bottom_left_corner",
            "se": "bottom_right_corner",
            "n": "sb_v_double_arrow",
            "s": "sb_v_double_arrow",
            "w": "sb_h_double_arrow",
            "e": "sb_h_double_arrow",
            "move": "fleur",
            "new": "crosshair",
        }
        self.canvas.config(cursor=cursor_map.get(mode, "hand2"))

    def _reset_panel(self):
        has_cam = self._has_camera()
        is_live = self._is_live_mode()
        is_hi = (getattr(self, "lang", "EN") == "HI")
        self._refresh_mode_ui()
        if not self.paused:
            self._hide_crop_selection()
            self.canvas.itemconfig(self.guide, state="normal")
        self.banner_frame.config(bg=GREY_BTN)
        if self.selected_plant is None:
            self.plant_lbl.config(text="मोड: ऑटो-डिटेक्ट (बीटा)" if is_hi else "Mode: Auto-Detect (Beta Production)")
        else:
            p_txt = translate_crop_hi(self.selected_plant) if is_hi else self.selected_plant.upper()
            self.plant_lbl.config(text=f"चयनित फसल: {p_txt}" if is_hi else f"Selected Plant: {p_txt}")

        if is_live:
            self.banner.config(
                text=("तैयार — पत्ती को कैमरे के सामने रखें" if is_hi else "READY — AIM LEAF AT CAMERA"),
                bg=GREY_BTN, fg=WHITE
            )
            self.disease_lbl.config(
                text=(
                    "पत्ती बॉक्स में रखें -> फोटो लें -> हैंडल खींचें -> पत्ती जांचें दबाएं"
                    if is_hi else
                    "Aim leaf -> Tap CAPTURE -> Drag Crop Handles -> Tap DIAGNOSE"
                )
            )
            self.capture_btn.config(text="📸  फोटो लें" if is_hi else "📸  CAPTURE LEAF", bg=GREEN_PRIMARY, fg=WHITE)
            self.canvas.itemconfig(self.live_badge, text="लाइव कैमरा" if is_hi else "LIVE WEBCAM", fill=GREEN_ACCENT)
            self.canvas.itemconfig(self.msg_txt, text="")
            self.quality_lbl.config(
                text=("पत्ती गुणवत्ता एआई: पत्ती को बॉक्स के अंदर रखें" if is_hi else "Leaf Quality AI: Align leaf inside box"),
                fg=MUTED
            )
        else:
            self.banner.config(
                text=("फाइल मोड — फाइल से पत्ती की फोटो चुनें" if is_hi else "FILE MODE — PICK LEAF IMAGE FROM FILE"),
                bg=GREY_BTN, fg=WHITE
            )
            self.disease_lbl.config(
                text=(
                    "फाइल से चुनें दबाएं -> क्रॉप हैंडल खींचें -> पत्ती जांचें दबाएं"
                    if is_hi else
                    "Tap PICK FROM FILE -> Drag Crop Handles -> Tap DIAGNOSE"
                )
            )
            self.capture_btn.config(text="📂  फाइल से चुनें" if is_hi else "📂  PICK FROM FILE", bg=GREEN_PRIMARY, fg=WHITE)
            if is_hi:
                badge_txt = "फाइल मोड (सैंपल)" if has_cam else "फाइल मोड (कैमरा नहीं)"
            else:
                badge_txt = "FILE MODE (SAMPLES)" if has_cam else "FILE MODE (NO CAMERA)"
            self.canvas.itemconfig(self.live_badge, text=badge_txt, fill=AMBER_WARN)
            if not self.paused:
                self._photo = None
                self.canvas.itemconfig(self.img_item, image="")
                if is_hi:
                    header_msg = (
                        "फाइल मोड चयनित — डिफ़ॉल्ट सैंपल फाइलें ब्राउज़ करें"
                        if has_cam else
                        "कोई कैमरा जुड़ा नहीं है — डिफ़ॉल्ट फाइल मोड सक्रिय"
                    )
                    self.canvas.itemconfig(
                        self.msg_txt,
                        text=(
                            f"{header_msg}\n\n"
                            "नीचे 'फाइल से चुनें' दबाएं (या यहाँ क्लिक करें)\n"
                            "फ़ोल्डर: diagnosis_samples/ (सेब, आम, आलू, टमाटर)"
                        )
                    )
                else:
                    header_msg = (
                        "File Mode Selected — Browse Default Sample Files"
                        if has_cam else
                        "No camera connected — Defaulted to File Mode"
                    )
                    self.canvas.itemconfig(
                        self.msg_txt,
                        text=(
                            f"{header_msg}\n\n"
                            "Tap 'PICK FROM FILE' below (or click here)\n"
                            "Folder: diagnosis_samples/ (Apple, Mango, Potato, Tomato)"
                        )
                    )
            self.quality_lbl.config(
                text=(
                    "फाइल मोड: diagnosis_samples/ में पत्ती के सैंपल चुनें (सेब, आम, आलू, टमाटर)"
                    if is_hi else
                    "File Mode: Browse leaf samples in diagnosis_samples/ (Apple, Mango, Potato, Tomato)"
                ),
                fg=MUTED
            )

        self.diagnose_btn.config(text="🔍  पत्ती जांचें" if is_hi else "🔍  DIAGNOSE LEAF", bg=CARD, border=GREEN_ACCENT, fg=WHITE)
        self._draw_bar(0, GREY_BTN, "पत्ती की प्रतीक्षा है..." if is_hi else "Waiting for leaf...")
        for row, num, txt in self.step_rows:
            num.config(bg=GREEN_PRIMARY, fg=WHITE)
            txt.config(text="")
            row.pack_forget()
        self.cam_border.config(bg=CARD)

    # ---- 7. SEPARATE ACTIONS: Capture / Pick from File, Retake, and Diagnose ----
    def pick_image_from_file(self):
        """Opens file picker inside the fixed diagnosis_samples/ folder structure when File Mode is active."""
        self._hide_mode_dropdown()
        if self.startup_splash_active or self.standby_active or self._waking_from_standby or time.monotonic() < self._wake_guard_until:
            return False
        is_hi = (getattr(self, "lang", "EN") == "HI")
        base_dir = ensure_diagnosis_samples_dir()
        init_dir = base_dir
        if self.selected_plant:
            cand = os.path.join(base_dir, self.selected_plant)
            if os.path.isdir(cand):
                init_dir = cand

        try:
            self.root.attributes("-topmost", False)
        except Exception:
            pass

        self._file_dialog_open = True
        self.last_activity_ts = time.monotonic()
        try:
            filepath = filedialog.askopenfilename(
                parent=self.root,
                initialdir=init_dir,
                title="जांच के लिए पत्ती की फोटो चुनें (diagnosis_samples)" if is_hi else "Select Leaf Image for Diagnosis (diagnosis_samples)",
                filetypes=[
                    ("Leaf Images", "*.jpg *.jpeg *.png *.bmp *.webp *.JPG *.JPEG *.PNG"),
                    ("All Files", "*.*"),
                ],
            )
        finally:
            self._file_dialog_open = False
            self.last_activity_ts = time.monotonic()
        if not filepath or not os.path.isfile(filepath):
            return False

        try:
            with Image.open(filepath) as raw_im:
                loaded_img = raw_im.convert("RGB")
        except Exception as e:
            self.quality_lbl.config(
                text=(f"फोटो फाइल नहीं खुल सकी: {e}" if is_hi else f"Could not open image file: {e}"),
                fg=RED_ALERT
            )
            return False

        self.latest_frame = loaded_img
        self.captured_frame = loaded_img
        self.last_probs = None
        self.last_raw_out = None

        self.paused = True
        self.canvas.itemconfig(self.guide, state="hidden")
        short_name = os.path.basename(filepath)
        if len(short_name) > 26:
            short_name = short_name[:23] + "..."
        self.last_file_short_name = short_name

        self._show_image(self.captured_frame)
        self._init_crop_selection()
        self.canvas.itemconfig(
            self.live_badge,
            text=(f"फाइल: {short_name} (क्रॉप समायोजित करें)" if is_hi else f"FILE: {short_name} (ADJUST CROP)"),
            fill=GREEN_ACCENT
        )

        cropped = self._get_cropped_leaf_image()
        score, rating, q_msg, q_color = LeafQualityAI.assess(cropped, self.sharpness_min, lang=self.lang)
        self.quality_lbl.config(
            text=(f"पत्ती क्रॉप करने के लिए हैंडल खींचें ({short_name}) | {q_msg}" if is_hi else f"Drag handles to crop leaf ({short_name}) | {q_msg}"),
            fg=q_color
        )
        self.banner_frame.config(bg=GREEN_PRIMARY)
        self.banner.config(
            text=("क्रॉप हैंडल समायोजित करें -> अभी जांचें दबाएं" if is_hi else "ADJUST CROP HANDLES -> TAP DIAGNOSE NOW"),
            bg=GREEN_PRIMARY, fg=WHITE
        )
        self.disease_lbl.config(
            text=(
                "सटीक पत्ती क्षेत्र चुनने के लिए फोटो पर हरे हैंडल खींचें, फिर 'अभी जांचें' दबाएं।"
                if is_hi else
                "Drag green handles on image to select exact leaf area, then tap DIAGNOSE NOW."
            )
        )

        self.capture_btn.config(text="📂  फाइल से चुनें" if is_hi else "📂  PICK FROM FILE", bg=AMBER_WARN, fg=WHITE)
        self.diagnose_btn.config(text="🔍  अभी जांचें" if is_hi else "🔍  DIAGNOSE NOW", bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE)
        return True

    def handle_capture_or_retake(self):
        """Toggles between CAPTURE/RETAKE in Live Mode, or opens PICK FROM FILE in File Mode."""
        self._hide_mode_dropdown()
        if self.startup_splash_active or self.standby_active or self._waking_from_standby or time.monotonic() < self._wake_guard_until:
            return
        if not self._is_live_mode():
            self.pick_image_from_file()
            return

        is_hi = (getattr(self, "lang", "EN") == "HI")
        if not self.paused:
            # 1. ACTION: CAPTURE (Freezes frame and activates manual crop selection handles)
            if self.latest_frame is not None:
                self.paused = True
                self.captured_frame = self.latest_frame
                self.canvas.itemconfig(self.guide, state="hidden")
                self._show_image(self.captured_frame)
                self._init_crop_selection()
                self.canvas.itemconfig(
                    self.live_badge,
                    text=("फोटो ली गई — क्रॉप करने हेतु हैंडल खींचें" if is_hi else "CAPTURED — DRAG HANDLES TO CROP"),
                    fill=GREEN_ACCENT
                )

                cropped = self._get_cropped_leaf_image()
                score, rating, q_msg, q_color = LeafQualityAI.assess(cropped, self.sharpness_min, lang=self.lang)
                self.quality_lbl.config(
                    text=(f"पत्ती का भाग चुनने के लिए हैंडल खींचें | {q_msg}" if is_hi else f"Drag handles to select leaf area | {q_msg}"),
                    fg=q_color
                )
                self.banner_frame.config(bg=GREEN_PRIMARY)
                self.banner.config(
                    text=("क्रॉप हैंडल समायोजित करें -> अभी जांचें दबाएं" if is_hi else "ADJUST CROP HANDLES -> TAP DIAGNOSE NOW"),
                    bg=GREEN_PRIMARY, fg=WHITE
                )
                self.disease_lbl.config(
                    text=(
                        "सटीक पत्ती क्षेत्र चुनने के लिए हरे हैंडल खींचें, फिर 'अभी जांचें' दबाएं।"
                        if is_hi else
                        "Drag green handles to select exact leaf area, then tap DIAGNOSE NOW."
                    )
                )

                # Swap Capture to RETAKE and Diagnose to DIAGNOSE NOW
                self.capture_btn.config(text="↺  पुनः फोटो लें" if is_hi else "↺  RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)
                self.diagnose_btn.config(text="🔍  अभी जांचें" if is_hi else "🔍  DIAGNOSE NOW", bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE)
            else:
                self.quality_lbl.config(
                    text=("कैमरा तैयार नहीं है। फाइल मोड चुनें या USB वेबकैम जांचें।" if is_hi else "Camera not ready. Switch to File Mode or check USB webcam."),
                    fg=RED_ALERT
                )
        else:
            # 2. ACTION: RETAKE (Unfreeze and hide crop handles)
            self.paused = False
            self.captured_frame = None
            self.last_probs = None
            self.last_raw_out = None
            self._hide_crop_selection()
            self.canvas.itemconfig(self.guide, state="normal")
            self._reset_panel()
            self._update_stats_bar()

    def handle_diagnose(self):
        """Runs MobileNetV4 inference strictly on the manually cropped leaf region."""
        self._hide_mode_dropdown()
        if self.startup_splash_active or self.standby_active or self._waking_from_standby or time.monotonic() < self._wake_guard_until:
            return
        if not self._is_live_mode() and self.captured_frame is None:
            if not self.pick_image_from_file():
                return

        is_hi = (getattr(self, "lang", "EN") == "HI")
        if self._is_live_mode() and self.captured_frame is None and self.latest_frame is not None:
            # If user directly pressed DIAGNOSE while live, capture frame and initialize crop box first
            self.paused = True
            self.captured_frame = self.latest_frame
            self.canvas.itemconfig(self.guide, state="hidden")
            self._show_image(self.captured_frame)
            self._init_crop_selection()
            self.canvas.itemconfig(
                self.live_badge,
                text=("फोटो ली गई — क्रॉप करने हेतु हैंडल खींचें" if is_hi else "CAPTURED — DRAG HANDLES TO CROP"),
                fill=GREEN_ACCENT
            )
            self.capture_btn.config(text="↺  पुनः फोटो लें" if is_hi else "↺  RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)
            self.diagnose_btn.config(text="🔍  अभी जांचें" if is_hi else "🔍  DIAGNOSE NOW", bg=GREEN_PRIMARY, border=GREEN_ACCENT, fg=WHITE)

        target_img = self._get_cropped_leaf_image()
        if target_img is None:
            if self._is_live_mode():
                self.disease_lbl.config(
                    text=("पत्ती की फोटो नहीं ली गई! कृपया कैमरे के सामने पत्ती रखें और 'फोटो लें' दबाएं।" if is_hi else "No leaf image captured! Please aim at leaf and tap CAPTURE.")
                )
            else:
                self.disease_lbl.config(
                    text=("कोई फोटो नहीं चुनी गई! पत्ती की फोटो लोड करने के लिए 'फाइल से चुनें' दबाएं।" if is_hi else "No image selected! Tap PICK FROM FILE to load a leaf image.")
                )
            return

        px0, py0, px1, py1 = self._get_crop_pixel_bounds()
        pw, ph = max(1, px1 - px0), max(1, py1 - py0)
        score, rating, q_msg, q_color = LeafQualityAI.assess(target_img, self.sharpness_min, lang=self.lang)
        self.quality_lbl.config(
            text=(f"चयनित भाग ({pw}×{ph} px) | {q_msg}" if is_hi else f"Diagnosed Crop ({pw}×{ph} px) | {q_msg}"),
            fg=q_color
        )

        if self.classifier:
            res = self.classifier.predict(target_img)
            if len(res) == 3:
                probs, ms, raw_out = res
            else:
                probs, ms = res
                raw_out = None
            self.last_probs = probs
            self.last_raw_out = raw_out
            self.latency_ms = ms
            self._render_diagnosis(probs, raw_out)
            self._update_stats_bar()

    def _render_diagnosis(self, probs, raw_out=None):
        is_hi = (getattr(self, "lang", "EN") == "HI")
        labels = self.classifier.labels
        n = len(labels)
        raw_probs = list(probs)
        adj = list(probs)

        # Unfiltered raw metrics for Out-Of-Distribution (OOD) validation
        raw_sorted = sorted(raw_probs, reverse=True)
        raw_top1 = raw_sorted[0]
        raw_top2 = raw_sorted[1] if len(raw_sorted) > 1 else 0.0
        raw_margin = raw_top1 - raw_top2
        max_logit = float(np.max(raw_out)) if raw_out is not None else 10.0

        # Plant filtering when a target crop is explicitly selected
        plant_tot = 1.0
        if self.selected_plant:
            plant_keep = [self.crops[i] == self.selected_plant for i in range(n)]
            plant_tot = sum(p for p, m in zip(raw_probs, plant_keep) if m)
            keep = [self.crops[i] == self.selected_plant or not self.crops[i] for i in range(n)]
            tot = sum(p for p, m in zip(adj, keep) if m)
            if tot > 0:
                adj = [p / tot if m else 0.0 for p, m in zip(adj, keep)]

        adj_sorted = sorted(adj, reverse=True)
        active_margin = adj_sorted[0] - (adj_sorted[1] if len(adj_sorted) > 1 else 0.0)

        best = max(range(n), key=lambda i: adj[i])
        conf = adj[best]
        crop, cond, healthy = self.parsed[best]

        # 1. OUT-OF-DISTRIBUTION (OOD) / UNKNOWN PLANT DETECTION:
        # Rejects non-target flora / background when Other_Plant_or_Background wins,
        # when raw neural logit energy is too weak, or when selected crop has negligible probability.
        is_negative_class = ("other" in cond.lower()) or ("background" in cond.lower())
        is_unknown_plant = (
            is_negative_class
            or (max_logit < self.ood_logit)
            or (self.selected_plant is not None and plant_tot < 0.12)
        )

        # 2. LOW CONFIDENCE / AMBIGUITY GATE:
        # Triggers 'LOW CONFIDENCE — PLEASE RETAKE' when confidence is below threshold
        # or top-1 vs top-2 margin is too narrow.
        is_low_confidence = (conf < self.threshold) or (active_margin < self.ood_margin)

        crop_disp = translate_crop_hi(crop) if is_hi else crop
        cond_disp = translate_cond_hi(cond) if is_hi else cond

        if is_unknown_plant:
            status = "अज्ञात पौधा / समर्थित सूची से बाहर" if is_hi else "UNKNOWN PLANT / OUT OF SCOPE"
            color = AMBER_WARN
            plant_txt = "पौधा: अपरिचित (समर्थित सूची से बाहर)" if is_hi else "Plant: Unrecognized (Outside Catalog)"
            disease_txt = (
                "नमूना समर्थित फसलों से बाहर है (सेब, आम, आलू, टमाटर)"
                if is_hi else
                "Specimen outside supported scope (Apple, Mango, Potato, Tomato)"
            )
            steps = OOD_STEPS_HI if is_hi else OOD_STEPS
            num_color = AMBER_WARN
            btn_txt = "अज्ञात पत्ती" if is_hi else "UNKNOWN LEAF"
            btn_color = AMBER_WARN
        elif is_low_confidence:
            status = "कम स्पष्टता (LOW CONFIDENCE) — पुनः फोटो लें" if is_hi else "LOW CONFIDENCE — PLEASE RETAKE"
            color = AMBER_WARN
            if self.selected_plant:
                p_sel = translate_crop_hi(self.selected_plant) if is_hi else self.selected_plant.upper()
                plant_txt = f"चयनित फसल: {p_sel}" if is_hi else f"Selected: {p_sel}"
            else:
                plant_txt = "मोड: ऑटो-डिटेक्ट (बीटा)" if is_hi else "Mode: Auto-Detect (Beta Production)"
            disease_txt = "कम विश्वास स्तर — सुरक्षित पहचान संभव नहीं" if is_hi else "Low Confidence — Cannot Safely Identify"
            steps = UNSURE_STEPS_HI if is_hi else UNSURE_STEPS
            num_color = AMBER_WARN
            btn_txt = "कम स्पष्टता" if is_hi else "LOW CONFIDENCE"
            btn_color = AMBER_WARN
        elif healthy:
            status = "स्वस्थ पत्ती — कोई रोग नहीं" if is_hi else "HEALTHY LEAF — NO DISEASE"
            color = GREEN_PRIMARY
            if is_hi:
                auto_suffix = " (स्वतः पहचाना गया)" if self.selected_plant is None else ""
                plant_txt = f"फसल: {crop_disp}{auto_suffix}" if crop else ("ऑटो-डिटेक्ट (बीटा)" if self.selected_plant is None else "")
                disease_txt = "कोई रोग नहीं मिला (स्वस्थ पत्ती)"
                btn_txt = "स्वस्थ फसल"
            else:
                auto_suffix = " (Auto-Detected)" if self.selected_plant is None else ""
                plant_txt = f"Plant: {crop}{auto_suffix}" if crop else ("Auto-Detect (Beta Production)" if self.selected_plant is None else "")
                disease_txt = "No Disease Detected (Healthy Foliage)"
                btn_txt = "HEALTHY CROP"
            steps = get_recommendation(crop, cond, lang=self.lang)
            num_color = GREEN_PRIMARY
            btn_color = GREEN_PRIMARY
        else:
            status = f"{cond_disp} रोग मिला" if is_hi else f"{cond.upper()} DETECTED"
            color = RED_ALERT
            if is_hi:
                auto_suffix = " (स्वतः पहचाना गया)" if self.selected_plant is None else ""
                plant_txt = f"फसल: {crop_disp}{auto_suffix}" if crop else ("ऑटो-डिटेक्ट (बीटा)" if self.selected_plant is None else "")
                disease_txt = cond_disp
                btn_txt = "रोग मिला"
            else:
                auto_suffix = " (Auto-Detected)" if self.selected_plant is None else ""
                plant_txt = f"Plant: {crop}{auto_suffix}" if crop else ("Auto-Detect (Beta Production)" if self.selected_plant is None else "")
                disease_txt = cond
                btn_txt = "DISEASE FOUND"
            steps = get_recommendation(crop, cond, lang=self.lang)
            num_color = RED_ALERT
            btn_color = RED_ALERT

        # Update Banner & Texts
        self.banner_frame.config(bg=color)
        self.banner.config(text=status, bg=color, fg=WHITE)
        self.plant_lbl.config(text=plant_txt)
        self.disease_lbl.config(text=disease_txt)
        self.cam_border.config(bg=color)
        self.diagnose_btn.config(text=btn_txt, bg=btn_color, fg=WHITE)

        # Update Confidence Bar (if unknown plant, display the rejection message)
        if is_unknown_plant:
            rej_txt = (
                f"अनिश्चित मिलान: {raw_top1 * 100:.1f}% (अज्ञात के रूप में अस्वीकृत)"
                if is_hi else
                f"Uncertain Match: {raw_top1 * 100:.1f}% (Rejected as Unknown)"
            )
            self._draw_bar(raw_top1, color, rej_txt)
        else:
            self._draw_bar(conf, color)

        # UpdateSteps
        for row, _, _ in self.step_rows:
            row.pack_forget()
        for (row, num, txt), step in zip(self.step_rows, steps):
            num.config(bg=num_color)
            txt.config(text=step)
            row.pack(fill="x", pady=(0, self.px(4)))

    def _draw_bar(self, frac, color, text=None):
        self.bar.delete("all")
        if frac > 0:
            self.bar.create_rectangle(0, 0, int(self.BAR_W * frac), self.BAR_H, fill=color, width=0)
        is_hi = (getattr(self, "lang", "EN") == "HI")
        default_lbl = f"विश्वास स्तर (Confidence): {frac * 100:.1f}%" if is_hi else f"Confidence: {frac * 100:.1f}%"
        lbl_text = default_lbl if text is None else text
        self.bar.create_text(
            self.BAR_W // 2, self.BAR_H // 2, fill=TEXT,
            font=self.f(10, True), text=lbl_text
        )

    def _update_stats_bar(self):
        mode_text = self.classifier.mode if self.classifier else "Initializing..."
        if self.classifier and self.classifier.error_reason:
            mode_text = f"DEMO ({self.classifier.error_reason})"
        lat = f"{self.latency_ms:.0f} ms" if self.latency_ms > 0 else "-- ms"
        if self.standby_active:
            cam = "OFF (Standby)"
            in_mode = "STANDBY"
        elif self.startup_splash_active:
            cam = self.camera.kind if self.camera else "starting"
            in_mode = "SPLASH (5s)"
        else:
            cam = self.camera.kind if self.camera else "none"
            in_mode = "LIVE" if self._is_live_mode() else "FILE"
        py_ver = f"Py {platform.python_version()}"
        self.stats_lbl.config(text=f"AGRILENS v{APP_VERSION} | Input: {in_mode} | AI: {mode_text} | Latency: {lat} | Camera: {cam} | {py_ver}")

    def close(self):
        self.running = False
        try:
            self._sync_sliders_to_attributes()
            self._save_current_settings()
        except Exception:
            pass
        for job in self.root.tk.call("after", "info"):
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        try:
            if self.camera:
                self.camera.close()
        finally:
            self.root.destroy()


# =============================================================================
# 8. MAIN ENTRY POINT
# =============================================================================
def _kill_previous_instances():
    """Terminates any older running AGRILENS main.py process so the new version replaces it cleanly."""
    if platform.system() != "Linux":
        return
    try:
        my_pid = os.getpid()
        res = subprocess.run(["pgrep", "-f", "main.py"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.isdigit() and int(line) != my_pid:
                subprocess.run(["kill", "-9", line], stderr=subprocess.DEVNULL)
    except Exception:
        pass


if __name__ == "__main__":
    _kill_previous_instances()
    root = tk.Tk()
    app = AgriLensApp(root)
    root.mainloop()
