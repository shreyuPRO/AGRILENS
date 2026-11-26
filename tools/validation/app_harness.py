"""
AGRILENS test and diagnostics harness.

Loads the kiosk application file WITHOUT modifying it and exposes helpers that the tests and
the field-validation tools share:

  * load_app()      import the app module from AGRILENS_APP_PATH (default: the frozen legacy
                    AGRILENS_RaspberryPi/main.py). Bytecode writing is disabled so importing
                    never creates __pycache__ next to the application.
  * decide()        runs the application's real confidence / out-of-distribution decision code
                    (AgriLensApp._render_diagnosis) against a stand-in for the UI object and
                    reports the verdict. The decision logic is not re-implemented here.
  * PROFILES        the two threshold sets used for characterisation.

Nothing here changes the application, the model, the labels or any threshold.
"""
import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/validation -> repository root
DEFAULT_APP_PATH = os.path.join(REPO_ROOT, "AGRILENS_RaspberryPi", "main.py")

# Threshold profiles used for characterisation. Neither is a recommendation.
#   code_defaults : the constants hard-coded in the application.
#   device        : the device calibration seen in the working-tree kiosk_config.json at Phase A
#                   (ood_logit 6.0). It is recorded here only so behaviour under that setting can
#                   be characterised. It is not a default and must not be promoted to one.
PROFILES = {
    "code_defaults": {"confidence_threshold": 0.40, "ood_margin": 0.12, "ood_logit": 1.40},
    "device": {"confidence_threshold": 0.40, "ood_margin": 0.12, "ood_logit": 6.0},
}

_MODULE_CACHE = {}


def app_path():
    return os.path.abspath(os.environ.get("AGRILENS_APP_PATH", DEFAULT_APP_PATH))


def load_app(path=None):
    path = os.path.abspath(path or app_path())
    if path in _MODULE_CACHE:
        return _MODULE_CACHE[path]
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("agrilens_app_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["agrilens_app_under_test"] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[path] = module
    return module


def sample_images(samples_dir=None):
    """Return [(label_from_filename, absolute_path), ...] for the 24 sample images, sorted."""
    base = (samples_dir or os.environ.get("AGRILENS_SAMPLES_DIR")
            or os.path.join(os.path.dirname(app_path()), "diagnosis_samples"))
    out = []
    for root, _dirs, files in os.walk(base):
        for name in files:
            if name.lower().endswith((".jpg", ".jpeg", ".png")):
                label = name.rsplit("_sample", 1)[0] if "_sample" in name else os.path.splitext(name)[0]
                out.append((label, os.path.join(root, name)))
    return sorted(out)


VERDICT_BY_BUTTON_EN = {
    "UNKNOWN LEAF": "UNKNOWN",
    "LOW CONFIDENCE": "LOW_CONFIDENCE",
    "HEALTHY CROP": "HEALTHY",
    "DISEASE FOUND": "DISEASE",
}


def decide(app, labels, probs, raw_out, profile="code_defaults", selected_plant=None, thresholds=None):
    """
    Run AgriLensApp._render_diagnosis with a stand-in `self` and return its verdict.
    `thresholds` (dict) overrides the named profile.
    """
    t = dict(PROFILES[profile])
    if thresholds:
        t.update(thresholds)
    parsed = [app.parse_label(lbl) for lbl in labels]
    fake = SimpleNamespace(
        lang="EN",
        classifier=SimpleNamespace(labels=list(labels)),
        selected_plant=selected_plant,
        crops=[p[0] for p in parsed],
        parsed=parsed,
        threshold=t["confidence_threshold"],
        ood_margin=t["ood_margin"],
        ood_logit=t["ood_logit"],
        banner_frame=MagicMock(), banner=MagicMock(), plant_lbl=MagicMock(), disease_lbl=MagicMock(),
        cam_border=MagicMock(), diagnose_btn=MagicMock(), bar=MagicMock(),
        step_rows=[(MagicMock(), MagicMock(), MagicMock()) for _ in range(6)],
        BAR_W=300, BAR_H=20,
        px=lambda n: n,
        _draw_bar=MagicMock(),
    )
    app.AgriLensApp._render_diagnosis(fake, list(probs), raw_out)
    button = fake.diagnose_btn.config.call_args.kwargs.get("text", "")
    banner = fake.banner.config.call_args.kwargs.get("text", "")
    return {
        "verdict": VERDICT_BY_BUTTON_EN.get(button, "OTHER:" + button),
        "banner": banner,
        "button": button,
        "plant_text": fake.plant_lbl.config.call_args.kwargs.get("text", ""),
        "disease_text": fake.disease_lbl.config.call_args.kwargs.get("text", ""),
        "last_verdict": getattr(fake, "last_verdict", None),   # language-independent summary used by the diagnosis history (5.3.0)
    }


def effective_config(app, repo_cfg=None, user_cfg=None, tmpdir=None):
    """
    Run the application's real load_kiosk_config() against the given dict contents.
    repo_cfg is the app-directory kiosk_config.json, user_cfg is ~/.agrilens_kiosk_config.json.
    A value of None means that file does not exist.
    """
    import json
    import tempfile

    own = tmpdir is None
    d = tmpdir or tempfile.mkdtemp(prefix="agrilens_cfg_")
    rp, up = os.path.join(d, "kiosk_config.json"), os.path.join(d, "user_kiosk_config.json")
    for p in (rp, up):
        if os.path.exists(p):
            os.remove(p)
    if repo_cfg is not None:
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(repo_cfg, f)
    if user_cfg is not None:
        with open(up, "w", encoding="utf-8") as f:
            json.dump(user_cfg, f)
    old = app.CONFIG_PATH, app.USER_CONFIG_PATH
    app.CONFIG_PATH, app.USER_CONFIG_PATH = rp, up
    try:
        return app.load_kiosk_config()
    finally:
        app.CONFIG_PATH, app.USER_CONFIG_PATH = old
        if own:
            for p in (rp, up):
                if os.path.exists(p):
                    os.remove(p)
            try:
                os.rmdir(d)
            except OSError:
                pass
