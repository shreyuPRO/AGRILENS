# 📋 AGRILENS — Build Revision & Version History

This document provides a comprehensive build log and changelog for the **AGRILENS** AI Plant Health & Disease Diagnosis Kiosk system.

---

## 📌 Current Build Information

| Attribute | Specification |
| :--- | :--- |
| **Current Version** | **`v4.9.4` (Production Release)** |
| **Last Build Date** | **`2026-11-15 17:35 IST` (November 15, 2026)** |
| **Build Identifier** | `BUILD-20261115-1735-V494` |
| **Vision Backbone** | MobileNetV4-Conv-Small (`mobilenetv4_conv_small`) Universal Inverted Bottleneck (UIB) in ONNX format |
| **Model Weights** | Single-file `agrilens.onnx` (`10,068,009 bytes` / `~10.07 MB`, all weights embedded) |
| **Supported Classes** | **24 Classes** across **4 Crops** (`Apple`, `Mango`, `Potato`, `Tomato`) trained on 23,893 images |
| **Runtime Target** | Python 3.10 – 3.13+ (Tested on Windows 11 & Raspberry Pi OS 64-bit Bookworm) |
| **Target Hardware** | Raspberry Pi 5 (8GB) or PC + 7" Waveshare Capacitive Touch Display (1024×600) + USB Webcam |
| **Academic Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |

---

## 🏷️ Version Summary & Evolution

