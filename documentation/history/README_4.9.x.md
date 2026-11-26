# AGRILENS — AI Plant Health & Disease Diagnosis Kiosk

[![Version](https://img.shields.io/badge/version-v4.9.4-16a34a.svg)](REVISION.md)
[![Build](https://img.shields.io/badge/build-2026--11--15%2017%3A35%20IST-0ea5e9.svg)](REVISION.md)
[![Model](https://img.shields.io/badge/backbone-MobileNetV4--Conv--Small%20ONNX-22c55e.svg)](../MobileV4/agrilens.onnx)
[![Classes](https://img.shields.io/badge/classes-24%20Classes%20(4%20Crops)-f59e0b.svg)](../MobileV4/labels.txt)
[![Partner](https://img.shields.io/badge/partner-Gundecha%20Education%20Academy-dc2626.svg)](https://www.gundechaedu.org/)

**AGRILENS** is an edge AI kiosk system engineered for instant, real-time agricultural crop disease diagnosis in rural and field environments. Built for deployment on **Raspberry Pi 5** touch kiosks and **Windows/Linux PC** workstations, it pairs a single-file **MobileNetV4-Conv-Small ONNX** vision backbone with training-aligned full-frame multi-scale inference, an on-device **Leaf Image Quality AI** validator, a real-time **Camera Control & ISP Panel**, and **Out-of-Distribution (OOD)** rejection gating.

---

## 📌 Build Information

| Attribute | Specification |
| :--- | :--- |
| **Current Version** | **`v4.9.4` (Production Release)** |
| **Last Build Date** | **`2026-11-15 17:35 IST` (November 15, 2026)** |
| **Vision Model** | MobileNetV4-Conv-Small (`mobilenetv4_conv_small`) Single-File ONNX (~10.07 MB) |
| **Training Dataset** | 23,893 images across 24 classes (15 Epochs, 97.28% – 98.31% Val Accuracy) |
| **Inference Latency** | ~24–40 ms on CPU (3-view training-aligned ensemble on Raspberry Pi 5 / PC) |
| **Diagnostic Classes** | **24 Classes** across **4 Crops** (`Apple`, `Mango`, `Potato`, `Tomato`) + OOD Logit & Margin Gating |
| **Target Hardware** | Raspberry Pi 5 (8 GB) or PC + Waveshare 7" Capacitive Touch Display (1024×600) + USB Webcam |
| **Python Runtime** | Python 3.10 – 3.13+ |
| **Academic Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |
| **Changelog & Revision History** | See [`REVISION.md`](REVISION.md) |

---

## 🌟 Key Features in v4.9.4

- **24-Class MobileNetV4 Edge Vision:** Powered by a single-file MobileNetV4-Conv-Small ONNX model (`agrilens.onnx`, ~10.07 MB with all weights embedded) trained on 23,893 images across 24 classes for Apple, Mango, Potato, and Tomato.
- **Bilingual Main Screen (Hindi / English `🌐 हिंदी / EN`):** Instant 1-tap language toggle on the main screen that translates all farmer-facing instructions, buttons (`फोटो लें`, `पुनः फोटो लें`, `फाइल से चुनें`, `पत्ती जांचें`, `अभी जांचें`), crop & disease names, Leaf Quality AI status messages, confidence bar labels, and 4-step farmer recommendations into Hindi (persisted in `kiosk_config.json`), while keeping the Admin Console and Camera Control Panel in English.
- **Event-Driven Over-The-Air (OTA) Software Updater & Remote Internet Provisioning:** Updates **immediately on reboot/startup** (`_trigger_ota_update(silent_boot=True)` and `agrilens-ota.service`) and **immediately on manual tap** via the **`☁ OTA UPDATE (INTERNET)`** button in the Admin Console (with strict anti-downgrade guard and per-file SHA-256 verification), plus `setup_remote_ota.sh` (provisioning **Raspberry Pi Connect** and **OpenSSH**).
- **Full-Screen Logo Screensaver (Startup & 3-Minute Inactivity Camera Auto-Off):** Consolidated all logo images (`agrilens_logo.jpg` and `gundecha_logo.png`) exclusively inside the `logos/` directory (`assets/` removed). Displays `agrilens_logo.jpg` as a **full-screen screensaver over the complete screen** (never inside the camera viewport) on startup and after **3 minutes of inactivity** (automatically turning off the camera via `self.camera.close()`). Touching or clicking anywhere on the screen immediately deactivates the screensaver and wakes the camera back into **Live Mode**.
- **Live Mode vs. File Mode Dropdown (`MODE: LIVE MODE ▾` / `MODE: FILE MODE ▾`):** Top-bar dropdown selector allowing the user to switch between **Live Mode** (webcam feed) and **File Mode** (browsing the built-in `diagnosis_samples/{Apple,Mango,Potato,Tomato}` catalog) at any time—even while a camera is connected. Defaults to **Live Mode** when a camera is attached and automatically defaults to **File Mode** when no camera is connected.
- **Interactive Manual Crop Selection Handles & Mobile Screen Optimization:** Upon capturing a leaf (`CAPTURE LEAF`) or loading an image (`PICK FROM FILE`), an adjustable 8-handle crop selection box appears on the canvas (pre-inset by 14% to exclude mobile phone bezels and fingers). Pressing **`DIAGNOSE NOW`** evaluates only the manually cropped area using a dual-stream Natural + Mobile-Screen-Restored (anti-glare, de-moiré, blue-backlight-neutralized) ensemble.
- **Direct 1-Tap Admin Access:** Tapping **`ADMIN`** opens the Admin Console and Camera Control Panel directly (password lock disabled).
- **Full-FoV 4:3 Camera Viewport:** Displays 100% of the 640×480 webcam field of view without edge cropping on the 1024×600 Waveshare 7" display.
- **Dedicated Camera Control Panel & Real-Time ISP:** Accessible via `ADMIN` -> `📷 CAMERA CONTROL PANEL`:
  - **Focus Calibration Meter & Neon Focus Peaking:** Real-time Laplacian focus sharpness bar ($0-100\%$) and neon-green edge highlight (`PEAKING: ON`) for manual lens focusing.
  - **6 Real-Time ISP Sliders:** Contrast ($50-200\%$), Brightness ($-50\%$ to $+50\%$), Color Saturation ($0-200\%$), Sharpness & Vein Crisping ($50-250\%$), White Balance Temperature (Cool $-50$ to Warm $+50$), and Macro Digital Zoom ($1.00\times - 2.00\times$).
  - **Hardware & Orientation Toggles:** Horizontal Mirror (`MIRROR H`), Vertical Flip (`FLIP 180°`), USB Auto-Exposure (`USB AUTO-EXP` with 50Hz anti-flicker via `v4l2-ctl`), and USB Auto White Balance (`USB AUTO-WB`).
- **Admin Calibration Sliders & `(i)` Tooltips:** PIN-protected Admin panel (`PIN: AGRILENS`) with real-time sliders for Confidence Threshold ($30\% - 95\%$), OOD Ambiguity Margin ($10\% - 60\%$), Neural Logit Energy Gate ($1.00 - 6.50$), and Sharpness Quality Gate ($20 - 120$).
- **Dual-Path Persistent Configuration:** Live adjustments are automatically sanitized, clamped, and persisted to both `kiosk_config.json` and `~/.agrilens_kiosk_config.json`.
- **Leaf Quality AI Validator:** Real-time pre-inference evaluation of **Sharpness & Focus** (40%), **Lighting & Exposure** (30%), and **Foliage Presence** (30%).
- **Integrated Extension Recommendations:** Farmer-ready cultural and chemical management guidance across all 19 disease and healthy categories.

---

## 📦 Supported Crops & Disease Classes (24 Classes)

| Crop | Classes | Supported Diagnostic Conditions |
| :--- | :---: | :--- |
| **Apple** | 3 | Apple Rust (`Apple_Rust`), Apple Scab (`Apple_Scab`), Healthy (`Apple_healthy`) |
| **Mango** | 8 | Anthracnose (`Mango_Anthracnose`), Bacterial Canker (`Mango_Bacterial_Canker`), Cutting Weevil (`Mango_Cutting_Weevil`), Die Back (`Mango_Die_Back`), Gall Midge (`Mango_Gall_Midge`), Powdery Mildew (`Mango_Powdery_Mildew`), Sooty Mould (`Mango_Sooty_Mould`), Healthy (`Mango_Healthy`) |
| **Potato** | 3 | Early Blight (`Potato_Early_blight`), Late Blight (`Potato_Late_blight`), Healthy (`Potato_healthy`) |
| **Tomato** | 10 | Bacterial Spot (`Tomato_Bacterial_spot`), Early Blight (`Tomato_Early_blight`), Late Blight (`Tomato_Late_blight`), Leaf Mold (`Tomato_Leaf_Mold`), Septoria Leaf Spot (`Tomato_Septoria_leaf_spot`), Two-Spotted Spider Mite (`Tomato_Spider_mites_Two_spotted_spider_mite`), Target Spot (`Tomato_Target_Spot`), Yellow Leaf Curl Virus (`Tomato_Tomato_YellowLeaf_Curl_Virus`), Mosaic Virus (`Tomato_Tomato_mosaic_virus`), Healthy (`Tomato_healthy`) |

---

## 📁 Repository Structure

```text
AGRILENS/
├── MobileV4/                                    # PC & Development Touch Kiosk Application
│   ├── logos/
│   │   ├── agrilens_logo.jpg                    # Official AGRILENS EXPISCOR 2026 Startup & Standby Logo
│   │   └── gundecha_logo.png                    # Official Gundecha Education Academy crest
│   ├── diagnosis_samples/                       # 24 Reference test images for File Mode (Apple, Mango, Potato, Tomato)
│   ├── Training_Scripts/
│   │   ├── consolidate_datasets.py              # Dataset verification & consolidation script (24 classes)
│   │   ├── train_mobilenetv4.py                 # Local PyTorch MobileNetV4 15-epoch training & single-file ONNX exporter
│   │   └── Train_AGRILENS_MobileNetV4.ipynb     # 1-Click Google Colab T4 GPU retraining notebook
│   ├── agrilens.onnx                            # Single-file MobileNetV4 ONNX model (~10.07 MB)
│   ├── kiosk_config.json                        # Persisted AI & Camera ISP calibration parameters
│   ├── labels.txt                               # 24-class model label definitions
│   ├── main.py                                  # Main Touch Kiosk GUI application
│   ├── requirements.txt                         # Python dependencies
│   └── run_agrilens_py313.bat                   # Windows Python 3.13 1-click launcher
│
├── AGRILENS_RaspberryPi/                        # Standalone Deployment Package for Raspberry Pi 5
│   ├── logos/
│   │   ├── agrilens_logo.jpg                    # Official AGRILENS EXPISCOR 2026 Startup & Standby Logo
│   │   └── gundecha_logo.png                    # Official Gundecha Education Academy crest
│   ├── diagnosis_samples/                       # 24 Reference test images for offline File Mode testing
│   ├── agrilens.onnx                            # Single-file MobileNetV4 ONNX model (~10.07 MB)
│   ├── HOW_TO_RUN_ON_RASPBERRY_PI.md            # Complete Raspberry Pi 5, Remote Internet & OTA guide
│   ├── kiosk_config.json                        # Raspberry Pi calibrated config defaults
│   ├── labels.txt                               # 24-class model label definitions
│   ├── main.py                                  # Main Touch Kiosk GUI application
│   ├── ota_update.sh                            # Over-The-Air (OTA) GitHub software updater script
│   ├── requirements.txt                         # Python dependencies
│   ├── run_agrilens.sh                          # Linux / Raspberry Pi shell launcher
│   ├── setup_remote_ota.sh                      # Remote Internet (RPi Connect + SSH) & Auto-OTA Timer setup
│   ├── setup_rpi.sh                             # Automated apt + pip + OTA dependency installer for Raspberry Pi OS
│   └── test_deps.py                             # 2-second environment & library diagnostic script
│
├── Documentation_and_References/                # Project Documentation & Changelog
│   ├── README.md                                # Detailed Project Overview (This file)
│   └── REVISION.md                              # Comprehensive Build & Version History
│
├── .gitignore                                   # Git exclusions for large datasets and caches
└── README.md                                    # Root Repository Documentation
```

---

## 🚀 Quick Start

### 1. Windows / PC
```bash
cd MobileV4
pip install -r requirements.txt
python main.py
```
Or double-click [`MobileV4/run_agrilens_py313.bat`](../MobileV4/run_agrilens_py313.bat).

### 2. Raspberry Pi 5
Refer to [`AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md`](../AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md):
```bash
cd ~/AGRILENS_RaspberryPi
chmod +x setup_rpi.sh run_agrilens.sh
./setup_rpi.sh
python3 test_deps.py
./run_agrilens.sh
```

---

## 🔒 Admin Access & Calibration

Access the Admin panel via the **`ADMIN`** button in the top-right corner of the kiosk:
- **Default PIN:** `AGRILENS`
- **Admin Capabilities:**
  - **AI Diagnostic Calibration Sliders:** Adjust Confidence Threshold ($30\% - 95\%$), OOD Ambiguity Margin ($10\% - 60\%$), Neural Logit Energy Gate ($1.00 - 6.50$), and Sharpness Quality Gate ($20 - 120$) with automatic persistence.
  - **Camera Control Panel (`📷 CAMERA CONTROL PANEL`):** Live camera preview, manual focus sharpness bar, neon Focus Peaking, Mirror/Flip toggles, USB Auto-Exposure/Auto-WB toggles, and 6 real-time ISP sliders (Contrast, Brightness, Saturation, Sharpness, White Balance, Macro Digital Zoom).
  - **Hardware Management:** Scan and reconnect USB webcams on the fly (`🔍 DETECT WEBCAM`) or fall back automatically to `PICK FROM FILE`.
  - **System Control:** Safely shut down the kiosk application (`✕ CLOSE APPLICATION`).

---

## 📜 Revision & Build Tracking

For a detailed history of all builds, architectural migrations, and changelogs, please refer to [`REVISION.md`](REVISION.md).

---

## 📄 License & Disclaimer

*Agricultural advice provided by this software is for advisory guidance only. Always consult local agricultural extension officers before applying chemical treatments.*
