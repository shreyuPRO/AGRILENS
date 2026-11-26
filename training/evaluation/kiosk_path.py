"""Run the APPLICATION's own inference and decision code on a model, read-only.
The application file is imported unchanged (bytecode writing disabled); its Classifier builds the six views, ensembles the logits and selects the
output exactly as on the kiosk; the verdict comes from AgriLensApp._render_diagnosis through tools/validation/app_harness.decide."""
import os, sys
import numpy as np
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "validation"))
import app_harness as H  # noqa: E402


def load_app(main_py): return H.load_app(main_py)


def classifier(app, onnx, labels):
    c = app.Classifier(onnx, labels)
    assert c.session is not None, f"engine not loaded: {c.mode} {c.error_reason}"
    return c


def softmax(x):
    e = np.exp(x - np.max(x)); return e / e.sum()


def kiosk(clf, pil):
    probs, _ms, raw = clf.predict(pil); return np.asarray(probs), np.asarray(raw)


def single(clf, pil):
    t = clf._prep_tensor(clf._prep_val_crop(pil.convert("RGB"))); raw = clf.session.run(None, {clf.input_name: t[None]})[0][0]; return softmax(raw), raw


def verdict(probs, raw, conf, margin, logit):
    """Identical to the application's gate order (checked against _render_diagnosis by verify_gate_equivalence in evaluate_release)."""
    s = np.sort(probs)[::-1]
    if raw is not None and raw.max() < logit: return "UNKNOWN"
    if s[0] < conf or s[0] - s[1] < margin: return "LOW_CONFIDENCE"
    return "ACCEPT"