| Version | Release Date | Primary Engine | Classes | Model Size | Key Highlights |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`v4.9.4`** | **2026-11-15 17:35 IST** | **MobileNetV4 ONNX** | **24 Classes** | **~10.07 MB** | **Screensaver Inactivity Timeout Extended from 30 Seconds to 3 Minutes (`INACTIVITY_TIMEOUT_SECONDS = 180.0`)** |
| `v4.9.3` | 2026-11-15 17:12 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | World-Class Touch UI/UX Redesign: Unified Top Control Bar (`🌱 CROP`, `📷 MODE`, `🌐 हिंदी / EN`, `⚙ ADMIN`), Larger `52px` Action Buttons (`📸 CAPTURE LEAF`, `🔍 DIAGNOSE LEAF`), Card-Framed Farmer Recommendations & Enhanced Typography |
| `v4.9.2` | 2026-11-15 14:36 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Bilingual Main Screen Toggle (`🌐 हिंदी / EN`) — Full Hindi & English Support for Instructions, Buttons, Crop/Disease Names, Quality AI, and Farmer Recommendations |
| `v4.9.1` | 2026-11-15 14:27 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Remote Over-The-Air (OTA) Trained Model Updates (`agrilens.onnx` via `MODEL_SHA256` Zero-Overhead Fingerprint Check) |
| `v4.9.0` | 2026-11-15 14:08 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Full-Screen Logo Screensaver Overlay (Deactivated on Touch/Click), Clean `AGRILENS` Top Title, and Version Display in Bottom Status Bar (`AGRILENS v4.9.0`) |
| `v4.8.6` | 2026-11-15 14:01 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Instant GUI Window Launch (`<0.2s`), Windows Space-Safe Restart (`subprocess.Popen`), and Boot OTA Guard (`remote_tuple > local_tuple` on `silent_boot`) |
| `v4.8.5` | 2026-11-15 13:45 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Fixed GitHub Email Privacy Protection (`GH007` Noreply Address) & Sanitized `push_ota_update.bat` Batch Script — Published Live to GitHub (`origin/main`) |
| `v4.8.4` | 2026-11-15 13:18 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Event-Driven Immediate OTA Updates Only on Reboot/Startup (`silent_boot=True` + `agrilens-ota.service`) and Manual Admin Trigger (`☁ OTA UPDATE`), Removing the 15-Minute Periodic Timer |
| `v4.8.3` | 2026-11-15 13:07 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Per-File SHA-256 Asset & Logo Verification (`logos/`, `labels.txt`, scripts) when `remote >= local`, Plus Automatic Legacy `assets/` Cleanup on Raspberry Pi |
| `v4.8.2` | 2026-11-15 12:36 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Strict Anti-Downgrade Version Guard across OTA Updater (`main.py` & `ota_update.sh`) and USB-to-Home Auto-Sync (`ensure_rpi_autostart`) — Never Allows Updating to Older Versions |
| `v4.8.1` | 2026-11-15 12:10 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Top-Bar & Startup Splash Version Display (`AGRILENS v4.8.1`), Auto-Terminate Previous Running Instance on Launch, Auto-Sync USB Pendrive to `~/AGRILENS_RaspberryPi` on RPi |
| `v4.8.0` | 2026-11-15 11:56 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Over-The-Air (OTA) GitHub Software Updater (`☁ OTA UPDATE`), Raspberry Pi Remote Internet & Auto-OTA Timer (`setup_remote_ota.sh`, `ota_update.sh`), Updated Clean AGRILENS Logo, Consolidated Exclusive `logos/` Folder (`assets/` Removed) |
| `v4.7.0` | 2026-11-14 12:54 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Dedicated `logos/` Folder, 5-Second Startup Splash Logo in Image Window, 30-Second Inactivity Standby (Camera Auto-Off + Logo Display), Touch-Screen Wake to Live Mode |
| `v4.6.0` | 2026-11-14 12:45 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Live Mode vs. File Mode Dropdown Selector (`MODE: LIVE MODE ▾` / `MODE: FILE MODE ▾`), Default Live Mode with Auto File Mode Fallback when No Camera is Connected, Direct Sample File Browser |
| `v4.5.0` | 2026-11-14 12:26 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Direct 1-Tap Admin Entry (Password Disabled), Mobile Phone Screen De-Moiré & Anti-Glare Engine, 14% Bezel-Excluding Default Crop Inset, Mobile-Calibrated Thresholds |
| `v4.4.0` | 2026-11-14 11:53 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | Interactive 8-Handle Manual Leaf Cropper on Canvas (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`), Diagnose Strictly on Cropped Area |
| `v4.3.0` | 2026-11-14 11:28 IST | MobileNetV4 ONNX | 24 Classes | ~10.07 MB | 24-Class Retrained Model (Apple, Mango, Potato, Tomato), Training-Aligned Inference, Camera Control & ISP Panel, File Mode Fallback (`diagnosis_samples/`), Full-FoV 4:3 Viewport, Standalone RPi Package |
| `v4.2.0` | 2026-11-01 07:12 IST | MobileNetV4 ONNX | 17 Classes | ~10.03 MB | Dark Foliage Theme, Rounded Pill Buttons, GEA Official Logo, Admin Parameter Sliders & Tooltips, Config Persistence, Async Non-Blocking Startup |
| `v4.1.0` | 2026-10-31 21:45 IST | MobileNetV4 ONNX | 17 Classes | ~10.03 MB | Negative Class Gating (`Other_Plant_or_Background`), 1-Click Colab Retraining Notebook, OOD Margin & Logit Thresholding |
| `v4.0.0` | 2026-10-30 18:30 IST | MobileNetV4 ONNX | 17 Classes | ~10.03 MB | Migration from V2 to V4, Touch-optimized `[CAPTURE]` / `[DIAGNOSE]` workflow, Leaf Image Quality AI (Sharpness, Glare, Foliage Coverage) |
| `v2.0.0` | 2026-10-25 14:00 IST | MobileNetV2 Keras | 15 Classes | ~54.00 MB | Legacy baseline prototype using TensorFlow/Keras on PlantVillage dataset |

---

## 📜 Detailed Changelog by Build

### [v4.9.4] — 2026-11-15 17:35 IST
#### ✨ Changed
1. **Screensaver Activates Only After 3 Minutes of Inactivity**:
   - Increased `INACTIVITY_TIMEOUT_SECONDS` from `30.0` to `180.0` so the full-screen logo screensaver (and camera power-off) only triggers after 3 minutes without any touch, click, or key press.

---

### [v4.9.3] — 2026-11-15 17:12 IST
#### ✨ Added & Enhanced
1. **Unified Top Navigation & Selection Bar (`_build_top_bar`)**:
   - Increased the top navigation bar height (`self.TOP_H = self.px(60)`) with a crisp dark-foliage border.
   - Grouped all 4 top selection buttons together in a single, evenly-spaced horizontal control cluster (`self.top_btn_bar`) between the `AGRILENS` title on the left and the Gundecha Education Academy logo on the right:
     1. **`🌱 CROP: AUTO (ALL)`** / **`🌱 फसल: ऑटो (सभी)`** (`192 × 44 px`)
     2. **`📷 MODE: LIVE ▾`** / **`📷 मोड: लाइव ▾`** (`176 × 44 px`)
     3. **`🌐 हिंदी / EN`** / **`🌐 भाषा: हिंदी`** (`142 × 44 px`)
     4. **`⚙ ADMIN`** (`114 × 44 px`)
   - Updated `toggle_mode_dropdown()` to dynamically align the mode dropdown menu directly beneath the repositioned `mode_btn`.
2. **Larger Action Buttons & Enhanced Readability (`_build_body`, `_build_plant_picker`)**:
   - Increased bottom action buttons (`📸  CAPTURE LEAF` / `🔍  DIAGNOSE LEAF`) to `52px` height and `size=13` bold font, and crop picker tiles to `250 × 66 px` (`size=12`).
   - Upgraded typography across the Status Banner (`13pt bold`), Crop Mode (`11pt bold`), Disease Name (`13pt bold`), Confidence Bar (`22px` height, `10pt bold`), Quality AI bar (`10pt bold`), and 4-step farmer recommendation cards (`10pt` inside bordered `CARD` containers).

---

### [v4.9.2] — 2026-11-15 14:36 IST
#### ✨ Added & Enhanced
1. **Bilingual Main Screen Toggle (`🌐 हिंदी / EN`)**:
   - Added a 1-tap **`🌐 हिंदी / EN`** (when in English) / **`🌐 भाषा: हिंदी`** (when in Hindi) button in the top bar of the Main Screen (`_build_top_bar`, `toggle_language`, `_refresh_language_ui`), keeping the Admin Console and Camera Control Panel in English.
   - Translates all farmer-facing instructions, buttons (`फोटो लें`, `पुनः फोटो लें`, `फाइल से चुनें`, `पत्ती जांचें`, `अभी जांचें`), mode selector dropdown (`मोड: लाइव कैमरा ▾` / `मोड: फाइल मोड ▾`), crop picker (`फसल चुनें (ऑटो)` / `सेब (APPLE)`, `आम (MANGO)`, `आलू (POTATO)`, `टमाटर (TOMATO)`), Leaf Quality AI status messages (`LeafQualityAI.assess(..., lang=self.lang)`), confidence bar labels, 24 crop/disease names (`translate_crop_hi`, `translate_cond_hi`), 4-step farmer recommendations (`RECOMMENDATIONS_HI`, `UNSURE_STEPS_HI`, `OOD_STEPS_HI`), and disclaimer (`DISCLAIMER_HI`).
   - Dynamically re-renders active captured frames and diagnosis outcomes immediately when toggled between Hindi and English, and persists `"language"` in `kiosk_config.json`.

---

### [v4.9.1] — 2026-11-15 14:27 IST
#### ✨ Added & Enhanced
1. **Remote Over-The-Air (OTA) Trained AI Model Updates (`agrilens.onnx` & `MODEL_SHA256`)**:
   - Embedded `MODEL_SHA256` inside `main.py` (automatically updated by `train_mobilenetv4.py` and `push_ota_update.bat` whenever `agrilens.onnx` is retrained or published).
   - During OTA checks (`_trigger_ota_update` in `main.py` and `ota_update.sh`), the kiosk compares its local `agrilens.onnx` SHA-256 fingerprint against `MODEL_SHA256` from GitHub's `main.py`.
   - If the model has not changed, `0 bytes` of extra model bandwidth are used. If a newly trained `agrilens.onnx` (`~10.07 MB`) was pushed to GitHub, the kiosk automatically downloads `agrilens.onnx`, verifies its SHA-256 integrity, updates `labels.txt`, and restarts with the new model.

---

### [v4.9.0] — 2026-11-15 14:08 IST
#### ✨ Added & Enhanced
1. **Full-Screen AGRILENS Logo Screensaver Overlay (`_build_screensaver_overlay` & `_show_fullscreen_screensaver`)**:
   - Removed the AGRILENS logo from inside the Camera viewport (`self.canvas`) and replaced it with a **full-screen screensaver overlay** (`self.screensaver_frame`, `self.W × self.H`) covering the entire screen.
   - Displays on startup (5s or deactivated immediately on touch/click) and after 30 seconds of inactivity (`INACTIVITY_TIMEOUT_SECONDS = 30.0`, turning off the camera).
   - Touching or clicking anywhere on the screen immediately deactivates the full-screen screensaver and wakes the camera into Live Mode.
2. **Clean Main Page Title & Version in Bottom Status Text**:
   - Restored the top-bar brand title to `AGRILENS` (without the version number) and placed `AGRILENS v4.9.0` in the bottom status text (`self.stats_lbl`).

---

### [v4.8.6] — 2026-11-15 14:01 IST
#### ✨ Fixed & Enhanced
1. **Instant Non-Blocking GUI Launch & Space-Safe Restart (`_restart_application`)**:
   - Removed synchronous `_auto_install_package("cv2", "opencv-python")` before `tk.Tk()` so the window opens in `<0.2s` even if `opencv-python` is not installed on a PC.
   - Replaced `os.execv` in `_restart_application()` with `subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=APP_BASE_DIR)` so Python installations in paths containing spaces (`C:\Users\Faiyaz Engineer\...`) restart cleanly on Windows.
   - Updated `silent_boot=True` OTA check to only trigger a restart when `remote_tuple > local_tuple`.

---

### [v4.8.5] — 2026-11-15 13:45 IST
#### ✨ Fixed & Enhanced
1. **GitHub Email Privacy (`GH007`) & `push_ota_update.bat` Fix**:
   - Configured repository Git author email to `35885868+faiyaze04@users.noreply.github.com` to comply with GitHub's `GH007` private email protection.
   - Removed unescaped `&` and `>` characters from `push_ota_update.bat` (`echo` and `title` lines) and pushed `v4.8.5` live to `origin/main` on GitHub.

---

### [v4.8.4] — 2026-11-15 13:18 IST
#### ✨ Added & Enhanced
1. **Immediate Event-Driven OTA Updates (On Reboot/Startup + Manual Admin Button Only)**:
   - Removed the 15-minute repeating `agrilens-ota.timer` so the kiosk is never interrupted mid-demonstration by a periodic timer.
   - **Immediate On Reboot / Startup**: `_start_async_bootstrap()` in `main.py` immediately launches `_trigger_ota_update(silent_boot=True)` in a non-blocking background thread (with automatic brief Wi-Fi readiness retries on boot), and `setup_remote_ota.sh` configures `agrilens-ota.service` (`WantedBy=multi-user.target`, `After=network-online.target`) + `run_agrilens.sh` to check GitHub once on reboot. If an update is found, it applies and restarts immediately (`150 ms`).
   - **Immediate Manual OTA via Admin**: Tapping **`ADMIN`** $\rightarrow$ **`☁ OTA UPDATE (INTERNET)`** immediately checks GitHub, downloads any newer version (`remote_tuple >= local_tuple` with changed `SHA-256`), and restarts immediately (`150 ms`).

---

### [v4.8.3] — 2026-11-15 13:07 IST
#### ✨ Added & Enhanced
1. **Per-File SHA-256 Verification for Logos, Labels & Scripts (`remote_tuple >= local_tuple`)**:
   - While strictly blocking downgrades (`remote_tuple < local_tuple`), both `_trigger_ota_update()` in `main.py` and `ota_update.sh` now inspect the `SHA-256` hash of every companion file (`logos/agrilens_logo.jpg`, `logos/gundecha_logo.png`, `labels.txt`, `HOW_TO_RUN_ON_RASPBERRY_PI.md`, `setup_rpi.sh`, `run_agrilens.sh`, `ota_update.sh`, `setup_remote_ota.sh`) whenever `remote_tuple >= local_tuple`. Even if a logo or label file is updated within the same version or a newer version, any file with a changed SHA-256 hash is automatically downloaded and applied.
2. **Automatic Cleanup of Legacy `assets/` Directory on Raspberry Pi**:
   - Both USB-to-Home auto-sync (`ensure_rpi_autostart`) and OTA update remove any leftover `~/AGRILENS_RaspberryPi/assets` folder on the Raspberry Pi SD card so only `logos/` exists.

---

### [v4.8.2] — 2026-11-15 12:36 IST
#### ✨ Added & Enhanced
1. **Strict Anti-Downgrade Version Protection (`_parse_version_tuple` & `_extract_version_from_code`)**:
   - Added semantic version tuple parsing across `main.py` (`_trigger_ota_update` and `ensure_rpi_autostart`) and `ota_update.sh`.
   - **OTA Anti-Downgrade Guard**: Before downloading or applying any OTA files from GitHub, both the in-app **`☁ OTA UPDATE (INTERNET)`** button and the background `ota_update.sh` script parse `APP_VERSION` from the remote `main.py` and compare it against the local installed version. If `remote_version < local_version`, the downgrade is strictly blocked (`"OTA BLOCKED: Remote vX.Y.Z is older than installed vA.B.C"`). Updates are only applied when `remote_version > local_version`.
   - **USB-to-Home Anti-Downgrade Guard**: When launched from a USB drive (`/media/...` or `/mnt/...`) on Raspberry Pi, `ensure_rpi_autostart()` checks the installed version in `~/AGRILENS_RaspberryPi/main.py` and refuses to overwrite a newer installed version with an older USB copy.

---

### [v4.8.1] — 2026-11-15 12:10 IST
#### ✨ Added & Enhanced
1. **Top-Bar, Startup Splash & Immediate Stats Bar Version Display (`v4.8.1`)**:
   - Displayed `AGRILENS v4.8.1` directly in the top header bar, on the 5-second startup splash badge (`AGRILENS v4.8.1 — STARTING IN 5s...`), and immediately in the bottom status bar from startup.
2. **Auto-Termination of Older Running Instances & USB-to-Home Auto-Sync on Raspberry Pi**:
   - Added `_kill_previous_instances()` at startup so launching a new version automatically closes any older `main.py` instance still running in RAM (preventing an old `v4.7.0` window from staying open or locking `/dev/video0`).
   - Updated `ensure_rpi_autostart()` so if `main.py` is launched from a USB pendrive (`/media/...` or `/mnt/...`), it automatically syncs the updated files into `~/AGRILENS_RaspberryPi` on the Raspberry Pi SD card.

---

### [v4.8.0] — 2026-11-15 11:56 IST
#### ✨ Added & Enhanced
1. **Over-The-Air (OTA) Software Update Engine & Raspberry Pi Remote Internet Access**:
   - Added **`☁ OTA UPDATE (INTERNET)`** inside the Admin Console (`_trigger_ota_update`) that pulls the latest `main.py`, `labels.txt`, `logos/`, and scripts directly over HTTPS from GitHub (`https://raw.githubusercontent.com/faiyaze04/AGRILENS/main/AGRILENS_RaspberryPi/...`), verifies Python syntax via `py_compile`, and automatically restarts the kiosk.
   - Created `AGRILENS_RaspberryPi/ota_update.sh` for CLI/background OTA updates and automatic kiosk restart on `DISPLAY=:0`.
   - Created `AGRILENS_RaspberryPi/setup_remote_ota.sh` (integrated into `setup_rpi.sh`) to provision **Raspberry Pi Connect (`rpi-connect`)** for browser-based remote desktop/shell over the internet, **OpenSSH (`ssh`)**, and a systemd **`agrilens-ota.timer`** that checks GitHub on boot and every 15 minutes.
