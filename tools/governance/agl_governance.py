#!/usr/bin/env python3
"""AGRILENS engineering governance tool: version consistency, change impact, documentation checks, change register,
pre-commit / pre-release quality gate and the git / Kiro hook entry points.

Policy and rationale: documentation/governance/ENGINEERING_GOVERNANCE.md. Rules: tools/governance/governance_rules.json.

The tool never modifies production configuration, the generated OTA folder AGRILENS_RaspberryPi/, deployed files, or git
configuration. Commands that write (bump, index --write, register new/sync, install-git-hooks) change only the files they name.

Commands
  check [--staged | --full] [--no-tests]   PASS/FAIL report (pre-commit: --staged, pre-release: --full)
  impact [--staged]                       affected areas, version, documentation and tests for uncommitted changes
  docs [--hook]                           documentation obligations for uncommitted changes (--hook: silent when none)
  version                                 show the authoritative version and every derived value
  bump {patch,minor,major} --reason TEXT  increment APP_VERSION and propagate it (source files only, never the package)
  index [--write | --check]               HOW_TO.md documentation index
  register new --title T --category C     append a change-register entry skeleton
  register sync                           fill commit ids of 'pending' entries from git history
  hook-pretool                            Kiro PreToolUse entry point (reads the tool call as JSON on stdin)
  post-commit                             git post-commit entry point (records the commit in git notes, ref 'agrilens')
  install-git-hooks                       install the pre-commit and post-commit shims into .git/hooks
"""
import argparse
import datetime
import fnmatch
import hashlib
import importlib.util
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(ROOT, "tools", "governance", "governance_rules.json")
STATE_DIR_NAME = "agrilens"            # under the git directory; never part of the working tree
NOTES_REF = "agrilens"
INDEX_BEGIN, INDEX_END = "<!-- agl:index:begin -->", "<!-- agl:index:end -->"
VERSION_MARK = re.compile(r"<!-- agl:version -->([^<]*)<!-- /agl:version -->")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"


# ----------------------------------------------------------------------------------------------------------------- basics
def load_rules():
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def clean_env():
    """Environment for child tools (pytest, ruff, builder) without the GIT_* variables a git hook sets: tests that run git
    themselves must not inherit the index or directory of the commit in progress."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def run(cmd, cwd=ROOT, timeout=900, input_text=None, env=None):
    """Runs a command; returns (exit code, stdout, stderr) as text. Never raises for a non-zero exit."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, env=env, input=input_text.encode("utf-8") if input_text is not None else None)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except FileNotFoundError as e:
        return 127, "", str(e)
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s: {' '.join(cmd)}"


def git(*args, check=False):
    code, out, err = run(["git", *args])
    if check and code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip()}")
    return out if code == 0 else ""


def git_dir():
    d = git("rev-parse", "--git-dir").strip()
    return os.path.join(ROOT, d) if d and not os.path.isabs(d) else d


def state_path(name):
    d = os.path.join(git_dir(), STATE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def read_text(rel, source="worktree"):
    """File content from the working tree ('worktree'), the index ('index') or a commit ('HEAD', hash). None if absent."""
    if source == "worktree":
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            return None
        with open(p, "rb") as f:
            return f.read().decode("utf-8", "replace")
    spec = f":{rel}" if source == "index" else f"{source}:{rel}"
    code, out, _ = run(["git", "show", spec])
    return out if code == 0 else None


def read_bytes(rel, source="worktree"):
    if source == "worktree":
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            return None
        with open(p, "rb") as f:
            return f.read()
    spec = f":{rel}" if source == "index" else f"{source}:{rel}"
    try:
        p = subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True, timeout=120)
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


def const(src, name):
    m = re.search(rf'^{name}\s*=\s*"([^"]*)"', src or "", re.M)
    if m:
        return m.group(1)
    m = re.search(rf"^{name}\s*=\s*(\d+)", src or "", re.M)
    return m.group(1) if m else ""


def vtuple(v):
    m = SEMVER.match(v or "")
    return tuple(int(x) for x in m.groups()) if m else None


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def python_exe():
    """Interpreter for test and lint runs: AGRILENS_GOV_PYTHON if set, else the repository .venv, else the current one."""
    if os.environ.get("AGRILENS_GOV_PYTHON") and os.path.exists(os.environ["AGRILENS_GOV_PYTHON"]):
        return os.environ["AGRILENS_GOV_PYTHON"]
    for cand in (os.path.join(ROOT, ".venv", "Scripts", "python.exe"), os.path.join(ROOT, ".venv", "bin", "python")):
        if os.path.exists(cand):
            return cand
    return sys.executable


def matches(path, patterns):
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) for p in patterns)


def area_of(path, rules):
    for a in rules["areas"]:
        for p in a["paths"]:
            if path == p or (p.endswith("/") and path.startswith(p)):
                return a
    if path.endswith(".md"):
        return next(a for a in rules["areas"] if a["name"] == "documentation")
    return {"name": "other", "paths": [], "kind": "functional", "version_relevant": False, "docs": [], "tests": []}


def fill(path, version):
    return path.replace("{version}", version)


class Report:
    def __init__(self, title):
        self.title, self.rows = title, []

    def add(self, section, name, status, detail=""):
        self.rows.append({"section": section, "check": name, "status": status, "detail": str(detail)})

    @property
    def failed(self):
        return [r for r in self.rows if r["status"] == FAIL]

    def verdict(self):
        return FAIL if self.failed else PASS

    def render(self):
        lines = [f"AGRILENS {self.title}", "-" * 100]
        width = max([len(r["section"]) for r in self.rows] + [10])
        for r in self.rows:
            d = r["detail"].replace("\n", "\n" + " " * (width + 46))
            lines.append(f"{r['status']:<5} {r['section']:<{width}} {r['check']:<38} {d}")
        n = {s: sum(1 for r in self.rows if r["status"] == s) for s in (PASS, FAIL, WARN, SKIP)}
        lines += ["-" * 100, f"RESULT: {self.verdict()}  ({n[PASS]} pass, {n[FAIL]} fail, {n[WARN]} warn, {n[SKIP]} skipped)"]
        return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------- changes
