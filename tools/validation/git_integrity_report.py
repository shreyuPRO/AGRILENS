#!/usr/bin/env python3
"""
Git integrity report. Proves a phase did not damage existing work.

Compares the repository now with the Stage 0 backup folder (HEAD.txt, git_status_before.txt,
sha256_worktree_before.txt) and reports:
  * main branch and origin/main still point at the original commit (nothing pushed or merged)
  * every file that existed in the working tree at Stage 0 is byte-identical, unless it was
    deliberately moved with git mv (reported separately)
  * the pre-existing uncommitted changes (3 modified, 9 deleted) are still uncommitted and unstaged
  * no pre-existing uncommitted path appears in any commit made on the work branch
  * what was added, committed, staged and left untracked

Usage: python scripts/git_integrity_report.py --backup <backup folder> [--out report.md]
Exit code 0 = no violation found, 1 = at least one check failed.
"""
import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise SystemExit("git %s failed: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    """Backup files may be UTF-16 (PowerShell redirection) or UTF-8; detect by BOM."""
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig", errors="replace")


def parse_status(text):
    out = {}
    for line in text.splitlines():
        if len(line) > 3:
            out[line[3:].strip().strip('"')] = line[:2]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True)
    ap.add_argument("--out")
    ap.add_argument("--base-branch", default="main")
    ap.add_argument("--allow-modified", nargs="*", default=[], help="pre-existing files whose change is intentional and approved (reported separately)")
    a = ap.parse_args()

    lines, failures = [], []

    def check(name, ok, detail=""):
        lines.append("| %s | %s | %s |" % (name, "PASS" if ok else "**FAIL**", detail))
        if not ok:
            failures.append(name)

    original_head = read_text(os.path.join(a.backup, "HEAD.txt")).strip()
    before_status = parse_status(read_text(os.path.join(a.backup, "git_status_before.txt")))
    before_hash = {}
    for line in read_text(os.path.join(a.backup, "sha256_worktree_before.txt")).splitlines():
        digest, _, path = line.rstrip("\r\n").partition("  ")
        if path:
            before_hash[path] = digest

    branch = git("branch", "--show-current").strip()
    head = git("rev-parse", "HEAD").strip()
    main_head = git("rev-parse", a.base_branch).strip()
    origin = git("rev-parse", "origin/" + a.base_branch, check=False).strip()
    remote_refs = git("for-each-ref", "refs/remotes", "--format=%(refname)")
    commits = git("log", "--oneline", "%s..HEAD" % a.base_branch).strip().splitlines()

    check("%s branch unchanged" % a.base_branch, main_head == original_head, "%s == original %s" % (main_head[:10], original_head[:10]))
    check("origin/%s unchanged (nothing pushed)" % a.base_branch, origin == original_head, origin[:10])
    check("no remote branch for the work branch", ("refs/remotes/origin/%s" % branch) not in remote_refs.split() if branch != a.base_branch else True, branch)

    # moved files via git mv (renames in the index/history)
    renames = {}
    for row in git("diff", "--name-status", "-M", "%s..HEAD" % a.base_branch).splitlines():
        parts = row.split("\t")
        if parts[0].startswith("R"):
            renames[parts[1]] = parts[2]

    changed, missing, moved, approved = [], [], [], []
    for path, digest in before_hash.items():
        full = os.path.join(ROOT, path)
        if path in renames:
            moved.append(path)
            dest = os.path.join(ROOT, renames[path])
            if not os.path.exists(dest) or sha(dest) != digest:
                changed.append("%s -> %s (content changed by move)" % (path, renames[path]))
        elif not os.path.exists(full):
            missing.append(path)
        elif sha(full) != digest:
            (approved if path in a.allow_modified else changed).append(path)
    check("every pre-existing file is byte-identical (or a pure move)", not changed and not missing,
          "%d files compared, %d moved, %d approved edits %s, unexpected changes=%s missing=%s" % (len(before_hash), len(moved), len(approved), approved, changed[:5], missing[:5]))

    status_now = parse_status(git("status", "--short", "-uall"))
    dirty_before = {p: s for p, s in before_status.items()}
    still_dirty = {p for p in dirty_before if p in status_now and status_now[p].strip()}
    lost = [p for p in dirty_before if p not in status_now]
    check("pre-existing uncommitted changes still present and uncommitted", not lost,
          "%d of %d still show as changed; lost=%s" % (len(still_dirty), len(dirty_before), lost))
    staged = [p for p, s in status_now.items() if s[0] not in " ?"]
    check("nothing staged right now", not staged, "staged=%s" % staged[:5])
    committed_paths = set(git("diff", "--name-only", "%s..HEAD" % a.base_branch).splitlines())
    leaked = sorted(p for p in dirty_before if p in committed_paths)
    check("no pre-existing uncommitted path was committed", not leaked, "leaked=%s" % leaked)
    deleted_before = sorted(p for p, s in dirty_before.items() if "D" in s)
    restored = [p for p in deleted_before if os.path.exists(os.path.join(ROOT, p))]
    check("deleted documentation files were not restored", not restored, "%d entries remain deleted" % (len(deleted_before) - len(restored)))
    legacy_changes = sorted(p for p in committed_paths if p.startswith("AGRILENS_RaspberryPi/"))
    check("AGRILENS_RaspberryPi/ untouched in commits", not legacy_changes, "changes=%s" % legacy_changes[:5])

    untracked = sorted(p for p, s in status_now.items() if s == "??")
    report = ["# Git integrity report", "",
              "- Branch: `%s`  HEAD `%s`" % (branch, head[:10]),
              "- Commits on branch beyond `%s`: %d" % (a.base_branch, len(commits))]
    report += ["  - " + c for c in commits]
    report += ["", "| Check | Result | Detail |", "|---|---|---|"] + lines
    report += ["", "## Working tree now", "",
               "- Uncommitted tracked changes: %d (12 pre-existing + any listed below)" % sum(1 for s in status_now.values() if s != "??"),
               "- Untracked (new, not yet committed): %d" % len(untracked)]
    report += ["  - `%s`" % p for p in untracked[:60]]
    report += ["", "## Pre-existing changes (must remain exactly as they were)", ""]
    report += ["- `%s` %s" % (p, s.strip() or "-") for p, s in sorted(dirty_before.items())]
    text = "\n".join(report) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