2. **Updated Clean AGRILENS Splash Logo & Removed Legacy `assets/` Folder**:
   - Updated `logos/agrilens_logo.jpg` across all folders with the new centered AGRILENS EXPISCOR 2026 artwork.
   - Removed the duplicate `assets/` folder completely; `find_logo_file()` now loads all logos exclusively from `logos/`.

---

### [v4.7.0] — 2026-11-14 12:54 IST
#### ✨ Added & Enhanced
1. **Dedicated `logos/` Folder & `find_logo_file()` Resolver**:
   - Created `logos/` across `MobileV4/logos/` and `AGRILENS_RaspberryPi/logos/` storing `agrilens_logo.jpg` (AGRILENS EXPISCOR 2026 banner) and `gundecha_logo.png` (Gundecha Education Academy crest).
   - Updated all logo loaders (`_load_splash_logo` and `_build_school_logo`) to resolve through `find_logo_file()`.
2. **5-Second Startup Logo Display (`STARTUP_LOGO_SECONDS = 5.0`)**:
   - Displays `logos/agrilens_logo.jpg` inside the main image window for **5 seconds** on startup with a live countdown badge (`AGRILENS — STARTING IN Xs...`) while the ONNX engine and webcam initialize in the background.
3. **30-Second Inactivity Standby & Touch-to-Wake (`INACTIVITY_TIMEOUT_SECONDS = 30.0`)**:
   - After **30 seconds of inactivity**, automatically displays `logos/agrilens_logo.jpg` in the image box and turns off the USB camera hardware (`self.camera.close()`).
   - Touching anywhere on the screen (`_on_global_user_activity` -> `_wake_from_standby`) turns the camera back on (prioritizing `last_working_port` for fast wake-up) and switches back to **Live Mode**.

