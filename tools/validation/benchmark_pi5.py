#!/usr/bin/env python3
"""
AGRILENS - Raspberry Pi 5 inference benchmark (DRAFT, read-only with respect to the app).

Measures, on the machine it runs on:
  * model load time (several fresh loads)
  * per-image inference latency: mean, median, P95, P99, max (nearest-rank percentiles)
  * process CPU use and system CPU use (sampled from /proc)
  * memory: RSS before/after load, peak RSS (VmHWM), RSS trend during the run
  * SoC temperature, CPU frequency and firmware throttle flags (vcgencmd)

It times the REAL production pipeline (Classifier.predict: 6 image variants + ensemble)
by importing the Classifier class from the app file you point it at. It never edits the app,
the model or any config. Use --raw-session for a bare ONNX Runtime measurement instead.

PERFORMANCE ONLY. This measures speed, CPU, memory and temperature using the 24 sample images as a fixed\nworkload. It says nothing about model accuracy (see scripts/evaluate_field_validation.py for that).\n\nResults are only marked valid_for_pi5_reporting=true when /proc/device-tree/model says
"Raspberry Pi 5". Numbers from any other machine must not be quoted as Pi 5 figures.

Example (on the Pi):
  python3 benchmark_pi5.py --app-path ~/AGRILENS_RaspberryPi/main.py \
      --model ~/AGRILENS_RaspberryPi/agrilens.onnx --labels ~/AGRILENS_RaspberryPi/labels.txt \
      --samples-dir ~/AGRILENS_RaspberryPi/diagnosis_samples --runs 100
  Stop the kiosk first (or accept that it shares the CPU) and note which one you did.
"""
import argparse
import glob
import importlib.util
import json
import math
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone


def read(path, default=""):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return default


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def pi_model():
    return read("/proc/device-tree/model").rstrip("\x00")


def temp_c():
    try:
        return int(read("/sys/class/thermal/thermal_zone0/temp")) / 1000.0
    except ValueError:
        return None


