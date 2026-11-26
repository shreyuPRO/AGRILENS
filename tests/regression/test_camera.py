"""
Camera behaviour using a mocked OpenCV (no hardware). SIMULATED results only.

Characterises the CURRENT Camera class, including the gap that it does not reconnect on its own
after a disconnect (only detect_webcam() re-opens it). Phase C adds the supervisor and changes
those two characterisation tests deliberately.
"""
import subprocess
import threading
from types import SimpleNamespace

import numpy as np
import pytest


class FakeCap:
    def __init__(self, port, behaviour):
        self.port, self.behaviour = port, behaviour
        self.released = 0
        self.reads = 0
        self.props = {}

    def isOpened(self):
        return self.released == 0 and self.behaviour != "closed"

    def set(self, prop, value):
        self.props[prop] = value
        return True

    def read(self):
        self.reads += 1
        if self.behaviour == "raise":
            raise RuntimeError("device error")
        if self.behaviour == "fail":
            return False, None
        w = int(self.props.get(FakeCV2.CAP_PROP_FRAME_WIDTH, 640))
        h = int(self.props.get(FakeCV2.CAP_PROP_FRAME_HEIGHT, 480))
        if self.behaviour == "vga_only":
            if (w, h) != (640, 480):
                return False, None       # camera that cannot stream the HD mode
        elif self.behaviour == "max_vga":
            w, h = 640, 480              # camera that silently keeps 640x480
        return True, np.full((h, w, 3), 120, dtype=np.uint8)

    def release(self):
        self.released += 1


class FakeCV2:
    CAP_DSHOW, CAP_ANY, CAP_V4L2 = 700, 0, 200
    CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT, CAP_PROP_BUFFERSIZE = 3, 4, 38
    CAP_PROP_AUTO_EXPOSURE, CAP_PROP_BACKLIGHT, CAP_PROP_AUTO_WB, CAP_PROP_WB_TEMPERATURE = 21, 32, 44, 45
    CAP_PROP_FOURCC = 6
    COLOR_BGR2RGB = 4

    @staticmethod
    def VideoWriter_fourcc(*chars):
        return sum(ord(ch) << (8 * i) for i, ch in enumerate(chars))

    def __init__(self, ports):
        self.ports = ports          # {port: behaviour}
        self.opened = []            # every FakeCap created

    def VideoCapture(self, port, backend=0):
        cap = FakeCap(port, self.ports.get(port, "closed"))
        self.opened.append(cap)
        return cap

    @staticmethod
    def cvtColor(frame, _code):
        return frame


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="", returncode=0))


def make_camera(app, ports):
    cam = app.Camera(auto_detect=False)
    cam.cv2 = FakeCV2(ports)
    return cam


def test_detect_fails_cleanly_when_no_camera(app):
    cam = make_camera(app, {})
    ok, msg = cam.detect_webcam()
    assert ok is False and cam.kind == "none" and cam.port == -1 and cam.cap is None
    assert "No active webcam" in msg
    assert all(c.released >= 1 for c in cam.cv2.opened if c.behaviour != "closed")


def test_detect_selects_first_working_port_and_configures_it(app):
    # 5.1.0: the default request is 1280x720 (C270 maximum) in MJPG.
    cam = make_camera(app, {1: "ok"})
    ok, msg = cam.detect_webcam()
    assert ok and cam.port == 1 and cam.last_working_port == 1
    assert cam.kind.startswith("USB Camera") and (cam.width, cam.height) == (1280, 720)
    assert cam.cap.props[FakeCV2.CAP_PROP_FRAME_WIDTH] == 1280 and cam.cap.props[FakeCV2.CAP_PROP_FRAME_HEIGHT] == 720
    assert cam.cap.props[FakeCV2.CAP_PROP_BUFFERSIZE] == 1
    assert cam.cap.props[FakeCV2.CAP_PROP_FOURCC] == FakeCV2.VideoWriter_fourcc(*"MJPG")


def test_detect_falls_back_to_640x480_when_hd_delivers_no_frames(app):
    cam = make_camera(app, {0: "vga_only"})
    ok, _msg = cam.detect_webcam()
    assert ok and cam.port == 0 and (cam.width, cam.height) == (640, 480)
    assert cam.cap.props[FakeCV2.CAP_PROP_FRAME_WIDTH] == 640
    assert cam.read().size == (640, 480)