---

### [v4.6.0] — 2026-11-14 12:45 IST
#### ✨ Added & Enhanced
1. **Top-Bar Mode Dropdown (`MODE: LIVE MODE ▾` vs. `MODE: FILE MODE ▾`)**:
   - Added a touch-friendly dropdown selector (`self.mode_btn` and `self.mode_dropdown`) in the top bar right beside `SELECT CROP (AUTO)`.
   - Allows switching between **Live Mode (Camera)** and **File Mode (Sample Files)** at any time, even when a USB webcam is connected.
2. **Smart Default Mode Selection**:
   - **Default Mode:** Defaults to **Live Mode** whenever a camera is connected.
   - **No-Camera Auto-Fallback:** Automatically defaults to **File Mode** if no camera is connected at startup or if a camera disconnects mid-session, and prevents switching into an empty Live Mode when no camera is attached.
3. **Sample File Browser in File Mode**:
   - Selecting **File Mode** from the dropdown switches the kiosk to File Mode and opens the file browser directly inside the default sample directory (`diagnosis_samples/` or `diagnosis_samples/<SelectedCrop>`).

---

### [v4.5.0] — 2026-11-14 12:26 IST
#### ✨ Added & Enhanced
1. **Direct 1-Tap Admin Access**:
   - Disabled the Admin PIN/password lock screen so tapping **`ADMIN`** opens the Admin Console and Camera Control Panel immediately.