def cpu_khz():
    try:
        return int(read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"))
    except ValueError:
        return None


def throttled():
    out = sh(["vcgencmd", "get_throttled"])
    return out.split("=")[-1] if out else None


def vm_kb(key):
    for line in read("/proc/self/status").splitlines():
        if line.startswith(key + ":"):
            return int(line.split()[1])
    return None


def sys_cpu():
    parts = read("/proc/stat").splitlines()[:1]
    if not parts:
        return None
    vals = [int(x) for x in parts[0].split()[1:]]
    return sum(vals), vals[3] + vals[4]  # total, idle(+iowait)


def pct(sorted_vals, q):
    """Nearest-rank percentile."""
    if not sorted_vals:
        return None
    k = max(0, math.ceil(q / 100.0 * len(sorted_vals)) - 1)
    return sorted_vals[k]


def stats(vals):
    if not vals:
        return {}
    s = sorted(vals)
    return {
        "n": len(s), "mean": sum(s) / len(s), "median": pct(s, 50),
        "p95": pct(s, 95), "p99": pct(s, 99), "min": s[0], "max": s[-1],
    }


class Sampler(threading.Thread):
    """Samples RSS, temperature, frequency, system CPU and process CPU every `interval` s."""

    def __init__(self, interval=0.5):
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_evt = threading.Event()
        self.rows = []

    def run(self):
        last_wall, last_proc, last_sys = time.perf_counter(), time.process_time(), sys_cpu()
        while not self.stop_evt.wait(self.interval):
            now, proc, cur = time.perf_counter(), time.process_time(), sys_cpu()
            dw = now - last_wall
            proc_core_pct = 100.0 * (proc - last_proc) / dw if dw > 0 else None  # 100 = one full core
            sys_pct = None
            if cur and last_sys and cur[0] > last_sys[0]:
                sys_pct = 100.0 * (1.0 - (cur[1] - last_sys[1]) / (cur[0] - last_sys[0]))
            self.rows.append({"t": now, "rss_kb": vm_kb("VmRSS"), "temp_c": temp_c(),
                              "cpu_khz": cpu_khz(), "proc_cpu_core_pct": proc_core_pct,
                              "sys_cpu_pct": sys_pct})
            last_wall, last_proc, last_sys = now, proc, cur

    def stop(self):
        self.stop_evt.set()
        self.join(timeout=2)


def col(rows, key):
    return [r[key] for r in rows if r.get(key) is not None]


def rss_slope_kb_per_min(rows):
    pts = [(r["t"], r["rss_kb"]) for r in rows if r["rss_kb"] is not None]
    if len(pts) < 10:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    den = sum((p[0] - mx) ** 2 for p in pts)
    return 60.0 * sum((p[0] - mx) * (p[1] - my) for p in pts) / den if den else None


def load_app_module(path):
    spec = importlib.util.spec_from_file_location("agrilens_app_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app-path", help="Path to the app file that defines Classifier (main.py or agrilens_app.py)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--labels", help="labels file (not needed with --raw-session)")
    ap.add_argument("--samples-dir", help="folder with sample leaf images (searched recursively)")
    ap.add_argument("--raw-session", action="store_true", help="time bare ONNX Runtime on a random 6-image batch")
    ap.add_argument("--load-runs", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--soak-seconds", type=int, default=0, help="keep inferring this long to observe memory/thermal trend")
    ap.add_argument("--idle-seconds", type=int, default=10)
    ap.add_argument("--note", default="", help="free text, e.g. 'kiosk stopped, heatsink+fan fitted'")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    model_name = pi_model()
    is_pi5 = "Raspberry Pi 5" in model_name
    if not is_pi5:
        print("=" * 70)
        print(" NOT A RASPBERRY PI 5 (%s). Results are marked INVALID for Pi reporting." % (model_name or platform.platform()))
        print("=" * 70)

    result = {
        "schema": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "device_model": model_name or None,
        "valid_for_pi5_reporting": is_pi5,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "note": a.note,
        "args": {k: v for k, v in vars(a).items()},
        "throttled_before": throttled(),
        "governor": read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") or None,
    }
    try:
        import onnxruntime
        import numpy
        result["onnxruntime"], result["numpy"] = onnxruntime.__version__, numpy.__version__
    except ImportError as e:
        sys.exit("onnxruntime/numpy missing: %s" % e)

    # idle baseline
    s_idle = Sampler()
    s_idle.start()
    time.sleep(a.idle_seconds)
    s_idle.stop()
    result["idle"] = {"sys_cpu_pct_mean": (sum(col(s_idle.rows, "sys_cpu_pct")) / max(1, len(col(s_idle.rows, "sys_cpu_pct")))) if col(s_idle.rows, "sys_cpu_pct") else None,
                      "temp_c_mean": (sum(col(s_idle.rows, "temp_c")) / max(1, len(col(s_idle.rows, "temp_c")))) if col(s_idle.rows, "temp_c") else None}

    rss_start = vm_kb("VmRSS")
    sampler = Sampler()
    sampler.start()

    # ---- model loading ----
    load_ms = []
    infer_fn, label_count = None, None
    if a.raw_session:
        import numpy as np
        import onnxruntime as ort
        for _ in range(a.load_runs):
            t0 = time.perf_counter()
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            sess = ort.InferenceSession(a.model, opts, providers=["CPUExecutionProvider"])
            load_ms.append((time.perf_counter() - t0) * 1000)
        name = sess.get_inputs()[0].name
        batch = np.random.RandomState(0).rand(6, 3, 224, 224).astype("float32")
        infer_fn = lambda _img: sess.run(None, {name: batch})
        images = [None]
    else:
        if not (a.app_path and a.labels and a.samples_dir):
            sys.exit("--app-path, --labels and --samples-dir are required unless --raw-session is used")
        from PIL import Image
        mod = load_app_module(os.path.abspath(a.app_path))
        for _ in range(a.load_runs):
            t0 = time.perf_counter()
            clf = mod.Classifier(a.model, a.labels)
            load_ms.append((time.perf_counter() - t0) * 1000)
            if clf.session is None:
                sys.exit("Classifier fell back to DEMO mode: %s" % clf.error_reason)
        label_count = len(clf.labels)
        paths = sorted(p for p in glob.glob(os.path.join(a.samples_dir, "**", "*"), recursive=True)
                       if p.lower().endswith((".jpg", ".jpeg", ".png")))
        if not paths:
            sys.exit("no sample images found in %s" % a.samples_dir)
        images = [Image.open(p).convert("RGB") for p in paths]
        infer_fn = lambda img: clf.predict(img)
        result["sample_count"] = len(images)

    rss_after_load = vm_kb("VmRSS")
    result["model_load_ms"] = {"first": load_ms[0], "all": load_ms, "later_median": (sorted(load_ms[1:])[len(load_ms[1:]) // 2] if len(load_ms) > 1 else None)}
    result["label_count"] = label_count

    # ---- inference ----
    for i in range(a.warmup):
        infer_fn(images[i % len(images)])
    lat = []
    for i in range(a.runs):
        t0 = time.perf_counter()
        infer_fn(images[i % len(images)])
        lat.append((time.perf_counter() - t0) * 1000)
    result["inference_ms"] = stats(lat)

    soak_lat = []
    if a.soak_seconds > 0:
        end = time.perf_counter() + a.soak_seconds
        i = 0
        while time.perf_counter() < end:
            t0 = time.perf_counter()
            infer_fn(images[i % len(images)])
            soak_lat.append((time.perf_counter() - t0) * 1000)
            i += 1
            time.sleep(0.5)  # roughly one scan every 0.5 s on top of inference time
        result["soak_inference_ms"] = stats(soak_lat)

    sampler.stop()
    rows = sampler.rows
    peak = vm_kb("VmHWM")
    result["memory_kb"] = {"rss_at_start": rss_start, "rss_after_load": rss_after_load,
                           "rss_end": vm_kb("VmRSS"), "peak_rss_vmhwm": peak,
                           "rss_trend_kb_per_min": rss_slope_kb_per_min(rows)}
    pc, sc = col(rows, "proc_cpu_core_pct"), col(rows, "sys_cpu_pct")
    result["cpu"] = {"process_core_pct_mean": sum(pc) / len(pc) if pc else None,
                     "process_core_pct_max": max(pc) if pc else None,
                     "note_process": "100 = one fully used core; Pi 5 has 4 cores (max 400)",
                     "system_pct_mean": sum(sc) / len(sc) if sc else None,
                     "system_pct_max": max(sc) if sc else None}
    tc, fk = col(rows, "temp_c"), col(rows, "cpu_khz")
    result["thermal"] = {"temp_c_max": max(tc) if tc else None, "temp_c_end": tc[-1] if tc else None,
                         "cpu_khz_min": min(fk) if fk else None, "cpu_khz_max": max(fk) if fk else None,
                         "throttled_after": throttled(),
                         "note": "get_throttled bit 0x4/0x40000 = throttled now/occurred; 0x1/0x10000 = under-voltage"}

    out = a.out or "benchmark_%s_%s.json" % (result["host"], datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    il = result["inference_ms"]
    print("\nModel load first/median-later (ms): %.0f / %s" % (load_ms[0], "%.0f" % result["model_load_ms"]["later_median"] if result["model_load_ms"]["later_median"] else "n/a"))
    print("Inference ms  mean %.1f  median %.1f  P95 %.1f  P99 %.1f  max %.1f  (n=%d)" % (il["mean"], il["median"], il["p95"], il["p99"], il["max"], il["n"]))
    print("Peak RSS (kB):", peak, " RSS trend kB/min:", result["memory_kb"]["rss_trend_kb_per_min"])
    print("CPU: process mean %s%% of one core, system mean %s%%" % (result["cpu"]["process_core_pct_mean"], result["cpu"]["system_pct_mean"]))
    print("Temp max:", result["thermal"]["temp_c_max"], " throttled:", result["throttled_before"], "->", result["thermal"]["throttled_after"])
    print("valid_for_pi5_reporting:", is_pi5, "  written:", out)


if __name__ == "__main__":
    main()