def test_detect_reports_the_size_the_camera_actually_delivers(app):
    cam = make_camera(app, {0: "max_vga"})
    assert cam.detect_webcam()[0] and (cam.width, cam.height) == (640, 480) and "640x480" in cam.kind


def test_configured_640x480_is_requested_without_hd_attempt(app):
    cam = make_camera(app, {0: "ok"})
    cam.resolution = (640, 480)
    assert cam.detect_webcam()[0] and (cam.width, cam.height) == (640, 480)
    assert FakeCV2.CAP_PROP_FOURCC not in cam.cap.props


def test_hd_frames_are_returned_at_full_size(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    assert cam.read().size == (1280, 720)


def test_port_that_opens_but_never_delivers_frames_is_released(app):
    cam = make_camera(app, {0: "fail"})
    ok, _msg = cam.detect_webcam()
    assert ok is False and cam.cap is None
    probing = [c for c in cam.cv2.opened if c.behaviour == "fail"]
    assert probing and all(c.released >= 1 for c in probing)   # opened-but-silent handles are not leaked


def test_last_working_port_is_probed_first(app):
    cam = make_camera(app, {0: "ok", 2: "ok"})
    cam.last_working_port = 2
    assert cam.detect_webcam()[0] and cam.port == 2


def test_read_returns_pil_frame(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    cam.resolution = (640, 480)
    cam.detect_webcam()
    img = cam.read()
    assert img is not None and img.size == (640, 480) and img.mode == "RGB"


def test_isp_is_noop_at_neutral_settings(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    img = cam.read()
    assert np.asarray(img).mean() == pytest.approx(120, abs=0.01)


def test_single_dropped_frame_resets_after_success(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    cam.cap.behaviour = "fail"
    assert cam.read() is None and cam.fail_count == 1
    cam.cap.behaviour = "ok"
    assert cam.read() is not None and cam.fail_count == 0


def test_camera_is_dropped_after_more_than_30_failed_reads(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    cap = cam.cap
    cap.behaviour = "fail"
    for _ in range(30):
        assert cam.read() is None
    assert cam.cap is cap and cam.kind != "none"       # exactly 30 failures: still held
    assert cam.read() is None                           # the 31st
    assert cam.cap is None and cam.kind == "none" and cap.released == 1


def test_exceptions_during_read_count_as_failures(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    cam.cap.behaviour = "raise"
    for _ in range(31):
        assert cam.read() is None
    assert cam.cap is None and cam.kind == "none"


def test_no_automatic_reconnect_after_disconnect_current_behaviour(app):
    # Gap to fix in Phase C: after the drop, nothing re-opens the camera unless detect_webcam() is called.
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    cam.cap.behaviour = "fail"
    for _ in range(31):
        cam.read()
    cam.cv2.ports[0] = "ok"                             # camera is plugged back in
    for _ in range(50):
        assert cam.read() is None
    assert cam.cap is None
    assert cam.detect_webcam()[0] and cam.read() is not None   # only an explicit re-detect recovers


def test_close_releases_and_is_idempotent(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    cap = cam.cap
    cam.close()
    cam.close()
    assert cap.released == 1 and cam.cap is None and cam.kind == "none" and cam.port == -1
    assert cam.read() is None


def test_repeated_detection_releases_previous_handle(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    first = cam.cap
    for _ in range(5):
        assert cam.detect_webcam()[0]
    assert first.released >= 1
    live = [c for c in cam.cv2.opened if c.released == 0 and c.behaviour == "ok"]
    assert len(live) == 1 and live[0] is cam.cap     # no leaked handles after 6 detections


def test_concurrent_reads_do_not_raise_or_deadlock(app):
    cam = make_camera(app, {0: "ok"})
    cam.detect_webcam()
    errors = []

    def worker():
        try:
            for _ in range(40):
                cam.read()
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert not any(t.is_alive() for t in threads) and not errors


def test_missing_opencv_is_reported_not_raised(app, monkeypatch):
    import builtins
    cam = app.Camera(auto_detect=False)
    cam.cv2 = None
    real_import = builtins.__import__

    def blocked(name, *a, **k):
        if name == "cv2":
            raise ImportError("no cv2")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", blocked)
    ok, msg = cam.detect_webcam()
    assert ok is False and "OpenCV" in msg
