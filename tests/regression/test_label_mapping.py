"""Label-to-output mapping: 24 labels, 24 model outputs, stable order, consistent with samples."""
import hashlib
import os

import app_harness as H


def test_label_count_and_uniqueness(labels):
    assert len(labels) == 24
    assert len(set(labels)) == 24


def test_label_order_is_python_sorted(labels):
    # train_mobilenetv4.py builds class indices with sorted(); the model output index i
    # therefore corresponds to the i-th label in sorted order.
    assert labels == sorted(labels)


def test_model_output_dimension_matches_labels(app, ort, labels):
    sess = ort.InferenceSession(app.MODEL_PATH, providers=["CPUExecutionProvider"])
    out_shape = sess.get_outputs()[0].shape
    assert out_shape[-1] == len(labels)


def test_model_input_is_nchw_224(app, ort):
    sess = ort.InferenceSession(app.MODEL_PATH, providers=["CPUExecutionProvider"])
    shape = sess.get_inputs()[0].shape
    assert list(shape[1:]) == [3, 224, 224]


def test_classifier_uses_labels_file_in_order(classifier, labels):
    assert classifier.labels == labels


def test_hardcoded_fallback_labels_match_labels_file(app, labels):
    # Classifier falls back to a built-in list when labels.txt cannot be read. It must not drift.
    clf = app.Classifier.__new__(app.Classifier)
    clf.labels_path = os.path.join("does", "not", "exist.txt")
    assert clf._load_labels() == labels


def test_parse_label_crops_and_health(app, labels):
    parsed = [app.parse_label(lbl) for lbl in labels]
    crops = {p[0] for p in parsed}
    assert crops == {"Apple", "Mango", "Potato", "Tomato"}
    healthy = [lbl for lbl, p in zip(labels, parsed) if p[2]]
    assert sorted(healthy) == ["Apple_healthy", "Mango_Healthy", "Potato_healthy", "Tomato_healthy"]


def test_each_label_has_exactly_one_sample(labels, samples):
    names = [lbl for lbl, _ in samples]
    assert sorted(names) == sorted(labels)


def test_model_sha256_constant_matches_model_file(app):
    with open(app.MODEL_PATH, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    assert app.MODEL_SHA256.lower() == digest


def test_ota_extractor_reads_same_model_hash_from_source(app):
    with open(H.app_path(), "r", encoding="utf-8") as f:
        text = f.read()
    assert app._extract_const_from_code(text, "MODEL_SHA256").lower() == app.MODEL_SHA256.lower()
