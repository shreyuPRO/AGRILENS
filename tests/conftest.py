"""
Shared fixtures. The tests exercise the application file selected by AGRILENS_APP_PATH
(default: the generated device package AGRILENS_RaspberryPi/main.py, i.e. exactly what is published) and never modify it.

Environment variables (all optional):
  AGRILENS_APP_PATH      path to the application file under test
  AGRILENS_SAMPLES_DIR   folder with the 24 sample images (default: <app dir>/diagnosis_samples)
"""
import os
import sys

import pytest

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "validation"))

import app_harness as H  # noqa: E402

BASELINE_DIR = os.path.join(ROOT, "tests", "regression", "baseline")  # production 4.9.4 baselines (config precedence, goldens of the 4.9.4 model)


@pytest.fixture(scope="session")
def app():
    return H.load_app()


@pytest.fixture(scope="session")
def ort():
    return pytest.importorskip("onnxruntime")


@pytest.fixture(scope="session")
def classifier(app, ort):
    clf = app.Classifier(app.MODEL_PATH, app.LABELS_PATH)
    assert clf.session is not None, "Classifier fell back to DEMO mode: %s" % clf.error_reason
    return clf


@pytest.fixture(scope="session")
def labels(app):
    with open(app.LABELS_PATH, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


@pytest.fixture(scope="session")
def samples():
    found = H.sample_images()
    assert found, "no sample images found; set AGRILENS_SAMPLES_DIR"
    return found


@pytest.fixture(scope="session")
def golden(app):
    """Golden predictions for the model under test, selected by model SHA-256 (goldens are model-specific).
    Missing goldens for the model under test are a FAILURE, never a silent skip."""
    import glob
    import json
    found = {}
    for p in glob.glob(os.path.join(ROOT, "tests", "regression", "baseline*", "golden_predictions.json")):
        with open(p, encoding="utf-8") as f:
            g = json.load(f)
        found[str(g.get("model_sha256", "")).lower()] = g
    sha = str(app.MODEL_SHA256).lower()
    assert sha in found, "no golden predictions for model %s (have: %s)" % (sha, sorted(found))
    return found[sha]
