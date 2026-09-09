"""Runs every check that CI would run, locally.

GitHub Actions cannot execute on this account, so the workflow file is present and
correct but never runs. That leaves a choice between an unverified repository and a
verification step someone has to remember. This is that step, made into one command:

    python scripts/verify.py

It runs exactly what `.github/workflows/ci.yml` runs, in the same order, and stops at
the first failure. Anything the workflow gains must be added here too, and a test holds
the two in step so they cannot drift apart quietly.

Install it as a pre-push hook so it cannot be forgotten:

    python scripts/verify.py --install-hook
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

HOOK = """#!/bin/sh
# Installed by scripts/verify.py. GitHub Actions cannot run on this account, so the
# checks run here instead. Skip deliberately with: git push --no-verify
exec "{python}" "{script}" || exit 1
"""


def steps(fixture: Path) -> list[tuple[str, list[str]]]:
    """The check list, mirroring .github/workflows/ci.yml step for step."""
    return [
        ("Lint", [PY, "-m", "ruff", "check", "src", "tests", "scripts"]),
        ("Tests", [PY, "-m", "pytest", "tests", "-q"]),
        ("Fixture", [PY, "tests/make_fixture.py",
                     "--out", str(fixture / "00_raw"), "--per-day", "60"]),
        ("Probe", [PY, "scripts/probe_data.py", "--data-dir", str(fixture)]),
        ("Training", [PY, "scripts/train_baseline.py",
                      "--data-dir", str(fixture), "--rounds", "40"]),
        ("Submission", [PY, "scripts/make_submission.py", "--data-dir", str(fixture),
                        "--team", "keen-hamburger", "--rounds", "40", "--seeds", "1"]),
    ]


def install_hook() -> None:
    hooks = REPO / ".git" / "hooks"
    if not hooks.is_dir():
        raise SystemExit(f"no hooks directory at {hooks}; is this a git checkout?")
    target = hooks / "pre-push"
    target.write_text(
        HOOK.format(python=PY.replace("\\", "/"),
                    script=str(REPO / "scripts" / "verify.py").replace("\\", "/")),
        encoding="utf-8", newline="\n",
    )
    target.chmod(0o755)
    print(f"installed {target}")
    print("every push now runs the checks first; skip one with: git push --no-verify")


def main() -> None:
    ap = argparse.ArgumentParser(description="run the CI checks locally")
    ap.add_argument("--install-hook", action="store_true",
                    help="install this as a git pre-push hook and exit")
    ap.add_argument("--quick", action="store_true",
                    help="lint and tests only, skipping the synthetic pipeline run")
    args = ap.parse_args()

    if args.install_hook:
        install_hook()
        return

    fixture = Path(tempfile.mkdtemp(prefix="taxiout-verify-"))
    env = {**os.environ, "PYTHONPATH": str(REPO / "src"), "PYTHONIOENCODING": "utf-8"}
    selected = steps(fixture)
    if args.quick:
        selected = selected[:2]

    t0 = time.time()
    try:
        for name, cmd in selected:
            print(f"\n=== {name} " + "=" * (60 - len(name)), flush=True)
            started = time.time()
            proc = subprocess.run(cmd, cwd=REPO, env=env, check=False)  # noqa: S603
            if proc.returncode != 0:
                print(f"\nFAILED at {name} (exit {proc.returncode})")
                raise SystemExit(proc.returncode)
            print(f"--- {name} ok [{time.time() - started:.0f}s]")
    finally:
        shutil.rmtree(fixture, ignore_errors=True)

    print(f"\nall {len(selected)} checks passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
