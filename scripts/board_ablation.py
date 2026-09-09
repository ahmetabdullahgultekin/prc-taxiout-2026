"""Ablate the feature families on the leaderboard rather than on the holdout.

The holdout is 2025 predicting 2025; the board is 2025 predicting 2026. Those are not
the same question, and this project has now measured a case where they disagree by
seventeen seconds in total: the overlap family gained 10.76 locally and lost 7.03 on the
board. Any feature whose value depends on a relationship holding across that year will
look good locally and can still lose.

So the ablation that decides anything is this one. It builds one submission per family,
each with that family removed and everything else held fixed, and reports the scores as
a table. This is also the shape of the contribution table the 2025 winner published, and
they produced it the same way, on the ranking set rather than by cross-validation.

XGBoost alone by default. It is about four seconds behind the blend, which does not
matter for a comparison where every configuration pays the same penalty, and it turns a
ninety-minute build into six minutes. The features come from the cache.

Submissions are free in the sense that matters: teams are ranked by their best score, so
a deliberately weakened configuration cannot cost anything but the time to run it.

    python scripts/board_ablation.py --team vibrant-lollipop
    python scripts/board_ablation.py --team vibrant-lollipop --families weather atfm
    python scripts/board_ablation.py --team vibrant-lollipop --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from taxiout import config
from taxiout.application import cache
from taxiout.features import groups

REPO = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> str:
    proc = subprocess.run(  # noqa: S603
        cmd, cwd=REPO, capture_output=True, text=True, check=False,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(REPO / "src"),
             "PYTHONIOENCODING": "utf-8"},
    )
    if proc.returncode != 0:
        raise SystemExit(f"failed: {' '.join(cmd)}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return proc.stdout


def main() -> None:
    ap = argparse.ArgumentParser(description="ablate feature families on the leaderboard")
    ap.add_argument("--team", required=True)
    ap.add_argument("--data-dir", default=str(config.DATA_DIR))
    ap.add_argument("--learners", default="xgboost")
    ap.add_argument("--rounds", type=int, default=1000)
    ap.add_argument("--families", nargs="*", default=None,
                    help="which families to drop, one submission each; default all of them")
    ap.add_argument("--dry-run", action="store_true", help="list what would be run")
    ap.add_argument("--out", default=None, help="write the table here as JSON")
    args = ap.parse_args()

    directory = config.cache(args.data_dir)
    changed = cache.stale(directory)
    if changed:
        raise SystemExit(
            f"the cache in {directory} is stale ({len(changed)} files differ). "
            "Rebuild it with scripts/cache_features.py --ranking, or the whole table "
            "will describe a model that no longer exists."
        )

    families = args.families if args.families is not None else sorted(groups.GROUPS)
    plan = [("baseline", [])] + [(f, [f]) for f in families]
    print(f"{len(plan)} submissions: a baseline and one per family\n")
    if args.dry_run:
        for label, drop in plan:
            print(f"  {label:<24} drop {drop}")
        return

    results: list[dict] = []
    for label, drop in plan:
        t = time.time()
        cmd = [sys.executable, "scripts/make_submission.py", "--team", args.team,
               "--data-dir", args.data_dir, "--use-cache", "--learners", args.learners,
               "--rounds", str(args.rounds), "--seeds", "1", "--raw-target"]
        if drop:
            cmd += ["--drop-groups", *drop]
        out = run(cmd)
        version = int(out.split("_v")[-1].split(".parquet")[0])
        n_features = int(out.split("using ")[1].split(" features")[0])

        score_out = run([sys.executable, "scripts/submit.py", "--team", args.team,
                         "--data-dir", args.data_dir, "--version", str(version)])
        score = float(score_out.split("SCORE")[1].strip().split()[0])
        results.append({"dropped": label, "features": n_features,
                        "version": version, "score": score})
        base = results[0]["score"]
        print(f"  {label:<24} n={n_features:>3}  v{version:<3} "
              f"score {score:8.4f}   {score - base:+8.4f}   [{time.time() - t:.0f}s]",
              flush=True)

    base = results[0]["score"]
    print("\nwhat each family is worth on the board, most valuable first:")
    for row in sorted(results[1:], key=lambda r: -(r["score"] - base)):
        worth = row["score"] - base
        verdict = "" if worth > 0 else "   <- the model is better without it"
        print(f"  {row['dropped']:<24} {worth:+8.4f}{verdict}")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwritten: {args.out}")


if __name__ == "__main__":
    main()
