#!/usr/bin/env python3
"""Apply the AGRILENS 5.0.0 changes to application/main.py. Every replacement must match exactly once, otherwise nothing is written.
Changes (all other behaviour is unchanged):
  1. version identifiers: APP_VERSION 5.0.0, MODEL_ID/MODEL_VERSION/DATASET_VERSION/OTA_RELEASE_ID; truthful header and tooltip
  2. model-specific rejection-gate calibration (MODEL_CALIBRATION_*), applied only when the loaded model file matches MODEL_SHA256;
     saved thresholds are honoured only if they were saved for the model now loaded (fixes stale ood_logit 6.0 after a model change)
  3. model/application compatibility check: model file SHA-256 computed at load; output width must equal the label count
  4. OTA safety (in-app updater): the downloaded main.py is compiled BEFORE the model is replaced; the files being replaced are copied to
     rollback/v<running version>/ first; rollback.sh added to the OTA file list
"""
import os
P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "application", "main.py")
s = open(P, encoding="utf-8").read(); orig = s


def rep(old, new):
    global s
    n = s.count(old)
    if n != 1: raise SystemExit(f"expected exactly one match, found {n}: {old[:80]!r}")
    s = s.replace(old, new)


rep('Model: MobileNetV4 (ONNX) - 98.31% Accuracy\n', 'Model: AGRILENS-MULTICROP (MobileNetV4-Conv-Small ONNX, 24 classes); see MODEL_* constants and models/ manifests\n')
rep('APP_VERSION = "4.9.4"\nBUILD_TIMESTAMP = "2026-11-15 17:35 IST"\nMODEL_SHA256 = "0b5bb7fb3916a7c1138f90cfc9abfdc130f06495a34282d474e52718b072ff80"\n',
    'APP_VERSION = "5.0.0"\nBUILD_TIMESTAMP = "UNSET"\nMODEL_SHA256 = "UNSET"\n'
    '# Model identity (independent of APP_VERSION). MODEL_SHA256 is verified against the model file by deployment/packaging/build_device_package.py.\n'
    'MODEL_ID = "AGRILENS-MULTICROP"\nMODEL_VERSION = "1.0.0"\nMODEL_NUM_CLASSES = 24\nDATASET_VERSION = "AGL-MULTICROP-MD 1.0.0"\nOTA_RELEASE_ID = "AGRILENS-5.0.0"\n'
    '# Rejection-gate calibration of the model above, set on validation data only (training/evaluation/). Used only when the loaded model matches MODEL_SHA256.\n'
    'MODEL_CALIBRATION_CONFIDENCE = 0.40\nMODEL_CALIBRATION_MARGIN = 0.12\nMODEL_CALIBRATION_OOD_LOGIT = 1.40\n')
rep('''def load_kiosk_config():
    cfg = dict(DEFAULT_CONFIG)''', '''THRESHOLD_KEYS = ("confidence_threshold", "ood_margin", "ood_logit")


def file_sha256(path):
    """SHA-256 of a file, or "" if it cannot be read."""
    try:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest().lower()
    except Exception:
        return ""


def resolve_gate_thresholds(cfg, model_sha256):
    """
    Chooses the rejection-gate thresholds for the model that is actually loaded.
    1. Thresholds saved in the kiosk configuration are used only if they were saved for this model (calibration_model_sha256 matches).
    2. Otherwise, if the loaded model is the release model (MODEL_SHA256), its embedded calibration is used.
    3. Otherwise (unrecognised model file) the generic code defaults are used.
    Returns (dict of the three thresholds, human-readable source).
    """
    sha = str(model_sha256 or "").lower()
    saved_for = str((cfg or {}).get("calibration_model_sha256", "") or "").lower()
    if sha and saved_for == sha and all(k in (cfg or {}) for k in THRESHOLD_KEYS):
        th = {k: float(cfg[k]) for k in THRESHOLD_KEYS}
        src = "saved settings for this model"
    elif sha and sha == str(MODEL_SHA256).lower():
        th = {"confidence_threshold": MODEL_CALIBRATION_CONFIDENCE, "ood_margin": MODEL_CALIBRATION_MARGIN, "ood_logit": MODEL_CALIBRATION_OOD_LOGIT}
        src = f"calibration of {MODEL_ID} {MODEL_VERSION}"
    else:
        th = {"confidence_threshold": CONFIDENCE_THRESHOLD, "ood_margin": OOD_MARGIN_THRESHOLD, "ood_logit": OOD_LOGIT_THRESHOLD}
        src = "generic defaults (model file not recognised)"
    th["confidence_threshold"] = _clamp_num(th["confidence_threshold"], CONFIDENCE_THRESHOLD, 0.30, 0.95)
    th["ood_margin"] = _clamp_num(th["ood_margin"], OOD_MARGIN_THRESHOLD, 0.10, 0.60)
    th["ood_logit"] = _clamp_num(th["ood_logit"], OOD_LOGIT_THRESHOLD, 1.00, 6.50)
    return th, src


def load_kiosk_config():
    cfg = dict(DEFAULT_CONFIG)''')
