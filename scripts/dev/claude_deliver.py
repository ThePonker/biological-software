"""Delivery helper for Claude sessions (runs in Claude's workspace, not on Wil's PC).

Claude delivers files to Wil's PC with its device tools (stage = copy from the PC,
commit = write to the PC). This script does the steps in between, so they are the
same every time:

  1. prepare  -- for the files changed between two commits: lint them with ruff (it
                 stops before writing anything if ruff finds a problem), check the copies just
                 staged from the PC still match BASE (so nothing Wil changed is
                 overwritten), copy each new version to an output folder keeping
                 the PC's line endings (CRLF where his copy has CRLF), and print
                 the JSON lists for the stage and commit tool calls.
  2. verify   -- after writing and re-staging: compare each delivered file with
                 the staged copy byte for byte.

    python3 scripts/dev/claude_deliver.py prepare BASE HEAD --out /mnt/user-data/outputs/<name>
    python3 scripts/dev/claude_deliver.py verify BASE HEAD --out /mnt/user-data/outputs/<name>

Options: --pc-root (Wil's folder on the PC), --staged (where staged files land).
Run from the repo root. Reads git only; writes only under --out.
"""
import argparse
import json
import os
import subprocess
import sys

PC_ROOT = r"C:\Users\Wil J. Heeney\OneDrive\Biological Software"
STAGED = "/mnt/user-data/uploads/Biological Software"


def changed(base: str, head: str) -> list:
    """Files added, modified or renamed (new path) between base and head."""
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", base, head],
                         capture_output=True, text=True, check=True).stdout
    files = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        if status[0] in "AM":
            files.append(path)
        elif status[0] == "D":
            print(f"  NOTE deleted in {head}: {path} -- Wil removes it on the PC (Claude never deletes)")
    return files


def git_show(rev: str, path: str):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def pc_path(root: str, rel: str) -> str:
    return root + "\\" + rel.replace("/", "\\")


def lint(files: list) -> bool:
    """ruff (the repo's ruff.toml) on the .py files being delivered -- the same check as
    Wil's pre-commit hook, so a delivery never stops his commit (13 Oct 2026)."""
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return True
    try:
        r = subprocess.run([sys.executable, "-m", "ruff", "check", *py],
                           capture_output=True, text=True)
    except OSError as e:
        print(f"  STOP lint: could not run ruff ({e})")
        return False
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        print("  STOP lint: fix the problems above, commit, and prepare again "
              "(nothing written)")
        if "No module named ruff" in r.stderr:
            print("  (install it: pip install ruff)")
        return False
    return True


def prepare(a) -> int:
    files = changed(a.base, a.head)
    if not lint(files):
        return 1
    problems = 0
    os.makedirs(a.out, exist_ok=True)
    for rel in files:
        staged = os.path.join(a.staged, rel)
        old = git_show(a.base, rel)
        crlf = False
        if os.path.exists(staged):
            pc = open(staged, "rb").read()
            crlf = b"\r\n" in pc
            if old is not None and pc.replace(b"\r\n", b"\n") != old.replace(b"\r\n", b"\n"):
                print(f"  STOP {rel}: Wil's copy differs from {a.base} -- do not overwrite; ask him")
                problems += 1
                continue
        elif old is not None:
            print(f"  NOTE {rel}: not staged yet (stage it first to protect Wil's copy)")
        new = open(rel, "rb").read()
        if crlf:
            new = new.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        dest = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(new)
        print(f"  ready {rel}{'  (CRLF kept)' if crlf else ''}")
    stage = [pc_path(a.pc_root, r) for r in files]
    commit = [{"stagedPath": os.path.join(a.out, r), "devicePath": pc_path(a.pc_root, r)}
              for r in files]
    print("\nSTAGE (paths):", json.dumps(stage))
    for i in range(0, len(commit), 50):
        print(f"\nCOMMIT batch {i // 50 + 1}:", json.dumps(commit[i:i + 50]))
    print(f"\n{len(files)} file(s); {problems} stop(s)")
    return 1 if problems else 0


def verify(a) -> int:
    bad = 0
    files = changed(a.base, a.head)
    for rel in files:
        sent = os.path.join(a.out, rel)
        got = os.path.join(a.staged, rel)
        if not (os.path.exists(got) and open(sent, "rb").read() == open(got, "rb").read()):
            print(f"  MISMATCH {rel}")
            bad += 1
    print(f"verified {len(files) - bad} of {len(files)}")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=("prepare", "verify"))
    ap.add_argument("base")
    ap.add_argument("head")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pc-root", default=PC_ROOT)
    ap.add_argument("--staged", default=STAGED)
    a = ap.parse_args(argv)
    if a.action == "prepare" and os.path.isdir(a.out) and os.listdir(a.out):
        print(f"--out {a.out} is not empty: use a new folder name (this script never deletes)")
        return 2
    return prepare(a) if a.action == "prepare" else verify(a)


if __name__ == "__main__":
    sys.exit(main())
