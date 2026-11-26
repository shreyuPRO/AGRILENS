#!/usr/bin/env python3
"""Write documentation/release_notes/FILE_CHANGE_REGISTER_5.0.0.csv from git: every path changed between the 4.9.4/Phase A base and the
staged (or committed) 5.0.0 tree, classified as added / modified / moved / renamed / archived / deleted.
  python write_change_register.py [--base phase-A] [--target <commit>|--cached]"""
import argparse, csv, os, subprocess
from collections import Counter
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument("--base", default="phase-A"); ap.add_argument("--target", default=""); a = ap.parse_args()
cmd = ["git", "-C", R, "-c", "core.quotepath=off", "diff", "--name-status", "-M50%", a.base] + ([a.target] if a.target else ["--cached"])
rows = []
for ln in subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines():
    p = ln.split("\t"); st = p[0]
    if st.startswith("R"):
        src, dst = p[1], p[2]
        kind = "archived" if dst.startswith("archive/") else ("renamed" if os.path.dirname(src) == os.path.dirname(dst) else "moved")
        rows.append({"change": kind, "path": dst, "previous_path": src, "similarity_percent": st[1:]})
    else:
        rows.append({"change": {"A": "added", "M": "modified", "D": "deleted", "T": "modified"}.get(st[0], st), "path": p[1], "previous_path": "", "similarity_percent": ""})
for r in rows:
    r["note"] = "generated OTA publication folder (build_device_package.py)" if r["path"].startswith("AGRILENS_RaspberryPi/") else ""
out = os.path.join(R, "documentation", "release_notes", "FILE_CHANGE_REGISTER_5.0.0.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, ["change", "path", "previous_path", "similarity_percent", "note"], lineterminator="\n"); w.writeheader(); w.writerows(sorted(rows, key=lambda r: (r["change"], r["path"])))
print(out, dict(Counter(r["change"] for r in rows)), "total", len(rows))