2. **Mobile Phone Screen Optical Alignment (`_enhance_mobile_screen` & Dual-Stream Ensemble)**:
   - Added `3×3` Gaussian anti-aliasing (`sigma=0.65`) to suppress RGB subpixel Moiré patterns when photographing leaves displayed on mobile phones.
   - Added room-reflection black-floor subtraction and blue OLED/LCD backlight neutralization while preserving the leaf's natural `R:G` ratio.
   - Evaluates both Natural RGB and Mobile-Screen-Restored RGB streams across the user's cropped leaf selection.
   - Pre-inset the initial manual crop box by 14% to automatically exclude mobile phone bezels and fingers, and calibrated default thresholds (`confidence_threshold: 0.40`, `ood_margin: 0.12`, `ood_logit: 1.40`, `sharpness_min: 25.0`) for mobile screen testing.

---

### [v4.4.0] — 2026-11-14 11:53 IST
#### ✨ Added & Enhanced
1. **Interactive 8-Handle Manual Leaf Cropper (`_init_crop_selection`, `_get_cropped_leaf_image`)**:
   - Added adjustable 8-handle crop selection overlay (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w` grab handles, drag-to-pan, draw-new-box, double-tap for full image, rule-of-thirds grid, and dimmed outer scrim) on captured or file-loaded leaf images.
   - Pressing **`DIAGNOSE NOW`** crops and evaluates strictly the user-selected leaf region.

---

### [v4.3.0] — 2026-11-14 11:28 IST
#### ✨ Added & Enhanced
1. **24-Class Consolidated Dataset & Single-File MobileNetV4 Retraining (`cd7d109`, `f10f4a3`)**:
   - Expanded diagnostic catalog to **24 classes** across **4 primary crops** (`Apple`: 3 classes, `Mango`: 8 classes, `Potato`: 3 classes, `Tomato`: 10 classes) totaling **23,893 images** from `MobileV4/datasets`.
   - Trained `mobilenetv4_conv_small` for 15 epochs with mixed precision (AMP), Cosine Annealing LR schedule, label smoothing ($0.06$), and screen-resilient color/contrast jitter (`97.28%` holdout validation accuracy).
   - Exported model as a **single self-contained `agrilens.onnx` file** (`10,068,009 bytes`), eliminating external `agrilens.onnx.data` tensor files for simpler deployment.
2. **Interactive 8-Handle Manual Leaf Cropper & Training-Aligned Inference (`_init_crop_selection`, `_get_cropped_leaf_image`, `Classifier.predict`)**:
   - Added interactive 8-handle crop selection overlay (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w` grab handles, drag-to-move, draw-new-box, double-tap to select full image, rule-of-thirds guide grid, and dimmed outer scrim) when a frame is captured or loaded from file.
   - Pressing **`DIAGNOSE NOW`** crops the exact user-selected leaf region (`_get_cropped_leaf_image()`) and runs both `LeafQualityAI.assess()` and `Classifier.predict()` strictly on the cropped area.
   - Removed automated pre-segmentation (`LeafOutlineSegmenter`) and artificial color shifting (`_dehaze_screen_glare`) so the model sees natural RGB pixels matching `train_mobilenetv4.py`.
