"""
Classifier behaviour: model loading, preprocessing, prediction output, golden regression and error handling.

These are regression tests. The sample-image checks prove that restructuring did not change the
numbers. They are NOT an accuracy measurement (one image per class).
"""
import numpy as np
import pytest
from PIL import Image

import app_harness as H


# ---- loading ---------------------------------------------------------------------------------------------

def test_model_loads_in_onnx_mode(classifier):
    assert classifier.mode.startswith("ONNX")
    assert classifier.error_reason == ""
    assert classifier.layout == "NCHW" and (classifier.w, classifier.h) == (224, 224)
    assert len(classifier.labels) == 24


def test_missing_model_falls_back_to_demo(app, tmp_path):
    clf = app.Classifier(str(tmp_path / "missing.onnx"), app.LABELS_PATH)
    assert clf.mode == "DEMO" and clf.error_reason == "Model file not found"
    probs, _ms, raw = clf.predict(Image.new("RGB", (64, 64)))
    assert raw is None and len(probs) == 24 and probs == [1.0 / 24] * 24


def test_corrupt_model_falls_back_to_demo(app, tmp_path):
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"not an onnx file")
    clf = app.Classifier(str(bad), app.LABELS_PATH)
    assert clf.mode == "DEMO" and clf.error_reason


# ---- preprocessing ---------------------------------------------------------------------------------------

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def test_prep_tensor_shape_dtype_and_normalisation(classifier):
    white = classifier._prep_tensor(Image.new("RGB", (300, 200), (255, 255, 255)))
    black = classifier._prep_tensor(Image.new("RGB", (300, 200), (0, 0, 0)))
    assert white.shape == (3, 224, 224) and white.dtype == np.float32
    np.testing.assert_allclose(white[:, 0, 0], (1.0 - MEAN) / STD, rtol=1e-6)
    np.testing.assert_allclose(black[:, 0, 0], (0.0 - MEAN) / STD, rtol=1e-6)


def test_prep_tensor_channel_order_is_rgb(classifier):
    red = classifier._prep_tensor(Image.new("RGB", (50, 50), (255, 0, 0)))
    np.testing.assert_allclose(red[0, 0, 0], (1.0 - MEAN[0]) / STD[0], rtol=1e-6)
    np.testing.assert_allclose(red[2, 0, 0], (0.0 - MEAN[2]) / STD[2], rtol=1e-6)


@pytest.mark.parametrize("size", [(640, 480), (480, 640), (224, 224), (1000, 300), (300, 1000), (100, 100)])
def test_val_crop_outputs_224(classifier, size):
    assert classifier._prep_val_crop(Image.new("RGB", size)).size == (224, 224)


def test_val_crop_resizes_shorter_edge_to_256_then_center_crops(classifier):
    # A 640x480 image: shorter edge 480 -> 256, so width becomes round(640*256/480)=341; crop 224 from the centre.
    img = Image.new("RGB", (640, 480), (10, 20, 30))
    img.paste((200, 0, 0), (0, 0, 20, 480))        # left edge strip
    img.paste((0, 200, 0), (620, 0, 640, 480))     # right edge strip
    crop = np.asarray(classifier._prep_val_crop(img))
    assert not (crop[:, :, 0] > 150).any() and not (crop[:, :, 1] > 150).any()  # edge strips are cropped away


def test_enhance_mobile_screen_keeps_size_and_mode(classifier):
    img = Image.new("RGB", (320, 240), (90, 120, 60))
    out = classifier._enhance_mobile_screen(img)
    assert out.size == img.size and out.mode == "RGB"


# ---- prediction output -----------------------------------------------------------------------------------

def test_prediction_output_contract(classifier, samples):
    _label, path = samples[0]
    probs, ms, raw = classifier.predict(Image.open(path).convert("RGB"))
    assert len(probs) == 24 and len(raw) == 24
    assert abs(sum(probs) - 1.0) < 1e-5 and min(probs) >= 0.0
    assert ms > 0


def test_prediction_is_deterministic(classifier, samples):
    img = Image.open(samples[3][1]).convert("RGB")
    a, _, ra = classifier.predict(img)
    b, _, rb = classifier.predict(img)
    np.testing.assert_allclose(a, b, atol=1e-7)
    np.testing.assert_allclose(ra, rb, atol=1e-6)