# classifier: model hash, output-width check, truthful mode string
rep('''        self.labels = self._load_labels()
        self.session = None''', '''        self.labels = self._load_labels()
        self.model_sha256 = file_sha256(self.model_path) if os.path.exists(self.model_path) else ""
        self.session = None''')
for _ in range(2):
    rep('''            self.mode = "ONNX (98.31%)"
            self.error_reason = ""''' if _ == 0 else '''                self.mode = "ONNX (98.31%)"
                self.error_reason = ""''', ('''            self.mode = self._mode_after_load()
            self.error_reason = ""''' if _ == 0 else '''                self.mode = self._mode_after_load()
                self.error_reason = ""'''))
rep('''    def _prep_tensor(self, rgb_img):''', '''    def _mode_after_load(self):
        """Verifies that the model output width matches the label list; returns the engine mode string (and disables inference on mismatch)."""
        try:
            n_out = self.session.get_outputs()[0].shape[-1]
            n_out = int(n_out) if isinstance(n_out, (int, float)) or str(n_out).isdigit() else None
        except Exception:
            n_out = None
        if n_out is not None and n_out != len(self.labels):
            self.session = None
            self.error_reason = f"model outputs {n_out} classes but labels.txt has {len(self.labels)}"
            return "DEMO"
        if self.model_sha256 and self.model_sha256 == str(MODEL_SHA256).lower():
            return f"ONNX {MODEL_ID} {MODEL_VERSION}"
        return "ONNX (unrecognised model file)"

    def _prep_tensor(self, rgb_img):''')
# mismatch must keep DEMO mode: the two assignments set error_reason "" after _mode_after_load(); guard that
s = s.replace('''            self.mode = self._mode_after_load()
            self.error_reason = ""''', '''            self.mode = self._mode_after_load()
            if self.mode != "DEMO":
                self.error_reason = ""''').replace('''                self.mode = self._mode_after_load()
                self.error_reason = ""''', '''                self.mode = self._mode_after_load()
                if self.mode != "DEMO":
                    self.error_reason = ""''')
# app: keep loaded config, resolve thresholds when the model is known
rep('''        cfg = load_kiosk_config()
        self.threshold = float(cfg.get("confidence_threshold", CONFIDENCE_THRESHOLD))''', '''        cfg = load_kiosk_config()
        self._loaded_cfg = dict(cfg)
        self.gate_source = "configuration (model not loaded yet)"
        self.threshold = float(cfg.get("confidence_threshold", CONFIDENCE_THRESHOLD))''')
rep('''    def _on_bootstrap_complete(self, classifier, parsed, crops, plants):
        self.classifier = classifier''', '''    def _on_bootstrap_complete(self, classifier, parsed, crops, plants):
        self.classifier = classifier
        th, self.gate_source = resolve_gate_thresholds(getattr(self, "_loaded_cfg", {}), getattr(classifier, "model_sha256", ""))
        self.threshold, self.ood_margin, self.ood_logit = th["confidence_threshold"], th["ood_margin"], th["ood_logit"]
        print(f"AGRILENS {APP_VERSION}: model {getattr(classifier, 'mode', '?')}; rejection gates from {self.gate_source}: "
              f"confidence {self.threshold:.2f}, margin {self.ood_margin:.2f}, logit {self.ood_logit:.2f}")''')