3. **Camera Control Panel & Real-Time ISP Pipeline (`_build_camera_panel`, `_apply_isp`)**:
   - Added dedicated **`📷 CAMERA CONTROL PANEL`** screen accessible from the Admin Console:
     - **Manual Focus Sharpness Meter & Focus Peaking:** Real-time Laplacian focus bar ($0-100\%$) and optional neon-green edge highlight (`PEAKING: ON`) for tuning manual focus lenses.
     - **6 Real-Time ISP Sliders:** Contrast ($50-200\%$), Brightness Offset ($-50\%$ to $+50\%$), Color Saturation ($0-200\%$), Sharpness & Vein Crisping ($50-250\%$), White Balance Warmth ($-50$ Cool to $+50$ Warm), and Macro Digital Zoom ($1.00\times - 2.00\times$).
     - **Orientation & UVC Hardware Toggles:** `MIRROR H`, `FLIP 180°`, `USB AUTO-EXP` (with 50Hz power-line anti-flicker via `v4l2-ctl`), and `USB AUTO-WB`.
4. **File Mode Fallback & Curated `diagnosis_samples/` Catalog (`c99e730`)**:
   - When no USB camera is detected, the kiosk automatically activates **File Mode** (`PICK FROM FILE`), allowing full offline testing and demonstration using 24 curated reference samples in `diagnosis_samples/{Apple,Mango,Potato,Tomato}`.