def changed_files(mode):
    """mode 'staged': files in the index that differ from HEAD; 'worktree': staged + unstaged + untracked (not ignored)."""
    if mode == "staged":
        out = git("diff", "--cached", "--name-status", "-z", "--no-renames")
        parts = [p for p in out.split("\0") if p]
        return [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]
    files = {}
    for args in (("diff", "--name-status", "-z", "--no-renames", "HEAD"),):
        parts = [p for p in git(*args).split("\0") if p]
        for i in range(0, len(parts) - 1, 2):
            files[parts[i + 1]] = parts[i]
    for p in git("ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if p:
            files[p] = "A"
    return [(s, p) for p, s in sorted(files.items())]


def added_lines(mode, path):
    """Lines added by the change: staged diff, or (worktree) diff against HEAD; an untracked file counts as wholly added."""
    if mode != "staged" and not git("ls-files", "--", path).strip():
        return (read_text(path) or "").splitlines()
    out = git(*(["diff", "--cached", "-U0", "--", path] if mode == "staged" else ["diff", "HEAD", "-U0", "--", path]))
    return [ln[1:] for ln in out.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def diff_text(mode, path):
    return git(*(["diff", "--cached", "-U3", "--", path] if mode == "staged" else ["diff", "HEAD", "-U3", "--", path]))


def new_change_ids(mode):
    rules = load_rules()
    reg = rules["change_register"]
    return re.findall(r"^### (CR-\d{4})", "\n".join(added_lines(mode, reg)), re.M)


# -------------------------------------------------------------------------------------------------------------- version
def version_info(source="worktree"):
    rules = load_rules()
    v = rules["version"]
    src = read_text(v["source_file"], source) or ""
    pkg_src = read_text(f"{v['package_dir']}/main.py", source) or ""
    return {"source": src, "version": const(src, v["constant"]), "package_version": const(pkg_src, v["constant"]), "package_source": pkg_src}


def load_package_builder():
    rules = load_rules()
    path = os.path.join(ROOT, rules["version"]["package_builder"])
    spec = importlib.util.spec_from_file_location("agl_build_device_package", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # module level only defines constants and functions
    return mod


def norm(b):
    return b.replace(b"\r\n", b"\n") if b is not None else None


def package_drift(source):
    """Source files of the device package whose content differs from the committed package copy."""
    rules = load_rules()
    pkg = rules["version"]["package_dir"]
    builder = load_package_builder()
    drift = []
    for s_rel, d_rel in builder.SOURCES:
        a, b = norm(read_bytes(s_rel, source)), norm(read_bytes(f"{pkg}/{d_rel}", source))
        if a != b:
            drift.append(s_rel)
    return drift


def check_version(rep, source="worktree"):
    rules = load_rules()
    vr = rules["version"]
    info = version_info(source)
    src, v, p = info["source"], info["version"], info["package_version"]
    sec = "version"
    if not vtuple(v):
        rep.add(sec, "APP_VERSION is semantic X.Y.Z", FAIL, f"{vr['source_file']}: APP_VERSION = {v!r}")
        return info
    rep.add(sec, "APP_VERSION is semantic X.Y.Z", PASS, f"{v} ({vr['source_file']}, authoritative)")
    for name, pattern in vr["derived_constants"].items():
        want, got = fill(pattern, v), const(src, name)
        rep.add(sec, f"{name} derived from version", PASS if got == want else FAIL, got if got == want else f"{got!r}, expected {want!r}")
    missing = [c for c in vr["required_constants"] if not const(src, c) or const(src, c) == "UNSET"]
    rep.add(sec, "identity constants present", FAIL if missing else PASS, ", ".join(missing) or "BUILD_TIMESTAMP, MODEL_*, DATASET_VERSION set")
    for f in vr["marker_files"]:
        txt = read_text(f, source)
        marks = VERSION_MARK.findall(txt or "")
        if txt is None:
            rep.add(sec, f"version marker in {f}", FAIL, "file missing")
        elif not marks:
            rep.add(sec, f"version marker in {f}", FAIL, "no <!-- agl:version --> marker")
        else:
            bad = [m for m in marks if m.strip() != v]
            rep.add(sec, f"version marker in {f}", FAIL if bad else PASS, f"shows {bad}, source is {v}" if bad else v)
    notes = fill(vr["release_notes"], v)
    rep.add(sec, "release notes for this version", PASS if read_text(notes, source) is not None else FAIL, notes)
    # Generated OTA package: may lag the source between releases, never lead it; equal versions require equal content
    if not vtuple(p):
        rep.add(sec, "published package version", FAIL, f"{vr['package_dir']}/main.py APP_VERSION = {p!r}")
        return info
    drift = package_drift(source)
    if vtuple(p) > vtuple(v):
        rep.add(sec, "source version >= package version", FAIL, f"package {p} is newer than source {v}")
    elif drift and vtuple(v) == vtuple(p):
        rep.add(sec, "version incremented for shipped changes", FAIL,
                f"{len(drift)} shipped source file(s) differ from package {p} but APP_VERSION is still {v}: {', '.join(drift[:6])}. "
                f"Run: python tools/governance/agl_governance.py bump <patch|minor|major> --reason ...")
    elif drift:
        rep.add(sec, "version incremented for shipped changes", PASS, f"source {v} > package {p}; {len(drift)} file(s) await the next package build")
    else:
        rep.add(sec, "package matches source", PASS, f"source {v}, package {p}, shipped files identical")
    rec = fill(vr["release_record"], p)
    rec_txt = read_text(rec, source)
    try:
        rec_ok = rec_txt is not None and json.loads(rec_txt).get("app_version") == p
    except ValueError:
        rec_ok = False
    rep.add(sec, "release record of the package", PASS if rec_ok else FAIL, rec)
    return info


def check_package_integrity(rep, source="worktree"):
    """SHA256SUMS, RELEASE_MANIFEST.json and model hash of the generated package (read-only)."""
    rules = load_rules()
    pkg = rules["version"]["package_dir"]
    sec = "package"
    sums = read_text(f"{pkg}/SHA256SUMS", source)
    man_txt = read_text(f"{pkg}/RELEASE_MANIFEST.json", source)
    if sums is None or man_txt is None:
        rep.add(sec, "SHA256SUMS / RELEASE_MANIFEST.json", FAIL, "missing")
        return
    bad, listed = [], set()
    for line in sums.splitlines():
        if not line.strip():
            continue
        h, rel = line.split(None, 1)
        rel = rel.strip()
        listed.add(rel)
        b = read_bytes(f"{pkg}/{rel}", source)
        if b is None or sha256_bytes(b) != h:
            bad.append(rel)
    rep.add(sec, "SHA256SUMS verifies", FAIL if bad else PASS, ", ".join(bad[:5]) or f"{len(listed)} files")
    tracked = [p[len(pkg) + 1:] for p in git("ls-files", pkg).splitlines()]
    extra = sorted(set(tracked) - listed - {"SHA256SUMS", "RELEASE_MANIFEST.json", "README_GENERATED.md"})
    rep.add(sec, "no unlisted files in package", FAIL if extra else PASS, ", ".join(extra[:5]) or "only listed files tracked")
    man = json.loads(man_txt)
    psrc = read_text(f"{pkg}/main.py", source) or ""
    onnx = read_bytes(f"{pkg}/agrilens.onnx", source) or b""
    problems = []
    if man.get("app_version") != const(psrc, "APP_VERSION"):
        problems.append("app_version")
    if man.get("release") != const(psrc, "OTA_RELEASE_ID"):
        problems.append("release")
    if not (man.get("model_sha256") == const(psrc, "MODEL_SHA256").lower() == sha256_bytes(onnx)):
        problems.append("model_sha256 / MODEL_SHA256 / agrilens.onnx")
    if man.get("files_sha256", {}).keys() and set(man["files_sha256"]) != listed:
        problems.append("files_sha256 != SHA256SUMS")
    rep.add(sec, "RELEASE_MANIFEST.json consistent", FAIL if problems else PASS, ", ".join(problems) or f"{man.get('release')}, model {man.get('model_sha256', '')[:12]}...")


# ------------------------------------------------------------------------------------------------------------------ model
def model_dir_for(sha):
    for rel in git("ls-files", "models").splitlines():
        if rel.endswith("agrilens.onnx"):
            b = read_bytes(rel)
            if b and sha256_bytes(b) == sha:
                return os.path.dirname(rel)
    return ""


def check_model(rep, deep):
    sec = "model"
    src = read_text(load_rules()["version"]["source_file"]) or ""
    sha = const(src, "MODEL_SHA256").lower()
    mdir = model_dir_for(sha)
    if not mdir:
        rep.add(sec, "MODEL_SHA256 matches a model in models/", FAIL, sha)
        return
    rep.add(sec, "MODEL_SHA256 matches a model in models/", PASS, mdir)
    labels = [ln.strip() for ln in (read_text(f"{mdir}/labels.txt") or "").splitlines() if ln.strip()]
    n = int(const(src, "MODEL_NUM_CLASSES") or 0)
    rep.add(sec, "MODEL_NUM_CLASSES == labels", PASS if n == len(labels) else FAIL, f"{n} / {len(labels)}")
    prod = [ln.strip() for ln in (read_text("models/production/agrilens-24class-4.9.4/labels.txt") or "").splitlines() if ln.strip()]
    rep.add(sec, "class order == production labels", PASS if labels == prod else FAIL, "identical" if labels == prod else "order differs")
    reg = json.loads(read_text("models/manifests/MODEL_REGISTRY.json") or "{}")
    rep.add(sec, "model in MODEL_REGISTRY.json", PASS if any(m.get("sha256") == sha for m in reg.get("models", [])) else FAIL, sha[:12] + "...")
    man_txt = read_text(f"{mdir}/MODEL_MANIFEST.json")
    if man_txt:
        man = json.loads(man_txt)
        ok = man.get("sha256") == sha and man.get("classes") == labels and man.get("model_id") == const(src, "MODEL_ID") and man.get("model_version") == const(src, "MODEL_VERSION")
        rep.add(sec, "MODEL_MANIFEST.json consistent", PASS if ok else FAIL, f"{man.get('model_id')} {man.get('model_version')}")
    calib = read_text("training/evaluation/calibration_1.0.0/FROZEN_GATE_CALIBRATION.json")
    if calib and const(src, "MODEL_VERSION") == "1.0.0":
        c = json.loads(calib)
        flat = json.dumps(c)
        want = {k: float(re.search(rf"^{k}\s*=\s*([\d.]+)", src, re.M).group(1)) for k in ("MODEL_CALIBRATION_CONFIDENCE", "MODEL_CALIBRATION_MARGIN", "MODEL_CALIBRATION_OOD_LOGIT")}
        found = all(re.search(rf"\b{re.escape(str(val))}\b", flat) for val in want.values())
        rep.add(sec, "rejection gates == frozen calibration", PASS if found else FAIL, ", ".join(f"{k.split('_')[-1].lower()} {val}" for k, val in want.items()))
    if not deep:
        return
    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError as e:
        rep.add(sec, "ONNX load / inference sanity", FAIL, f"{e} (install requirements-dev.txt)")
        return
    sess = ort.InferenceSession(os.path.join(ROOT, mdir, "agrilens.onnx"), providers=["CPUExecutionProvider"])
    ishape, oshape = sess.get_inputs()[0].shape, sess.get_outputs()[0].shape
    ok_in = list(ishape[1:]) == [3, 224, 224]
    ok_out = oshape[-1] == len(labels)
    rep.add(sec, "ONNX input 3x224x224 (NCHW)", PASS if ok_in else FAIL, str(ishape))
    rep.add(sec, "ONNX output width == labels", PASS if ok_out else FAIL, str(oshape))
    x = np.zeros((1, 3, 224, 224), dtype=np.float32)
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0]
    rep.add(sec, "inference sanity (finite logits)", PASS if np.isfinite(out).all() and out.shape[-1] == len(labels) else FAIL, f"shape {out.shape}")


# ------------------------------------------------------------------------------------------------------------- repository
def check_repository(rep, mode):
    rules = load_rules()
    sec = "repository"
    if mode == "staged":
        files = changed_files("staged")
        live = [p for s, p in files if s != "D"]
        rep.add(sec, "staged changes", PASS if files else WARN, f"{len(files)} file(s)" if files else "nothing staged")
    else:
        live = [p for p in git("ls-files").splitlines() if os.path.exists(os.path.join(ROOT, p))]
        dirty = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]
        rep.add(sec, "working tree clean", WARN if dirty else PASS, f"{len(dirty)} uncommitted entr(y/ies)" if dirty else "clean")
        untracked = [p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p]
        junk_u = [p for p in untracked if matches(p, rules["junk_patterns"])]
        rep.add(sec, "no stray untracked files", WARN if junk_u else PASS, ", ".join(junk_u[:6]) or "none")
    src_mode = "index" if mode == "staged" else "worktree"
    junk = [p for p in live if matches(p, rules["junk_patterns"])]
    rep.add(sec, "no temporary/debug/generated junk", FAIL if junk else PASS, ", ".join(junk[:8]) or "none")
    big = []
    for p in live:
        b = read_bytes(p, src_mode)
        if b is not None and len(b) > rules["large_file_bytes"] and not matches(p, rules["large_file_allowed"]):
            big.append(f"{p} ({len(b) // 1_000_000} MB)")
    rep.add(sec, "no large unintended artefacts", FAIL if big else PASS, ", ".join(big) or f"limit {rules['large_file_bytes'] // 1_000_000} MB (models allowed)")
    if mode == "staged":
        frozen = [p for p in live if area_of(p, rules)["kind"] == "frozen"]
        rep.add(sec, "frozen artefacts untouched", WARN if frozen else PASS, ("changed: " + ", ".join(frozen[:6]) + " (needs an approved exception in the change register)") if frozen else "none changed")
        gen = [p for p in live if area_of(p, rules)["kind"] == "generated"]
        if gen:
            rep.add(sec, "generated package changed via builder", WARN, f"{len(gen)} file(s) in AGRILENS_RaspberryPi/ staged; this publishes on the next push to main (integrity checked below)")
    # Text hygiene: encoding, BOM, mojibake, line endings, secrets, local paths
    exts = tuple(rules["text_extensions"])
    moj = re.compile(rules["mojibake_pattern"])
    secrets = [re.compile(s) for s in rules["secret_patterns"]]
    allow = [a["line"] for a in rules["secret_allowlist"]]
    localp = [re.compile(s) for s in rules["local_path_patterns"]]
    bom_ok = {e["path"] for e in rules.get("bom_exceptions", [])}
    enc_bad, bom, moji, crlf, sec_hits, path_hits, email_hits = [], [], [], [], [], [], []
    for p in live:
        if not p.endswith(exts) and not p.rsplit("/", 1)[-1].startswith("."):
            continue
        b = read_bytes(p, src_mode)
        if b is None:
            continue
        if b.startswith(b"\xef\xbb\xbf") and p not in bom_ok:
            bom.append(p)
        try:
            txt = b.decode("utf-8")
        except UnicodeDecodeError:
            enc_bad.append(p)
            continue
        if b"\r\n" in b and matches(p, rules["lf_required"]):
            crlf.append(p)
        lines = added_lines("staged", p) if mode == "staged" else txt.splitlines()
        if moj.search("\n".join(lines)):
            moji.append(p)
        for ln in lines:
            if any(a in ln for a in allow):
                continue
            if any(s.search(ln) for s in secrets):
                sec_hits.append(p)
                break
        if mode == "staged":
            if any(lp.search(ln) for ln in lines for lp in localp):
                path_hits.append(p)
            if any(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", ln) and "noreply" not in ln and not ln.lstrip().startswith(("git@", "#")) for ln in lines):
                email_hits.append(p)
    rep.add(sec, "UTF-8 encoding", FAIL if enc_bad else PASS, ", ".join(enc_bad[:6]) or "all text files decode as UTF-8")
    rep.add(sec, "no byte-order mark", FAIL if bom else PASS, ", ".join(bom[:6]) or "none")
    rep.add(sec, "no malformed characters (mojibake)", (FAIL if mode == "staged" else WARN) if moji else PASS, ", ".join(moji[:6]) or "none")
    rep.add(sec, "LF line endings where required", FAIL if crlf else PASS, ", ".join(crlf[:6]) or "*.sh, *.py, AGRILENS_RaspberryPi/*")
    rep.add(sec, "no secrets or credentials", FAIL if sec_hits else PASS, ", ".join(sorted(set(sec_hits))[:6]) or "none (allow-listed: kiosk Admin PIN)")
    if mode == "staged":
        rep.add(sec, "no local machine paths added", WARN if path_hits else PASS, ", ".join(path_hits[:6]) or "none")
        rep.add(sec, "no personal data (e-mail) added", WARN if email_hits else PASS, ", ".join(email_hits[:6]) or "none")
        # cr-at-eol: files stored byte-for-byte with CRLF (`-text` in .gitattributes, e.g. models/**) are not trailing whitespace.
        # Per-invocation option only; the repository's git configuration is not changed.
        code, out, _ = run(["git", "-c", "core.whitespace=cr-at-eol", "diff", "--cached", "--check"])
        rep.add(sec, "whitespace / conflict markers", FAIL if code != 0 else PASS, out.strip().splitlines()[0] if code != 0 and out.strip() else "clean")


# -------------------------------------------------------------------------------------------------------------- code
def bash_exe():
    for cand in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"):
        if cand and os.path.exists(cand) and "System32" not in cand:
            return cand
    return ""


def check_code(rep, mode):
    sec = "code"
    if mode == "staged":
        files = [p for s, p in changed_files("staged") if s != "D"]
    else:
        files = git("ls-files").splitlines()
    py = [p for p in files if p.endswith(".py") and os.path.exists(os.path.join(ROOT, p))]
    sh = [p for p in files if p.endswith(".sh") and os.path.exists(os.path.join(ROOT, p))]
    js = [p for p in files if p.endswith(".json") and os.path.exists(os.path.join(ROOT, p))]
    bad = []
    tmp = os.path.join(tempfile.gettempdir(), "agl_gov_compile.pyc")
    for p in py:
        try:
            py_compile.compile(os.path.join(ROOT, p), cfile=tmp, doraise=True)
        except py_compile.PyCompileError as e:
            bad.append(f"{p}: {str(e).splitlines()[-1]}")
    rep.add(sec, "Python syntax", FAIL if bad else PASS, "\n".join(bad[:5]) or f"{len(py)} file(s) compile")
    if py:
        code, out, err = run([python_exe(), "-m", "ruff", "check", "--force-exclude", *py] if mode == "staged" else [python_exe(), "-m", "ruff", "check", "."], env=clean_env())
        if code == 127 or "No module named ruff" in err:
            rep.add(sec, "ruff lint", FAIL, "ruff not installed: python -m venv .venv && .venv pip install -r requirements-dev.txt")
        else:
            rep.add(sec, "ruff lint", PASS if code == 0 else FAIL, "clean" if code == 0 else "\n".join((out + err).strip().splitlines()[-6:]))
    else:
        rep.add(sec, "ruff lint", SKIP, "no Python files")
    bash = bash_exe()
    if sh and bash:
        bad_sh = []
        for p in sh:
            code, _, err = run([bash, "-n", p])
            if code != 0:
                bad_sh.append(f"{p}: {err.strip().splitlines()[-1] if err.strip() else code}")
        rep.add(sec, "shell syntax (bash -n)", FAIL if bad_sh else PASS, "\n".join(bad_sh[:5]) or f"{len(sh)} script(s)")
    elif sh:
        rep.add(sec, "shell syntax (bash -n)", WARN, "bash not found")
    bad_js = []
    for p in js:
        try:
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            bad_js.append(f"{p}: {e}")
    if js:
        rep.add(sec, "JSON syntax", FAIL if bad_js else PASS, "\n".join(bad_js[:5]) or f"{len(js)} file(s)")
    rep.add(sec, "type checks", SKIP, "no type checker configured in pyproject.toml")


def check_tests(rep, mode, enabled):
    sec = "tests"
    if not enabled:
        rep.add(sec, "pytest", SKIP, "disabled with --no-tests (recorded as not run)")
        return None
    if mode == "staged":
        rules = load_rules()
        files = [p for _, p in changed_files("staged")]
        if files and all(area_of(p, rules)["kind"] == "documentation" for p in files):
            rep.add(sec, "pytest", SKIP, "documentation-only change; tests not applicable")
            return None
    t0 = time.time()
    # addopts is overridden so that exactly one -q applies and pytest prints its summary line
    code, out, err = run([python_exe(), "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider", "-q", "-rfE"], timeout=1800, env=clean_env())
    text = (out + err).strip().splitlines()
    summary = next((ln.strip("= ") for ln in reversed(text) if re.search(r"\d+ (passed|failed|error)", ln)), "")
    if "No module named pytest" in err:
        rep.add(sec, "pytest", FAIL, "pytest not installed (requirements-dev.txt)")
        return None
    status = PASS if code == 0 else FAIL
    detail = f"{summary or 'exit ' + str(code)} in {time.time() - t0:.0f}s"
    if code != 0:
        detail += "\n" + "\n".join([ln for ln in text if ln.startswith(("FAILED", "ERROR"))][:8])
    rep.add(sec, "pytest (unit, integration, OTA, rollback, camera, model contract)", status, detail)
    return {"command": "pytest -q", "exit": code, "summary": summary}


def check_packaging(rep, deep):
    sec = "packaging"
    rules = load_rules()
    src = read_text(rules["version"]["source_file"]) or ""
    mdir = model_dir_for(const(src, "MODEL_SHA256").lower())
    if not mdir:
        rep.add(sec, "package build", FAIL, "no model matches MODEL_SHA256")
        return
    code, out, err = run([python_exe(), rules["version"]["package_builder"], "--model-dir", mdir, "--check-only"], env=clean_env())
    rep.add(sec, "builder pre-checks (--check-only)", PASS if code == 0 else FAIL, (out + err).strip().splitlines()[-1] if (out + err).strip() else f"exit {code}")
    if not deep:
        return
    # Build in a temporary copy: the committed AGRILENS_RaspberryPi/ is never touched
    pkg = rules["version"]["package_dir"]
    with tempfile.TemporaryDirectory(prefix="agl_pkg_") as tmp:
        for rel in ("application", "deployment", mdir, "models/production", pkg):
            s = os.path.join(ROOT, rel)
            if os.path.exists(s):
                shutil.copytree(s, os.path.join(tmp, rel), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        code, out, err = run([python_exe(), os.path.join(tmp, rules["version"]["package_builder"]), "--model-dir", mdir], cwd=tmp, env=clean_env())
        if code != 0:
            rep.add(sec, "package build (temporary copy)", FAIL, (out + err).strip()[-400:])
            return
        rep.add(sec, "package build (temporary copy)", PASS, "build succeeded; repository package untouched")
        info = version_info()
        built = {}
        for dp, _, fs in os.walk(os.path.join(tmp, pkg)):
            for f in fs:
                p = os.path.join(dp, f)
                built[os.path.relpath(p, os.path.join(tmp, pkg)).replace(os.sep, "/")] = sha256_bytes(open(p, "rb").read())
        if info["version"] == info["package_version"]:
            committed = {p[len(pkg) + 1:]: sha256_bytes(read_bytes(p) or b"") for p in git("ls-files", pkg).splitlines()}
            diff = sorted(k for k in set(built) | set(committed) if built.get(k) != committed.get(k))
            rep.add(sec, "reproducible build == committed package", FAIL if diff else PASS, ", ".join(diff[:6]) or f"{len(built)} files byte-identical")
        else:
            rep.add(sec, "reproducible build == committed package", SKIP, f"source {info['version']} is ahead of package {info['package_version']} (development); the package is rebuilt at release time")
        unwanted = [k for k in built if matches(k, rules["junk_patterns"])]
        rep.add(sec, "no unwanted files in package", FAIL if unwanted else PASS, ", ".join(unwanted) or f"{len(built)} files")


# --------------------------------------------------------------------------------------------------------- documentation
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CODE_PATH = re.compile(r"`((?:documentation|deployment|training|tools|tests|models|datasets|application|AGRILENS_RaspberryPi|archive)/[^`*<>{}\s]+?)`")


def doc_references(rel, text):
    """Relative link targets and backticked repository paths in a Markdown document."""
    refs = []
    base = os.path.dirname(rel)
    for m in LINK.finditer(text):
        t = m.group(1).split("#", 1)[0]
        if not t or re.match(r"^[a-z]+:", t):
            continue
        refs.append(os.path.normpath(os.path.join(base, t)).replace(os.sep, "/"))
    for m in CODE_PATH.finditer(text):
        t = m.group(1).rstrip(".,;:)")
        if "..." in t or "…" in t:
            continue
        refs.append(t.rstrip("/"))
    return refs


def path_exists(rel):
    return os.path.exists(os.path.join(ROOT, rel)) or bool(git("ls-files", rel).strip())


def check_documentation(rep, mode):
    rules = load_rules()
    sec = "documentation"
    src = "index" if mode == "staged" else "worktree"
    v = version_info(src)["version"]
    # HOW_TO index
    for name, status, detail in index_problems(rules, v, src):
        rep.add(sec, name, status, detail)
    # Broken references in current (canonical) documents
    broken = []
    for d in rules["current_docs"]:
        txt = read_text(d, src)
        if txt is None:
            broken.append(f"{d}: missing")
            continue
        for r in doc_references(d, txt):
            if not path_exists(r) and not r.startswith(("D:", "C:")):
                broken.append(f"{d} -> {r}")
    rep.add(sec, "no broken references (current docs)", FAIL if broken else PASS, "\n".join(broken[:10]) or f"{len(rules['current_docs'])} documents")
    # Unindexed documents
    indexed = {e["path"] for e in rules["documentation_index"]}
    md = [p for p in git("ls-files", "*.md").splitlines() if p.startswith("documentation/") and p not in indexed]
    rep.add(sec, "every documentation/ file indexed", WARN if md else PASS, ", ".join(md[:8]) or "all indexed in HOW_TO.md")
    # Future version references in current docs
    future = []
    for d in rules["current_docs"]:
        for m in re.finditer(r"\b(?:AGRILENS[ -]|v)(\d+\.\d+\.\d+)\b", read_text(d, src) or ""):
            if vtuple(m.group(1)) and vtuple(v) and vtuple(m.group(1)) > vtuple(v) and m.group(1) != "5.0.1":
                future.append(f"{d}: {m.group(0)}")
    rep.add(sec, "no references to unreleased versions", FAIL if future else PASS, ", ".join(future[:6]) or f"none above {v} (5.0.1 is the prepared rollback release)")
    if mode != "staged":
        return
    # Change register and documentation obligations for the staged change
    files = [p for _, p in changed_files("staged")]
    functional = [p for p in files if area_of(p, rules)["kind"] in ("functional", "generated", "frozen")]
    ids = new_change_ids("staged")
    entries = {e["id"]: e for e in parse_register(read_text(rules["change_register"], "index") or "")}
    if functional:
        rep.add(sec, "change register entry for this change", PASS if ids else FAIL,
                ", ".join(ids) if ids else f"{len(functional)} functional file(s) staged; add an entry: python tools/governance/agl_governance.py register new --title ... --category ...")
    elif files:
        rep.add(sec, "change register entry for this change", PASS if ids else WARN, ", ".join(ids) or "documentation-only change without an entry")
    for cid in ids:
        e = entries.get(cid)
        if not e:
            rep.add(sec, f"{cid} complete", FAIL, "entry not parseable")
            continue
        missing = [f for f in REGISTER_FIELDS if not e["fields"].get(f, "").strip() or e["fields"][f].strip().startswith("TODO")]
        rep.add(sec, f"{cid} complete", FAIL if missing else PASS, ("missing: " + ", ".join(missing)) if missing else e["title"])
    needed = obligations(files, mode="staged")["docs"]
    staged_docs = set(files)
    declared_none = any(entries.get(c, {}).get("fields", {}).get("Documentation updated", "").lower().startswith("none required") for c in ids)
    if functional and needed and not (staged_docs & set(needed)) and not declared_none:
        rep.add(sec, "relevant documentation updated", FAIL, "none of these staged: " + ", ".join(sorted(needed)[:6]) + " (or state 'None required: <reason>' in the register entry)")
    elif functional:
        rep.add(sec, "relevant documentation updated", PASS, ", ".join(sorted(staged_docs & set(needed))[:6]) or "declared not required in the register entry")


def index_problems(rules, v, source="worktree"):
    out = []
    how = rules["how_to"]
    raw = read_bytes(how, source)
    if raw is None:
        return [("HOW_TO.md present", FAIL, how)]
    if raw.startswith(b"\xef\xbb\xbf"):
        out.append(("HOW_TO.md has no BOM", FAIL, "BOM present"))
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return [("HOW_TO.md is UTF-8", FAIL, str(e))]
    if re.search(rules["mojibake_pattern"], txt):
        out.append(("HOW_TO.md has no malformed characters", FAIL, "mojibake found"))
    if INDEX_BEGIN not in txt or INDEX_END not in txt:
        return out + [("HOW_TO.md index markers", FAIL, "index markers missing")]
    block = txt.split(INDEX_BEGIN, 1)[1].split(INDEX_END, 1)[0]
    if block.strip() != render_index(rules).strip():
        out.append(("HOW_TO.md index up to date", FAIL, "differs from governance_rules.json; run: agl_governance.py index --write"))
    else:
        out.append(("HOW_TO.md index up to date", PASS, f"{len(rules['documentation_index'])} entries"))
    bad = []
    for e in rules["documentation_index"]:
        p = e["path"]
        if not path_exists(p):
            bad.append(f"{p}: missing")
            continue
        b = read_bytes(p, source) or read_bytes(p) or b""
        if b.startswith(b"\xef\xbb\xbf") and p not in {x["path"] for x in rules.get("bom_exceptions", [])}:
            bad.append(f"{p}: BOM")
        try:
            b.decode("utf-8")
        except UnicodeDecodeError:
            bad.append(f"{p}: not UTF-8")
        if p != p.strip() or "\\" in p:
            bad.append(f"{p}: malformed path")
    out.append(("index entries exist, UTF-8, no BOM", FAIL if bad else PASS, ", ".join(bad[:6]) or "all entries valid"))
    return out


def render_index(rules):
    groups = [("canonical", "Current documentation"), ("record", "Release, evaluation and decision records (do not edit)"),
              ("reference", "Release-specific references"), ("history", "History (superseded, kept for traceability)"), ("generated", "Generated")]
    lines = []
    for key, title in groups:
        entries = [e for e in rules["documentation_index"] if e["status"] == key]
        if not entries:
            continue
        lines += ["", f"**{title}**", "", "| Document | Topic |", "|---|---|"]
        for e in entries:
            lines.append(f"| [`{e['path']}`]({e['path']}) | {e['topic']} |")
    return "\n".join(lines) + "\n"


def write_index():
    rules = load_rules()
    p = os.path.join(ROOT, rules["how_to"])
    with open(p, encoding="utf-8") as f:
        txt = f.read()
    head, rest = txt.split(INDEX_BEGIN, 1)
    _, tail = rest.split(INDEX_END, 1)
    new = head + INDEX_BEGIN + "\n" + render_index(rules) + INDEX_END + tail
    if new != txt:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        return True
    return False


# --------------------------------------------------------------------------------------------------------- impact / docs
def obligations(files, mode):
    rules = load_rules()
    v = version_info("index" if mode == "staged" else "worktree")["version"]
    areas, docs, tests, topics, version_needed = {}, set(), set(), set(), False
    for p in files:
        a = area_of(p, rules)
        areas.setdefault(a["name"], []).append(p)
        docs.update(fill(d, v) for d in a["docs"])
        tests.update(a["tests"])
        version_needed |= a["version_relevant"] and a["kind"] != "generated"
        if p.endswith(".py") and a["kind"] == "functional":
            body = "\n".join(ln for ln in diff_text(mode, p).splitlines() if ln[:1] in "+-@")
            for t in rules["code_topics"]:
                if re.search(t["pattern"], body):
                    topics.add(t["topic"])
                    docs.update(fill(d, v) for d in t["docs"])
                    tests.update(t["tests"])
    docs.discard("")
    return {"areas": areas, "docs": sorted(docs), "tests": sorted(tests), "topics": sorted(topics), "version_needed": version_needed, "version": v}


def stale_comment_hints(mode, files):
    """Changed lines that mention an older application version or a superseded status."""
    v = vtuple(version_info()["version"])
    hints = []
    for p in files:
        # history documents and the governance tool itself legitimately contain old versions and status words
        if not p.endswith((".py", ".sh", ".md")) or p.startswith(("documentation/history/", "documentation/governance/", "tools/governance/")):
            continue
        for ln in added_lines(mode, p):
            for m in re.finditer(r"\bv?(\d+\.\d+\.\d+)\b", ln):
                t = vtuple(m.group(1))
                if t and v and t < v and t[0] >= 4 and ("current" in ln.lower() or "latest" in ln.lower()):
                    hints.append(f"{p}: '{ln.strip()[:90]}'")
            if re.search(r"not (yet )?published|release candidate", ln, re.I):
                hints.append(f"{p}: status wording '{ln.strip()[:90]}'")
    return hints[:10]


def cmd_impact(args):
    mode = "staged" if args.staged else "worktree"
    files = [p for _, p in changed_files(mode)]
    if not files:
        print("AGRILENS impact: no uncommitted changes.")
        return 0
    ob = obligations(files, mode)
    info = version_info()
    print(f"AGRILENS change impact ({mode}): {len(files)} file(s)")
    for name, fs in ob["areas"].items():
        print(f"  area {name}: {', '.join(fs[:6])}{' ...' if len(fs) > 6 else ''}")
    if ob["topics"]:
        print(f"  code topics touched: {', '.join(ob['topics'])}")
    drift = package_drift("worktree")
    if ob["version_needed"]:
        if vtuple(info["version"]) and vtuple(info["package_version"]) and vtuple(info["version"]) <= vtuple(info["package_version"]) and drift:
            print(f"  VERSION: shipped files changed but APP_VERSION is still {info['version']} (= package). Decide the increment:")
            print("           patch = bug fix / non-functional; minor = new backward-compatible feature or UI change; major = breaking.")
            print("           python tools/governance/agl_governance.py bump <patch|minor|major> --reason \"...\"")
        else:
            print(f"  VERSION: {info['version']} (package {info['package_version']}); propagation via bump/markers is consistent")
    else:
        print(f"  VERSION: no application version change required for these areas (application {info['version']})")
    print("  DOCS to verify/update: " + (", ".join(d for d in ob["docs"]) or "none"))
    print("  TESTS to run/extend: " + (", ".join(ob["tests"]) or "none mapped"))
    for h in stale_comment_hints(mode, files):
        print(f"  STALE? {h}")
    rules = load_rules()
    if not new_change_ids(mode) and any(area_of(p, rules)["kind"] != "documentation" for p in files):
        print("  REGISTER: no new change-register entry yet (python tools/governance/agl_governance.py register new ...)")
    return 0


def cmd_docs(args):
    files = [p for _, p in changed_files("worktree")]
    rules = load_rules()
    functional = [p for p in files if area_of(p, rules)["kind"] != "documentation"]
    if not functional:
        if not args.hook:
            print("AGRILENS docs: no uncommitted functional changes; nothing to verify.")
        return 0
    ob = obligations(files, "worktree")
    touched = set(files)
    pending = [d for d in ob["docs"] if d not in touched]
    done = [d for d in ob["docs"] if d in touched]
    print(f"[AGRILENS documentation governance] {len(functional)} uncommitted functional file(s) in: {', '.join(ob['areas'])}.")
    if ob["topics"]:
        print(f"Topics: {', '.join(ob['topics'])}.")
    if done:
        print("Already updated: " + ", ".join(done))
    if pending:
        print("Verify and update in this task (installation, user guide/HOW_TO, architecture, configuration, release notes, troubleshooting as relevant): " + ", ".join(pending))
    if not new_change_ids("worktree"):
        print("Change register: no new entry yet in documentation/CHANGE_REGISTER.md.")
    return 0


# --------------------------------------------------------------------------------------------------------------- register
REGISTER_FIELDS = ["Date", "Application version", "Category", "Description", "Reason", "Files affected", "Tests executed", "Test outcome", "Documentation updated", "Known risks", "Commit"]


def parse_register(text):
    entries = []
    for m in re.finditer(r"^### (CR-\d{4}) [—-] (.+?)\n(.*?)(?=^### CR-|\Z)", text, re.M | re.S):
        fields = {}
        for row in re.finditer(r"^\| ([^|]+?) \| (.*) \|\s*$", m.group(3), re.M):
            k, val = row.group(1).strip(), row.group(2).strip()
            if k not in ("Field", "---"):
                fields[k] = val
        entries.append({"id": m.group(1), "title": m.group(2).strip(), "fields": fields})
    return entries


def check_register_file(rep):
    rules = load_rules()
    txt = read_text(rules["change_register"])
    sec = "register"
    if txt is None:
        rep.add(sec, "change register present", FAIL, rules["change_register"])
        return
    entries = parse_register(txt)
    ids = [e["id"] for e in entries]
    rep.add(sec, "entries parse, ids unique and ascending", PASS if ids == sorted(set(ids)) and ids else FAIL, f"{len(ids)} entries, last {ids[-1] if ids else '-'}")
    cats = set(rules["change_categories"])
    bad = [f"{e['id']}: {c.strip()}" for e in entries for c in e["fields"].get("Category", "").split(";") if c.strip() and c.strip() not in cats]
    rep.add(sec, "categories valid", FAIL if bad else PASS, ", ".join(bad[:5]) or ", ".join(sorted(cats)))
    inc = [e["id"] for e in entries if any(not e["fields"].get(f, "").strip() for f in REGISTER_FIELDS)]
    rep.add(sec, "entries complete", FAIL if inc else PASS, ", ".join(inc) or "all fields present")
    pend = [e["id"] for e in entries if e["fields"].get("Commit", "").lower().startswith("pending")]
    rep.add(sec, "commit ids recorded", WARN if len(pend) > 1 else PASS, (", ".join(pend) + " pending (run: register sync)") if pend else "all recorded")


def cmd_register(args):
    rules = load_rules()
    path = os.path.join(ROOT, rules["change_register"])
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    entries = parse_register(txt)
    if args.action == "new":
        cats = [c.strip() for c in args.category.split(";")]
        unknown = [c for c in cats if c not in rules["change_categories"]]
        if unknown:
            print(f"Unknown category {unknown}; use one of: {', '.join(rules['change_categories'])}")
            return 2
        nxt = f"CR-{(max([int(e['id'][3:]) for e in entries] or [0]) + 1):04d}"
        v = version_info()["version"]
        files = [p for _, p in changed_files("worktree")]
        body = [f"\n### {nxt} — {args.title}\n", "| Field | Value |", "|---|---|", f"| Date | {datetime.date.today().isoformat()} |",
                f"| Application version | {v} (TODO: state the increment and rationale, or 'unchanged: <reason>') |", f"| Category | {'; '.join(cats)} |",
                "| Description | TODO |", "| Reason | TODO |", f"| Files affected | {', '.join(files[:12]) + (' ...' if len(files) > 12 else '') or 'TODO'} |",
                "| Tests executed | TODO (command) |", "| Test outcome | TODO (actual result; never assumed) |", "| Documentation updated | TODO (files, or 'None required: <reason>') |",
                "| Known risks | TODO |", "| Commit | pending |", ""]
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(body))
        print(f"Added {nxt} to {rules['change_register']}; replace every TODO before committing.")
        return 0
    if args.action == "sync":
        changed = 0
        for e in entries:
            if not e["fields"].get("Commit", "").lower().startswith("pending"):
                continue
            log = git("log", "--format=%h", "--reverse", "-S", f"### {e['id']} ", "--", rules["change_register"]).split()
            if log:
                txt = re.sub(rf"(^### {e['id']} .*?^\| Commit \| )pending[^|]*(\|)", rf"\g<1>{log[0]} \g<2>", txt, count=1, flags=re.M | re.S)
                changed += 1
        if changed:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(txt)
        print(f"register sync: {changed} commit id(s) filled")
        return 0
    for e in entries:
        print(f"{e['id']}  {e['fields'].get('Date', '')}  {e['fields'].get('Commit', '')[:10]:<10}  {e['title']}")
    return 0


# -------------------------------------------------------------------------------------------------------------- bump
def cmd_bump(args):
    rules = load_rules()
    vr = rules["version"]
    src_path = os.path.join(ROOT, vr["source_file"])
    with open(src_path, encoding="utf-8", newline="") as f:
        src = f.read()
    cur = const(src, vr["constant"])
    head = const(read_text(vr["source_file"], "HEAD") or "", vr["constant"])
    t = vtuple(cur)
    if not t:
        print(f"APP_VERSION {cur!r} is not X.Y.Z")
        return 2
    if vtuple(head) and t > vtuple(head) and not args.force:
        print(f"APP_VERSION is already {cur} (HEAD {head}); this task has been bumped. Use --force to bump again.")
        return 2
    new = {"patch": (t[0], t[1], t[2] + 1), "minor": (t[0], t[1] + 1, 0), "major": (t[0] + 1, 0, 0)}[args.part]
    nv = ".".join(map(str, new))
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " (development build)"
    src2 = re.sub(rf'^({vr["constant"]}\s*=\s*)"[^"]*"', rf'\g<1>"{nv}"', src, count=1, flags=re.M)
    for name, pattern in vr["derived_constants"].items():
        src2 = re.sub(rf'^({name}\s*=\s*)"[^"]*"', rf'\g<1>"{fill(pattern, nv)}"', src2, count=1, flags=re.M)
    src2 = re.sub(r'^(BUILD_TIMESTAMP\s*=\s*)"[^"]*"', rf'\g<1>"{stamp}"', src2, count=1, flags=re.M)
    with open(src_path, "w", encoding="utf-8", newline="") as f:
        f.write(src2)
    touched = [vr["source_file"]]
    for mf in vr["marker_files"]:
        p = os.path.join(ROOT, mf)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                txt = f.read()
            txt2 = VERSION_MARK.sub(f"<!-- agl:version -->{nv}<!-- /agl:version -->", txt)
            if txt2 != txt:
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(txt2)
                touched.append(mf)
    notes = os.path.join(ROOT, fill(vr["release_notes"], nv))
    if not os.path.exists(notes):
        with open(notes, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# AGRILENS {nv} release notes (in development, not published)\n\n| Item | Value |\n|---|---|\n| OTA release id | `{fill(vr['derived_constants']['OTA_RELEASE_ID'], nv)}` |\n"
                    f"| Previous version | {cur} |\n| Increment | {args.part}: {args.reason} |\n| Status | In development. Not built into `AGRILENS_RaspberryPi/`, not published, not deployed. |\n\n"
                    "## What changes for a kiosk\n\n- TODO\n\n## Tests\n\n- TODO (record actual results only)\n\n## Known limitations\n\n- TODO\n")
        touched.append(fill(vr["release_notes"], nv))
    with open(state_path("version_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"), "from": cur, "to": nv, "part": args.part, "reason": args.reason}) + "\n")
    print(f"APP_VERSION {cur} -> {nv} ({args.part}: {args.reason})")
    print("Updated: " + ", ".join(touched))
    print("Not changed (by design): AGRILENS_RaspberryPi/ and release manifests; they are regenerated by deployment/packaging/build_device_package.py at release time.")
    print("Record the increment and its rationale in the change-register entry (field 'Application version').")
    print(f"Add {fill(vr['release_notes'], nv)} to documentation_index in tools/governance/governance_rules.json, then run: agl_governance.py index --write")
    return 0