rep('''            "language": getattr(self, "lang", "EN"),
        }
        save_kiosk_config(cfg)''', '''            "language": getattr(self, "lang", "EN"),
            "calibration_model_sha256": getattr(getattr(self, "classifier", None), "model_sha256", "") or "",
        }
        save_kiosk_config(cfg)''')
rep('''        defaults = {
            "confidence_threshold": int(CONFIDENCE_THRESHOLD * 100),
            "ood_margin": int(OOD_MARGIN_THRESHOLD * 100),
            "ood_logit": int(OOD_LOGIT_THRESHOLD * 10),''', '''        th, _src = resolve_gate_thresholds({}, getattr(getattr(self, "classifier", None), "model_sha256", ""))
        defaults = {
            "confidence_threshold": int(round(th["confidence_threshold"] * 100)),
            "ood_margin": int(round(th["ood_margin"] * 100)),
            "ood_logit": int(round(th["ood_logit"] * 10)),''')
rep('''f"Version: v{APP_VERSION}\\nBuild: {BUILD_TIMESTAMP}\\nModel: MobileNetV4 ONNX (24 Classes)"''',
    '''f"Version: v{APP_VERSION} ({OTA_RELEASE_ID})\\nBuild: {BUILD_TIMESTAMP}\\nModel: {MODEL_ID} {MODEL_VERSION} (24 classes)\\nDataset: {DATASET_VERSION}"''')
# OTA safety in the in-app updater
rep('''                ("setup_remote_ota.sh", os.path.join(APP_BASE_DIR, "setup_remote_ota.sh")),
            ]''', '''                ("setup_remote_ota.sh", os.path.join(APP_BASE_DIR, "setup_remote_ota.sh")),
                ("rollback.sh", os.path.join(APP_BASE_DIR, "rollback.sh")),
            ]
            rollback_dir = os.path.join(APP_BASE_DIR, "rollback", f"v{APP_VERSION}")

            def backup_for_rollback(path):
                """Keeps a copy of the file of the running version before it is replaced (first copy wins)."""
                try:
                    if os.path.exists(path):
                        rel = os.path.relpath(path, APP_BASE_DIR)
                        dst = os.path.join(rollback_dir, rel)
                        if not os.path.exists(dst):
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.copy2(path, dst)
                except Exception:
                    pass''')
rep('''                    if rel_url == "main.py":
                        text_src = data.decode("utf-8", errors="replace")
                        remote_ver = _extract_version_from_code(text_src)''', '''                    if rel_url == "main.py":
                        # Compile the downloaded main.py BEFORE anything (including the model) is replaced
                        chk_path = os.path.join(APP_BASE_DIR, "main.py.ota_check")
                        with open(chk_path, "wb") as f_chk:
                            f_chk.write(data)
                        try:
                            py_compile.compile(chk_path, doraise=True)
                        finally:
                            try:
                                os.remove(chk_path)
                            except Exception:
                                pass
                        text_src = data.decode("utf-8", errors="replace")
                        remote_ver = _extract_version_from_code(text_src)''')
rep('''                                    m_tmp = model_dest + ".ota_tmp"
                                    with open(m_tmp, "wb") as f_mout:
                                        f_mout.write(m_data)
                                    os.replace(m_tmp, model_dest)
                                    updated_count += 1''', '''                                    m_tmp = model_dest + ".ota_tmp"
                                    with open(m_tmp, "wb") as f_mout:
                                        f_mout.write(m_data)
                                    backup_for_rollback(model_dest)
                                    os.replace(m_tmp, model_dest)
                                    updated_count += 1''')
rep('''                        if rel_url == "main.py":
                            py_compile.compile(tmp_path, doraise=True)
                        os.replace(tmp_path, dest_path)''', '''                        if rel_url == "main.py":
                            py_compile.compile(tmp_path, doraise=True)
                        backup_for_rollback(dest_path)
                        os.replace(tmp_path, dest_path)''')
assert s != orig
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s); print("patched", P)