5. **Full-FoV 4:3 Camera Viewport (`_render_full_fov`, `c99e730`)**:
   - Allocated 56.5% width to the left camera panel and matched the 4:3 aspect ratio of the 640×480 sensor so 100% of the camera field of view is visible without cropping on the 1024×600 Waveshare 7" screen.
6. **Standalone Raspberry Pi Deployment Package (`AGRILENS_RaspberryPi/`)**:
   - Created a self-contained deployment directory with `setup_rpi.sh`, `run_agrilens.sh`, `test_deps.py`, `HOW_TO_RUN_ON_RASPBERRY_PI.md`, resilient `ImageTk` PNG fallback, automatic pip package installer (`_auto_install_package`), and zero-delay desktop autostart registration (`ensure_rpi_autostart`).

---

### [v4.2.0] — 2026-11-01 07:12:32 IST
#### ✨ Added & Enhanced
1. **Dark Foliage Obsidian Color Palette**:
   - Replaced generic grey interface with an agricultural dark-mode aesthetic (`#08100a`, `#0e1a12`, `#15261a`, `#213d29`, `#16a34a`, `#22c55e`, `#ef4444`).
2. **High-Fidelity Rounded Pill Buttons (`RoundedButton`)**:
   - Built a bespoke anti-aliased Tkinter canvas component (`RoundedButton(tk.Canvas)`) with 3x supersampling and Pillow Lanczos downscaling.
