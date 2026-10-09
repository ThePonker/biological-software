"""Install the git pre-commit hook that lints the files you are committing (backlog I5).

    py -3.14 -m pip install ruff
    py -3.14 scripts\\install_git_hooks.py

After this, every `git commit` runs ruff (settings in ruff.toml) on the staged
.py files only. If it finds a problem the commit stops and the problem is listed;
fix it, `git add` the file again and re-commit. If ruff is not installed the hook
says so and lets the commit through. To skip it once: git commit --no-verify.

Re-running this script is safe: it rewrites the same hook. An existing hook that
this script did not write is moved to _archive first, never deleted.
"""
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, ".git", "hooks", "pre-commit")
MARK = "# installed by scripts/install_git_hooks.py"

# Git for Windows runs hooks with its own bash, so this is a shell script.
SCRIPT = f"""#!/bin/sh
{MARK}
files=$(git diff --cached --name-only --diff-filter=ACMR -- '*.py')
[ -z "$files" ] && exit 0
if command -v py >/dev/null 2>&1; then PY="py -3.14"; else PY="python3"; fi
if ! $PY -m ruff --version >/dev/null 2>&1; then
    echo "pre-commit: ruff is not installed, lint skipped ($PY -m pip install ruff)"
    exit 0
fi
echo "$files" | tr '\\n' '\\0' | xargs -0 $PY -m ruff check --force-exclude --quiet
status=$?
if [ $status -ne 0 ]; then
    echo ""
    echo "pre-commit: lint problems above -- commit stopped. Fix, git add, commit again."
    echo "            (to commit anyway: git commit --no-verify)"
fi
exit $status
"""


def main():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        sys.exit(f"No .git folder in {ROOT} -- run this from the repository.")
    os.makedirs(os.path.dirname(HOOK), exist_ok=True)
    if os.path.exists(HOOK):
        with open(HOOK, encoding="utf-8", errors="replace") as f:
            if MARK not in f.read():
                dest = os.path.join(ROOT, "_archive", f"pre-commit-hook-{datetime.now():%Y%m%d-%H%M%S}")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(HOOK, dest)
                print(f"Existing hook moved to {dest}")
    with open(HOOK, "w", encoding="utf-8", newline="\n") as f:
        f.write(SCRIPT)
    os.chmod(HOOK, 0o755)
    print(f"Pre-commit hook installed: {HOOK}")
    print("Test it: py -3.14 -m ruff check .   (should say All checks passed!)")


if __name__ == "__main__":
    main()
