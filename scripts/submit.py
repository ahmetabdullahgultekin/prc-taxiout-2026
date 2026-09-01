"""Uploads a submission file to the team bucket and waits for the score.

This exists because the manual step it replaces failed silently and cost a submission
round. `make_submission.py` printed

    mc cp <file> opensky/prc-2026-<team>/

and the configured alias for the OpenSky endpoint is `prc`, not `opensky`. `mc` does not
treat an unknown alias as an error: it reads the argument as a relative local path,
creates the directory and copies the file into it. It then reports success, and the copy
rate gives it away only if you happen to look, 122 MiB/s against about 2.5 MiB/s over
the network. The file never left the machine and no score ever arrived.

So the upload is checked here rather than assumed:

  * the alias must resolve to an https endpoint before anything is copied
  * the object must be listed in the remote bucket after the copy
  * the result file is polled and the score printed

    python scripts/submit.py --team vibrant-lollipop --version 3
    python scripts/submit.py --team vibrant-lollipop            # the newest file
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from taxiout import config

MC = Path.home() / "bin" / "mc.exe"
ALIAS = config.MC_ALIAS
POLL_SECONDS = 5
POLL_LIMIT = 300


def mc(*args: str) -> str:
    """Runs mc and returns stdout, raising on a non-zero exit."""
    proc = subprocess.run(  # noqa: S603
        [str(MC), *args], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise SystemExit(f"mc {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout


def check_alias() -> None:
    """Refuses to run unless the alias really points at a remote endpoint.

    Without this the copy silently becomes a local file copy, which is the exact
    failure this script was written to prevent.
    """
    out = mc("alias", "list", ALIAS)
    match = re.search(r"URL\s*:\s*(\S+)", out)
    if not match:
        raise SystemExit(
            f"alias {ALIAS!r} is not configured. `mc alias list` shows what is.\n"
            "Without a configured alias mc would copy the file to a local directory "
            "of that name and report success."
        )
    url = match.group(1)
    if not url.startswith("https://"):
        raise SystemExit(f"alias {ALIAS!r} points at {url}, which is not a remote endpoint")
    print(f"alias {ALIAS} -> {url}")


def main() -> None:
    ap = argparse.ArgumentParser(description="upload a submission and wait for the score")
    ap.add_argument("--data-dir", default=str(config.DATA_DIR))
    ap.add_argument("--team", required=True)
    ap.add_argument("--version", type=int, default=None, help="defaults to the newest file")
    ap.add_argument("--no-wait", action="store_true", help="upload and exit")
    args = ap.parse_args()

    out_dir = config.submissions(args.data_dir)
    if args.version is not None:
        path = out_dir / f"{args.team}_v{args.version}.parquet"
    else:
        files = sorted(out_dir.glob(f"{args.team}_v*.parquet"),
                       key=lambda p: int(re.search(r"_v(\d+)\.parquet$", p.name).group(1)))
        if not files:
            raise SystemExit(f"no submission files for {args.team} in {out_dir}")
        path = files[-1]
    if not path.exists():
        raise SystemExit(f"not found: {path}")

    check_alias()
    bucket = config.bucket(args.team)
    print(f"uploading {path.name} ({path.stat().st_size:,} bytes) to {bucket}/")
    mc("cp", str(path), f"{bucket}/")

    # The upload is not believed until the object is listed in the remote bucket.
    listing = mc("ls", f"{bucket}/")
    if path.name not in listing:
        raise SystemExit(
            f"{path.name} is not in {bucket} after the copy. The upload did not happen."
        )
    print(f"confirmed in the bucket: {path.name}")
    if args.no_wait:
        return

    result_key = f"{path.name}_result.json"
    print(f"waiting for {result_key}", end="", flush=True)
    for _ in range(POLL_LIMIT):
        if result_key in mc("ls", f"{bucket}/"):
            break
        print(".", end="", flush=True)
        time.sleep(POLL_SECONDS)
    else:
        raise SystemExit(
            f"\nno result after {POLL_LIMIT * POLL_SECONDS} s. The file is uploaded; "
            f"read it later with: mc cat {bucket}/{result_key}"
        )

    result = json.loads(mc("cat", f"{bucket}/{result_key}"))
    print()
    if result.get("status") != "Succeeded":
        raise SystemExit(f"submission rejected: {json.dumps(result, indent=2)}")
    print(f"  status      {result['status']}")
    print(f"  pairs used  {result.get('used_pairs', 0):,}")
    print(f"  SCORE       {result['score']}")


if __name__ == "__main__":
    main()