3. **Official Gundecha Education Academy Logo Badge**:
   - Embedded official GEA institution crest (`assets/gundecha_logo.png`) on the top-right header with clickable portal redirection to [gundechaedu.org](https://www.gundechaedu.org/) and hover tooltip.
4. **Admin Console Calibration Parameter Sliders & `(i)` Tooltips**:
   - Integrated 4 interactive sliders within the PIN-protected Admin panel (Confidence Threshold, OOD Margin, OOD Logit Gate, Leaf Sharpness Min) with mouse-over/touch `(i)` tooltips.
5. **Persistent Configuration (`kiosk_config.json`)**:
   - Live calibration adjustments are serialized to `kiosk_config.json` and restored automatically on next kiosk boot.
6. **Robust Webcam Detection Engine (DirectShow & V4L2 Cascading)**:
   - Platform-prioritized backend cascading (`CAP_DSHOW` -> `CAP_ANY` on Windows; `CAP_V4L2` -> `CAP_ANY` on Linux/Raspberry Pi) with friendly device name discovery.
7. **Instantaneous Non-Blocking Async Startup**:
   - Decoupled ONNX model loading and camera hardware probing from the Tkinter GUI thread into a background worker with thread-safe `queue.Queue` synchronization.

---

### [v4.1.0] — 2026-10-31 21:45:00 IST
#### ✨ Added & Enhanced
1. **Out-of-Distribution (OOD) Protection**:
   - Implemented dual-stage OOD gating: Softmax probability thresholding combined with top-1/top-2 logit margin and raw logit energy checks.
2. **1-Click Google Colab Retraining Pipeline (`Train_AGRILENS_MobileNetV4.ipynb`)**:
   - Jupyter notebook for automated retraining on Google Colab with free T4 GPU (~15 minutes).
3. **Automated Dataset Consolidation (`consolidate_datasets.py`)**:
   - Automated folder consolidation script standardizing crop image folders into a unified training hierarchy.

---

### [v4.0.0] — 2026-10-30 18:30:00 IST
#### ✨ Added & Enhanced
1. **MobileNetV4 Universal Inverted Bottleneck (UIB) Architecture**:
   - Upgraded from legacy MobileNetV2 to MobileNetV4 ONNX, reducing model weight footprint from 54MB to ~10MB while slashing CPU inference latency.
2. **Two-Stage Touch Workflow**:
   - Separated inspection into `[CAPTURE LEAF]` and `[DIAGNOSE NOW]`.
3. **Leaf Image Quality AI Validator**:
   - Real-time pre-inference analysis of spatial Laplacian focus sharpness, luminance exposure, and Excess Green foliage coverage.

---

### [v2.0.0] — 2026-10-25 14:00:00 IST
#### 📦 Baseline Release
- Initial prototype developed using TensorFlow/Keras MobileNetV2 (`agri_lens_plant_disease_20epoch.keras`) on 15 classes from the PlantVillage dataset.

---

## 📂 Active Production File Manifest (v4.5.0)

```text
AGRILENS/
├── MobileV4/                                    # PC & Development Touch Kiosk Application
│   ├── assets/
│   │   └── gundecha_logo.png                    # Official Gundecha Education Academy crest
│   ├── diagnosis_samples/                       # 24 Reference Leaf Images (Apple, Mango, Potato, Tomato)
│   ├── Training_Scripts/
│   │   ├── consolidate_datasets.py              # 24-Class Dataset Consolidation & Verification Pipeline
│   │   ├── train_mobilenetv4.py                 # Local PyTorch MobileNetV4 Trainer & Single-File ONNX Exporter
│   │   └── Train_AGRILENS_MobileNetV4.ipynb     # 1-Click Google Colab T4 GPU Training Notebook
│   ├── agrilens.onnx                            # Single-File MobileNetV4 ONNX Model (10,068,009 bytes)
│   ├── kiosk_config.json                        # Saved Admin & Camera ISP Calibration Parameters
│   ├── labels.txt                               # 24-Class Model Labels
│   ├── main.py                                  # Touch Kiosk GUI Application
│   ├── requirements.txt                         # Python Dependencies
│   └── run_agrilens_py313.bat                   # Windows Python 3.13 Launcher
│
├── AGRILENS_RaspberryPi/                        # Standalone Raspberry Pi 5 Deployment Package
│   ├── assets/
│   │   └── gundecha_logo.png                    # Official Gundecha Education Academy crest
│   ├── diagnosis_samples/                       # 24 Reference Leaf Images (Apple, Mango, Potato, Tomato)
│   ├── agrilens.onnx                            # Single-File MobileNetV4 ONNX Model (10,068,009 bytes)
│   ├── HOW_TO_RUN_ON_RASPBERRY_PI.md            # Raspberry Pi 5 & Thonny Deployment Guide
│   ├── kiosk_config.json                        # Saved Admin & Camera ISP Calibration Parameters
│   ├── labels.txt                               # 24-Class Model Labels
│   ├── main.py                                  # Touch Kiosk GUI Application
│   ├── requirements.txt                         # Python Dependencies
│   ├── run_agrilens.sh                          # Raspberry Pi Shell Launcher
│   ├── setup_rpi.sh                             # Automated Raspberry Pi OS Dependency Installer
│   └── test_deps.py                             # Dependency & Environment Verification Script
│
├── Documentation_and_References/
│   ├── README.md                                # Detailed Project Overview
│   └── REVISION.md                              # Global Project Revision Log (This file)
│
├── .gitignore                                   # Git Ignore Rules
└── README.md                                    # Root Repository Documentation
```