def cmd_version(_args):
    rules = load_rules()
    info = version_info()
    src = info["source"]
    print(f"authoritative   {rules['version']['source_file']}  APP_VERSION = {info['version']}")
    for c in list(rules["version"]["derived_constants"]) + rules["version"]["required_constants"]:
        print(f"  {c:<16}{const(src, c)}")
    for mf in rules["version"]["marker_files"]:
        print(f"  marker          {mf}: {', '.join(VERSION_MARK.findall(read_text(mf) or '')) or 'none'}")
    print(f"published pkg   {rules['version']['package_dir']}/main.py APP_VERSION = {info['package_version']}")
    print("derived at run time from APP_VERSION: About tooltip, status bar, start-up log line, OTA User-Agent and downgrade guard, rollback folder name")
    print("derived at build time: RELEASE_MANIFEST.json, SHA256SUMS, deployment/release_manifests/AGRILENS-<version>.json")
    return 0


# ------------------------------------------------------------------------------------------------------------- check
def run_check(mode, tests=True):
    rep = Report(f"quality gate ({'pre-commit, staged changes' if mode == 'staged' else 'pre-release, full repository'})")
    src = "index" if mode == "staged" else "worktree"
    check_repository(rep, mode)
    check_version(rep, src)
    check_package_integrity(rep, src)
    check_code(rep, mode)
    check_model(rep, deep=(mode != "staged"))
    check_documentation(rep, mode)
    check_register_file(rep)
    if mode != "staged":
        check_packaging(rep, deep=True)
    else:
        files = [p for _, p in changed_files("staged")]
        rules = load_rules()
        if any(area_of(p, rules)["name"] in ("application", "device-scripts", "packaging", "generated-package", "models") for p in files):
            check_packaging(rep, deep=False)
    tres = check_tests(rep, mode, tests)
    tree = git("write-tree").strip() if mode == "staged" else ""
    record = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "mode": mode, "tree": tree, "verdict": rep.verdict(),
              "version": version_info(src)["version"], "tests": tres, "rows": rep.rows}
    try:
        with open(state_path("last_check.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, indent=1)
    except Exception:
        pass
    return rep


def cmd_check(args):
    mode = "full" if args.full else "staged"
    rep = run_check(mode, tests=not args.no_tests)
    print(rep.render())
    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="\n") as f:
            f.write(rep.render() + "\n")
    return 1 if rep.failed else 0


# --------------------------------------------------------------------------------------------------------------- hooks
def extract_keys(obj, key):
    out = []
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k == key and isinstance(val, str) and val:
                out.append(val)
            else:
                out += extract_keys(val, key)
    elif isinstance(obj, list):
        for x in obj:
            out += extract_keys(x, key)
    return out


def _delegate_print(tool, top, raw):
    """Runs another repository's pretool hook and relays its stdout (permission decision) and stderr."""
    code, out, err = run([sys.executable, tool, "hook-pretool"], cwd=top, input_text=raw, timeout=1800)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return code


def extract_commands(obj):
    out = []
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in ("command", "cmd") and isinstance(val, str):
                out.append(val)
            else:
                out += extract_commands(val)
    elif isinstance(obj, list):
        for x in obj:
            out += extract_commands(x)
    return out


# git global options may precede the subcommand: -C <path>, -c key=value, --git-dir=..., --no-pager, ...
_GIT_OPTS = r"(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|\S+)|--?[A-Za-z][\w-]*(?:=(?:\"[^\"]*\"|\S+))?))*"
GIT_COMMIT = re.compile(r"\bgit" + _GIT_OPTS + r"\s+commit\b(?![^;&|\n]*--dry-run)")
PUBLISH = re.compile(r"\bgit" + _GIT_OPTS + r"\s+push\b|\bgh\s+release\s+create\b|publish_ota_release\.ps1")


def recent_pass_for_tree(tree, max_age=900):
    try:
        with open(state_path("last_check.json"), encoding="utf-8") as f:
            r = json.load(f)
        age = (datetime.datetime.now() - datetime.datetime.fromisoformat(r["time"])).total_seconds()
        return r.get("mode") == "staged" and r.get("tree") == tree and r.get("verdict") == PASS and age < max_age
    except Exception:
        return False


HOOK_BLOCK = 3   # the Kiro hook command maps 3 -> 2 (Kiro's "block"); any other failure, e.g. a missing file, then never blocks the shell


def cmd_hook_pretool(_args):
    """Kiro PreToolUse gate. Exit 0 = allow (stdout may carry an 'ask' decision), HOOK_BLOCK = block (report on stderr)."""
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
        cmds = extract_commands(payload)
    except ValueError:
        payload, cmds = {}, [raw]
    text = "\n".join(cmds)
    # The command may target another repository (tool-call cwd or `git -C <path>`): that repository's own rules apply
    # the tool call's own working directory wins over the session cwd at the top of the Kiro payload
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    cwds = extract_keys(tool_input, "cwd") + extract_keys(payload, "cwd")
    m = re.search(r"\bgit\b[^;&|\n]*?\s-C\s+(?:\"([^\"]*)\"|(\S+))", text)
    target = (m.group(1) or m.group(2)) if m else (cwds[0] if cwds else "")
    if target and (GIT_COMMIT.search(text) or PUBLISH.search(text)):
        base = cwds[0] if (m and cwds and not os.path.isabs(target)) else ""
        code, top, _ = run(["git", "-C", os.path.join(base, target) if base else target, "rev-parse", "--show-toplevel"])
        top = top.strip()
        if code == 0 and top and os.path.normcase(os.path.abspath(top)) != os.path.normcase(os.path.abspath(ROOT)):
            other = os.path.join(top, "tools", "governance", "agl_governance.py")
            if not os.path.exists(other):
                return 0
            return _delegate_print(other, top, raw)
    if PUBLISH.search(text):
        print(json.dumps({"hookSpecificOutput": {"permissionDecision": "ask", "permissionDecisionReason":
              "AGRILENS governance: pushing, tagging or publishing changes GitHub and can trigger OTA on every kiosk. Explicit user approval is required."}}))
        return 0
    if not GIT_COMMIT.search(text):
        return 0
    rep = run_check("staged", tests=True)
    if rep.failed:
        sys.stderr.write(rep.render() + "\n\nAGRILENS pre-commit gate: commit blocked. Fix the FAIL rows above (or record an approved exception) and retry.\n")
        return HOOK_BLOCK
    return 0


def cmd_pre_commit(_args):
    tree = git("write-tree").strip()
    if recent_pass_for_tree(tree):
        print("AGRILENS pre-commit: this exact staged tree passed the quality gate moments ago (Kiro hook); not re-running.")
        return 0
    rep = run_check("staged", tests=True)
    print(rep.render())
    if rep.failed:
        print("\nAGRILENS pre-commit gate: commit blocked.")
        return 1
    return 0


def cmd_post_commit(_args):
    head = git("rev-parse", "HEAD").strip()
    if not head:
        return 0
    rules = load_rules()
    files = [ln for ln in git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", head).splitlines() if ln]
    reg_diff = git("show", head, "--format=", "-U0", "--", rules["change_register"])
    ids = re.findall(r"^\+### (CR-\d{4})", reg_diff, re.M)
    last = {}
    try:
        with open(state_path("last_check.json"), encoding="utf-8") as f:
            last = json.load(f)
    except Exception:
        pass
    tree = git("rev-parse", f"{head}^{{tree}}").strip()
    check = {"verdict": last.get("verdict"), "time": last.get("time"), "tests": last.get("tests"),
             "failed": [r["check"] for r in last.get("rows", []) if r["status"] == FAIL], "warnings": [r["check"] for r in last.get("rows", []) if r["status"] == WARN]} \
        if last.get("tree") == tree else {"verdict": "not run for this tree", "tests": None}
    info = version_info("HEAD")
    note = {"commit": head, "date": git("show", "-s", "--format=%cI", head).strip(), "application_version": info["version"], "package_version": info["package_version"],
            "change_ids": ids, "files_changed": files, "documentation_changed": [p for p in files if area_of(p, rules)["kind"] == "documentation" or p.endswith(".md")],
            "quality_gate": check, "pushed": False}
    code, _, err = run(["git", "notes", f"--ref={NOTES_REF}", "add", "-f", "-m", json.dumps(note, indent=1), head])
    outstanding = []
    if not ids and any(area_of(p, rules)["kind"] != "documentation" for p in files):
        outstanding.append("no change-register entry in this commit")
    if check["verdict"] != PASS:
        outstanding.append(f"quality gate: {check['verdict']}")
    pend = [e["id"] for e in parse_register(read_text(rules["change_register"]) or "") if e["fields"].get("Commit", "").lower().startswith("pending")]
    if pend:
        outstanding.append(f"commit id to backfill for {', '.join(pend)} (register sync, with the next change)")
    print(f"AGRILENS post-commit: {head[:10]} recorded in git notes (ref {NOTES_REF}){'' if code == 0 else ' FAILED: ' + err.strip()}; "
          f"version {info['version']}; change ids {', '.join(ids) or 'none'}; {len(files)} file(s); gate {check['verdict']}. Not pushed.")
    for o in outstanding:
        print(f"  outstanding: {o}")
    return 0


HOOK_SHIM = """#!/bin/sh
# AGRILENS governance {name} hook (installed by tools/governance/agl_governance.py install-git-hooks). Do not edit; edit the tool instead.
ROOT="$(git rev-parse --show-toplevel)"
for PY in "$ROOT/.venv/Scripts/python.exe" "$ROOT/.venv/bin/python" python3 python; do
  if "$PY" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    exec "$PY" "$ROOT/tools/governance/agl_governance.py" {command}
  fi
done
echo "AGRILENS {name}: no Python 3.8+ found; {fallback}" >&2
exit {fallback_code}
"""


def cmd_install_git_hooks(_args):
    hooks = os.path.join(git_dir(), "hooks")
    os.makedirs(hooks, exist_ok=True)
    plan = {"pre-commit": ("pre-commit", "commit blocked", 1), "post-commit": ("post-commit", "commit not recorded", 0)}
    for name, (command, fallback, code) in plan.items():
        p = os.path.join(hooks, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                if "AGRILENS governance" not in f.read():
                    print(f"{p} exists and is not an AGRILENS hook; not overwritten. Merge it by hand.")
                    continue
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(HOOK_SHIM.format(name=name, command=command, fallback=fallback, fallback_code=code))
        try:
            os.chmod(p, 0o755)
        except Exception:
            pass
        print(f"installed {p}")
    return 0


# ---------------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    g = c.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--full", action="store_true")
    c.add_argument("--no-tests", action="store_true")
    c.add_argument("--report")
    i = sub.add_parser("impact")
    i.add_argument("--staged", action="store_true")
    d = sub.add_parser("docs")
    d.add_argument("--hook", action="store_true")
    sub.add_parser("version")
    b = sub.add_parser("bump")
    b.add_argument("part", choices=["patch", "minor", "major"])
    b.add_argument("--reason", required=True)
    b.add_argument("--force", action="store_true")
    x = sub.add_parser("index")
    gx = x.add_mutually_exclusive_group()
    gx.add_argument("--write", action="store_true")
    gx.add_argument("--check", action="store_true")
    r = sub.add_parser("register")
    r.add_argument("action", choices=["new", "sync", "show"])
    r.add_argument("--title")
    r.add_argument("--category")
    for name in ("hook-pretool", "pre-commit", "post-commit", "install-git-hooks"):
        sub.add_parser(name)
    a = ap.parse_args(argv)
    if a.cmd == "register" and a.action == "new" and not (a.title and a.category):
        ap.error("register new needs --title and --category")
    if a.cmd == "index":
        if a.write:
            print("HOW_TO.md index updated" if write_index() else "HOW_TO.md index already up to date")
            return 0
        rules = load_rules()
        probs = index_problems(rules, version_info()["version"])
        for name, status, detail in probs:
            print(f"{status:<5} {name:<40} {detail}")
        return 1 if any(s == FAIL for _, s, _ in probs) else 0
    handlers = {"check": cmd_check, "impact": cmd_impact, "docs": cmd_docs, "version": cmd_version, "bump": cmd_bump, "register": cmd_register,
                "hook-pretool": cmd_hook_pretool, "pre-commit": cmd_pre_commit, "post-commit": cmd_post_commit, "install-git-hooks": cmd_install_git_hooks}
    return handlers[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
