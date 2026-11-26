#!/usr/bin/env python3
"""Build the unsupported-image set for AGRILENS-MULTICROP 1.0.0 (ood_v2). For an integrated four-crop model the other-crop leaves are in-distribution,
so the set holds: synthetic non-leaf images (new seeds), crops of two sample photographs (new seeds), background-only windows cut from TRAIN/VALIDATION
images of all four crops, and Mango Turning Brown leaves (a quarantined, unsupported Mango condition; informational). Each group is split 50/50 into a
calibration half and an evaluation half (seed 2026); the evaluation half is fingerprinted and not read until the single release evaluation.
Output (outside the repository): <out>/cache/*.npy, <out>/ood_v2_manifest.csv, <out>/OOD_V2_EVALUATION_HALF.sha256"""
import argparse, hashlib, os
import numpy as np, pandas as pd
from PIL import Image, ImageOps
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); ap.add_argument("--cache", required=True); ap.add_argument("--out", required=True); a = ap.parse_args()
C = os.path.join(a.out, "cache"); os.makedirs(C, exist_ok=True); rng = np.random.default_rng(2026); rows = []


def put(group, src, im, tag):
    w, h = im.size; s = 256.0 / min(w, h); im = im.convert("RGB").resize((max(256, round(w * s)), max(256, round(h * s))), Image.BILINEAR)
    oid = f"OOD2-{len(rows) + 1:05d}"; np.save(os.path.join(C, oid + ".npy"), np.asarray(im, dtype=np.uint8)); rows.append({"ood_id": oid, "group": group, "source": src, "tag": tag})


for k, kind in enumerate(("uniform", "green_uniform", "gradient", "noise", "checker", "block")):
    for i in range(20):
        r = np.random.default_rng(5000 + k * 100 + i); W, H = 320, 240
        if kind == "uniform": arr = np.ones((H, W, 3)) * r.integers(0, 256, 3)
        elif kind == "green_uniform": arr = np.ones((H, W, 3)) * np.array([60 + r.integers(0, 60), 110 + r.integers(0, 70), 40 + r.integers(0, 50)])
        elif kind == "gradient": arr = np.linspace(r.integers(0, 120), r.integers(130, 256), W)[None, :, None] * np.ones((H, 1, 3)) * (0.6 + 0.4 * r.random(3))
        elif kind == "noise": arr = r.normal(128, r.integers(10, 70), (H, W, 3))
        elif kind == "checker": sz = int(r.integers(8, 40)); arr = ((np.indices((H, W)).sum(0) // sz) % 2)[..., None] * np.array([255, 255, 255]) * 1.0
        else: arr = np.ones((H, W, 3)) * 255; arr[H // 3:2 * H // 3, W // 4:3 * W // 4] = r.integers(0, 256, 3)
        put("nonleaf_synthetic", "synthetic:" + kind, Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), kind)
import sklearn
sk = os.path.join(os.path.dirname(sklearn.__file__), "datasets", "images")
for name in ("china.jpg", "flower.jpg"):
    im = Image.open(os.path.join(sk, name)).convert("RGB")
    for i in range(60):
        s = int(rng.integers(100, min(im.size) + 1)); x, y = int(rng.integers(0, im.size[0] - s + 1)), int(rng.integers(0, im.size[1] - s + 1)); put("nonleaf_photo", name, im.crop((x, y, x + s, y + s)), name)
tv = pd.concat([pd.read_csv(os.path.join(a.dataset, "splits", f)) for f in ("train.csv", "val.csv")]).sample(frac=1, random_state=11); got = {}
for r in tv.itertuples():
    if got.get(r.crop, 0) >= 40: continue
    arr = np.load(os.path.join(a.cache, r.image_id + ".npy")).astype(np.float32) / 255; h, w = arr.shape[:2]; mx, mn = arr.max(2), arr.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0); fg = (sat > 0.15) & (mx > 0.08); s = int(min(h, w) * 0.4)
    for (y0, x0) in ((0, 0), (0, w - s), (h - s, 0), (h - s, w - s)):
        if fg[y0:y0 + s, x0:x0 + s].mean() < 0.005:
            put("nonleaf_background", r.image_id, Image.fromarray((arr[y0:y0 + s, x0:x0 + s] * 255).astype(np.uint8)), r.crop); got[r.crop] = got.get(r.crop, 0) + 1; break
m = pd.read_csv(os.path.join(a.dataset, "manifests", "image_manifest.csv"), low_memory=False); tb = m[(m.class_id == "MNG009") & (m.status == "quarantined")].sample(160, random_state=7)
for r in tb.itertuples():
    with Image.open(os.path.join(a.dataset, r.master_relpath.replace("/", os.sep))) as im:
        im.draft("RGB", (600, 600)); put("unsupported_mango_condition_turning_brown", r.image_id, ImageOps.exif_transpose(im), "MNG009")
df = pd.DataFrame(rows); df["split"] = ""
for g, idx in df.groupby("group").groups.items():
    ids = np.array(list(idx)); rng.shuffle(ids); df.loc[ids[: len(ids) // 2], "split"] = "calibration"; df.loc[ids[len(ids) // 2:], "split"] = "evaluation"
df.to_csv(os.path.join(a.out, "ood_v2_manifest.csv"), index=False)
ev = df[df.split == "evaluation"].sort_values("ood_id")
fp = hashlib.sha256("\n".join(f"{r.ood_id},{r.group},{r.source},{hashlib.sha256(open(os.path.join(C, r.ood_id + '.npy'), 'rb').read()).hexdigest()}" for r in ev.itertuples()).encode()).hexdigest()
open(os.path.join(a.out, "OOD_V2_EVALUATION_HALF.sha256"), "w").write(fp + "  fingerprint of the ood_v2 evaluation half\n")
print(df.groupby(["group", "split"]).size().unstack().to_string(), "\nfingerprint", fp)
