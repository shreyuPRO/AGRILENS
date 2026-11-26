"""
Confidence and out-of-distribution (OOD) decision rules.

The application's real AgriLensApp._render_diagnosis is executed against a stand-in UI object
(scripts/app_harness.decide), so the production rules are tested, not a copy of them.
Expected verdicts below are derived by hand from the rules, not recorded from the output.

Rules (code): UNKNOWN if the winning class is a negative class, OR max raw logit < ood_logit, OR a
selected crop has total probability < 0.12. Otherwise LOW_CONFIDENCE if confidence < threshold OR
(top1 - top2) < ood_margin. Otherwise HEALTHY or DISEASE by the label.
"""
import numpy as np
import pytest

import app_harness as H


def softmax(x):
    e = np.exp(x - np.max(x))
    return (e / e.sum()).tolist()


def logits(labels, peaks, base=0.0):
    v = np.full(len(labels), base, dtype=np.float64)
    for name, value in peaks.items():
        v[labels.index(name)] = value
    return v


def verdict(app, labels, raw, profile="code_defaults", plant=None, thresholds=None, probs=None):
    p = probs if probs is not None else softmax(raw)
    return H.decide(app, labels, p, raw, profile=profile, selected_plant=plant, thresholds=thresholds)["verdict"]


def test_confident_disease(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 10.0})
    assert verdict(app, labels, raw) == "DISEASE"
    assert verdict(app, labels, raw, "device") == "DISEASE"


def test_confident_healthy(app, labels):
    raw = logits(labels, {"Tomato_healthy": 10.0})
    assert verdict(app, labels, raw) == "HEALTHY"


def test_weak_logit_is_unknown_only_when_below_the_ood_gate(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 5.0}, base=-3.0)   # very peaked, but max logit is 5.0
    assert verdict(app, labels, raw, "code_defaults") == "DISEASE"   # 5.0 >= 1.40
    assert verdict(app, labels, raw, "device") == "UNKNOWN"          # 5.0 <  6.0


def test_ood_gate_boundary_is_strictly_less_than(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 6.0}, base=-3.0)
    assert verdict(app, labels, raw, "device") == "DISEASE"          # 6.0 < 6.0 is false
    raw2 = logits(labels, {"Tomato_Late_blight": 5.99}, base=-3.0)
    assert verdict(app, labels, raw2, "device") == "UNKNOWN"


def test_missing_raw_logits_disable_the_ood_gate(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 3.0}, base=-3.0)
    p = softmax(raw)
    out = H.decide(app, labels, p, None, profile="device")
    assert out["verdict"] == "DISEASE"  # max_logit defaults to 10.0 when raw output is unavailable


def test_low_probability_is_low_confidence(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 2.0})                # confidence about 0.24
    assert verdict(app, labels, raw, "code_defaults") == "LOW_CONFIDENCE"


def test_unknown_takes_precedence_over_low_confidence(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 2.0})
    assert verdict(app, labels, raw, "device") == "UNKNOWN"


def test_narrow_margin_is_low_confidence_even_with_high_confidence(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 6.5, "Tomato_Early_blight": 6.5})  # 0.5 / 0.5, margin 0
    assert verdict(app, labels, raw, "device") == "LOW_CONFIDENCE"


def _probs(labels, top, second, others_total):
    p = np.full(len(labels), others_total / (len(labels) - 2))
    p[labels.index("Tomato_Late_blight")] = top
    p[labels.index("Tomato_Early_blight")] = second
    return p.tolist()


def test_confidence_threshold_boundary(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 10.0})
    at = _probs(labels, 0.40, 0.10, 0.50)
    below = _probs(labels, 0.399, 0.10, 0.501)
    assert H.decide(app, labels, at, raw)["verdict"] == "DISEASE"          # conf < 0.40 is false
    assert H.decide(app, labels, below, raw)["verdict"] == "LOW_CONFIDENCE"


def test_margin_boundary_region(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 10.0})
    assert H.decide(app, labels, _probs(labels, 0.50, 0.39, 0.11), raw)["verdict"] == "LOW_CONFIDENCE"   # margin 0.11
    assert H.decide(app, labels, _probs(labels, 0.50, 0.37, 0.13), raw)["verdict"] == "DISEASE"          # margin 0.13


def test_selected_crop_mismatch_is_unknown(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 10.0})
    assert verdict(app, labels, raw, plant="Apple") == "UNKNOWN"      # Apple total probability < 0.12
    assert verdict(app, labels, raw, plant="Tomato") == "DISEASE"


def test_thresholds_can_be_overridden_per_call(app, labels):
    raw = logits(labels, {"Tomato_Late_blight": 3.0}, base=-3.0)
    assert verdict(app, labels, raw, thresholds={"ood_logit": 3.5}) == "UNKNOWN"
    assert verdict(app, labels, raw, thresholds={"ood_logit": 2.5}) == "DISEASE"


@pytest.mark.parametrize("name,expected", [
    ("Apple_healthy", "HEALTHY"), ("Mango_Healthy", "HEALTHY"), ("Potato_healthy", "HEALTHY"),
    ("Apple_Rust", "DISEASE"), ("Mango_Sooty_Mould", "DISEASE"), ("Potato_Late_blight", "DISEASE"),
])
def test_every_crop_reaches_expected_verdict(app, labels, name, expected):
    assert verdict(app, labels, logits(labels, {name: 10.0})) == expected