# ---- golden regression -----------------------------------------------------------------------------------

def test_predictions_match_golden_baseline(app, classifier, golden):
    assert golden["labels"] == classifier.labels
    rows = {r["file"]: r for r in golden["samples"]}
    seen = 0
    for label, path in H.sample_images():
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        g = rows[name]
        probs, _ms, raw = classifier.predict(Image.open(path).convert("RGB"))
        top = int(np.argmax(probs))
        assert top == g["top1_index"], name
        np.testing.assert_allclose(probs, g["probs"], atol=1e-5, err_msg=name)
        np.testing.assert_allclose(raw, g["raw_logits"], atol=1e-3, err_msg=name)
        for prof in H.PROFILES:
            assert H.decide(app, classifier.labels, probs, raw, profile=prof)["verdict"] == g["verdict_" + prof], (name, prof)
        seen += 1
    assert seen == len(golden["samples"]) == 24


KNOWN_SAMPLE_MISMATCHES = {
    # 4.9.4 production model: 23 of 24 samples top-1 correct; the spider-mite sample is read as Yellow Leaf Curl Virus.
    "0b5bb7fb3916a7c1138f90cfc9abfdc130f06495a34282d474e52718b072ff80": {"Tomato_Spider_mites_Two_spotted_spider_mite": "Tomato_Tomato_YellowLeaf_Curl_Virus"},
    # AGRILENS-MULTICROP 1.0.0: 24 of 24 samples top-1 correct (captured 2026-11-17).
    "776d08ac669d0ea8874a458bfb6ea2657c5d40525d30021c7c8c1204d520332b": {},
    # AGRILENS-MULTICROP 1.1.0 (AGRILENS 5.2.0): 24 of 24 samples top-1 correct (captured 2026-11-19).
    "0774ca4aadab930086ade370234919a69cf35c8a22844355f78a20a194e0f08e": {},
}


def test_known_sample_mismatch_is_recorded_not_hidden(golden):
    # Observation per model (one image per class, not an accuracy figure). Any change to this set means prediction behaviour changed.
    wrong = {r["filename_label"]: r["top1_label"] for r in golden["samples"] if not r["top1_matches_filename"]}
    assert golden["model_sha256"] in KNOWN_SAMPLE_MISMATCHES, "record the sample mismatches of this model"
    assert wrong == KNOWN_SAMPLE_MISMATCHES[golden["model_sha256"]]


# ---- inference error handling (characterisation of current behaviour) ------------------------------------

class _FlakySession:
    """Delegates to the real session but raises on batched calls (batch > 1)."""

    def __init__(self, real, fail_batch=True, nan=False):
        self.real, self.fail_batch, self.nan = real, fail_batch, nan

    def run(self, names, feeds):
        batch = next(iter(feeds.values()))
        if self.fail_batch and batch.shape[0] > 1:
            raise RuntimeError("simulated batch failure")
        out = self.real.run(names, feeds)
        if self.nan:
            out = [np.full_like(out[0], np.nan)]
        return out


def test_batch_failure_falls_back_to_single_view_inference(classifier, samples):
    img = Image.open(samples[5][1]).convert("RGB")
    expected, _, expected_raw = classifier.predict(img)
    real = classifier.session
    classifier.session = _FlakySession(real)
    try:
        probs, _ms, raw = classifier.predict(img)
    finally:
        classifier.session = real
    assert int(np.argmax(probs)) == int(np.argmax(expected))
    np.testing.assert_allclose(probs, expected, atol=1e-4)


def test_total_inference_failure_currently_raises(classifier, samples):
    class Dead:
        def run(self, *_a, **_k):
            raise RuntimeError("simulated failure")
    real = classifier.session
    classifier.session = Dead()
    try:
        with pytest.raises(RuntimeError):
            classifier.predict(Image.open(samples[0][1]).convert("RGB"))
    finally:
        classifier.session = real


def test_nan_output_currently_yields_none_probabilities(classifier, samples):
    # Known gap recorded for Phase C: all-NaN output returns (None, ms, None) instead of a clean error.
    real = classifier.session
    classifier.session = _FlakySession(real, fail_batch=False, nan=True)
    try:
        probs, _ms, raw = classifier.predict(Image.open(samples[0][1]).convert("RGB"))
    finally:
        classifier.session = real
    assert probs is None and raw is None
