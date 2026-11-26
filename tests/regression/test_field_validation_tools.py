"""
Field-validation tooling, exercised with SYNTHETIC data built from the 24 repo sample images.
This checks the tooling (storage of frame + crop, per-source separation, Wilson intervals, reporting).
It is not field data and says nothing about model accuracy. The camera path needs hardware (Phase E).
"""
import csv
import json
import os

import pytest
from PIL import Image

import capture_field_samples as cap
import evaluate_field_validation as ev


def test_default_inset_box_matches_kiosk_proposal():
    assert cap.default_inset_box(640, 480) == (90, 67, 550, 413)       # 14% inset, rounded
    assert cap.default_inset_box(100, 100) == (16, 16, 84, 84)         # minimum 16 px


def test_clamp_box_enforces_minimum_size_and_bounds():
    assert cap.clamp_box((-5, -5, 10, 10), 640, 480) == (0, 0, 16, 16)
    assert cap.clamp_box((600, 400, 900, 900), 640, 480) == (600, 400, 640, 480)
    assert cap.clamp_box((630, 470, 640, 480), 640, 480) == (624, 464, 640, 480)


def test_wilson_interval_properties():
    assert ev.wilson(0, 0) == (0.0, 0.0)
    lo, hi = ev.wilson(10, 10)
    assert hi == pytest.approx(1.0) and 0.65 < lo < 0.75
    lo, hi = ev.wilson(5, 10)
    assert lo < 0.5 < hi and hi - lo > 0.5          # n=10 gives a very wide band
    lo2, hi2 = ev.wilson(500, 1000)
    assert hi2 - lo2 < 0.07


def test_save_capture_keeps_original_frame_and_exact_crop(tmp_path):
    frame = Image.new("RGB", (640, 480), (10, 120, 30))
    frame.paste((255, 0, 0), (100, 100, 200, 200))
    row = cap.save_capture(str(tmp_path), frame, (100, 100, 200, 200), {
        "session": "s01", "seq": 1, "true_class": "Tomato_healthy", "source": "real_leaf", "crop_mode": "manual"})
    assert Image.open(tmp_path / row["frame_file"]).size == (640, 480)
    assert Image.open(tmp_path / row["frame_file"]).tobytes() == frame.tobytes()      # lossless original
    saved_crop = Image.open(tmp_path / row["crop_file"])
    assert saved_crop.size == (100, 100) and saved_crop.tobytes() == frame.crop((100, 100, 200, 200)).tobytes()
    rows = list(csv.DictReader(open(tmp_path / "field_samples.csv", encoding="utf-8")))
    assert rows[0]["crop_x0"] == "100" and rows[0]["crop_y1"] == "200" and rows[0]["source"] == "real_leaf"
    assert cap.next_index(str(tmp_path), "s01") == 2 and cap.next_index(str(tmp_path), "s02") == 1


def test_args_validation_rejects_bad_class_and_source():
    class A:
        source, true_class = "real_leaf", "Not_A_Class"
    with pytest.raises(SystemExit):
        cap.validate_args(A, ["Apple_Rust"])
    A.true_class = "Out_of_scope"
    cap.validate_args(A, ["Apple_Rust"])
    A.source = "photo"
    with pytest.raises(SystemExit):
        cap.validate_args(A, ["Apple_Rust"])


@pytest.fixture(scope="module")
def synthetic_folder(tmp_path_factory, app, labels, samples):
    folder = str(tmp_path_factory.mktemp("field"))
    seq = {"real_leaf": 0, "phone_screen": 0, "printed": 0}
    # real_leaf: all 24 samples; phone_screen: first 6; printed: first 3 (plus one out-of-scope each for two sources)
    plan = [("real_leaf", samples), ("phone_screen", samples[:6]), ("printed", samples[:3])]
    for source, items in plan:
        session = "syn_" + source
        with open(os.path.join(folder, "session_%s_device_config.json" % session), "w", encoding="utf-8") as f:
            json.dump({"effective_config": {"confidence_threshold": 0.4, "ood_margin": 0.12, "ood_logit": 6.0}}, f)
        for label, path in items:
            seq[source] += 1
            frame = Image.open(path).convert("RGB")
            cap.save_capture(folder, frame, cap.default_inset_box(*frame.size), {
                "session": session, "seq": seq[source], "true_class": label, "source": source, "crop_mode": "default_inset14pct"})
        seq[source] += 1
        blank = Image.new("RGB", (640, 480), (128, 128, 128))
        cap.save_capture(folder, blank, cap.default_inset_box(640, 480), {
            "session": session, "seq": seq[source], "true_class": "Out_of_scope", "source": source, "crop_mode": "default_inset14pct"})
    return folder


def test_evaluation_separates_sources_and_reports(synthetic_folder, app, classifier):
    result = ev.evaluate(synthetic_folder, app=app, classifier=classifier)
    assert not result["problems"], result["problems"]
    by = {}
    for r in result["results"]:
        by.setdefault(r["source"], []).append(r)
    assert {k: len(v) for k, v in by.items()} == {"real_leaf": 25, "phone_screen": 7, "printed": 4}
    s = ev.summarise(by["real_leaf"], result["labels"])
    assert s["in_scope_n"] == 24 and s["out_of_scope_n"] == 1
    assert 0 < s["top1_correct"] <= 24
    assert set(s["sensitivity"]) == {str(v) for v in ev.SENSITIVITY_OOD}
    # thresholds were taken from each session's recorded config (ood_logit 6.0), not hard-coded
    assert all(r["thresholds"]["ood_logit"] == 6.0 for r in result["results"])

    ev.write_outputs(result, synthetic_folder)
    report = open(os.path.join(synthetic_folder, "field_validation_report.md"), encoding="utf-8").read()
    for header in ("## Source: real_leaf", "## Source: phone_screen", "## Source: printed", "INFORMATION ONLY", "Pilot-size data"):
        assert header in report
    assert os.path.exists(os.path.join(synthetic_folder, "field_validation_results.csv"))


def test_evaluation_detects_a_tampered_crop(synthetic_folder, app, classifier):
    rows = list(csv.DictReader(open(os.path.join(synthetic_folder, "field_samples.csv"), encoding="utf-8")))
    target = os.path.join(synthetic_folder, rows[0]["crop_file"])
    original = open(target, "rb").read()
    try:
        Image.new("RGB", Image.open(target).size, (1, 2, 3)).save(target, format="PNG")
        result = ev.evaluate(synthetic_folder, app=app, classifier=classifier)
        assert any("stored crop differs" in p for p in result["problems"])
    finally:
        open(target, "wb").write(original)
