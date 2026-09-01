"""Produces the feature family ablation table.

In the 2025 winner's paper the contribution was presented as a single feature x RMSE table
(P06), and that table was produced directly on the ranking set (P04). This script produces
the same table on the local seasonal validation instead; the submission budget is then spent
on the rows that are genuinely uncertain.

The output is markdown that can be pasted straight into `docs/experiments.md` and the JOAS
paper.

    python scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --rounds 1200
    python scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --causal
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from taxiout.application import pipeline
from taxiout.features import groups


def markdown_table(rows: list[dict], baseline: float) -> str:
    head = "| configuration | features | January | July | total | Δ total |"
    sep = "|---|---:|---:|---:|---:|---:|"
    lines = [head, sep]
    for r in rows:
        delta = r["total"] - baseline
        marker = "-" if abs(delta) < 1e-9 else f"{delta:+.2f}"
        lines.append(
            f"| {r['config']} | {r['n_features']} | {r.get('month_1', float('nan')):.2f} | "
            f"{r.get('month_7', float('nan')):.2f} | {r['total']:.2f} | {marker} |"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="feature family ablation")
    ap.add_argument("--data-dir", default=os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))
    ap.add_argument("--rounds", type=int, default=1200)
    ap.add_argument("--seeds", type=int, default=1, help="number of models to average over seeds")
    ap.add_argument("--causal", action="store_true")
    ap.add_argument("--raw-target", action="store_true", help="train on the raw target instead of "
                                                              "the residual")
    ap.add_argument("--out", default="docs/ablation_report.md")
    args = ap.parse_args()

    t0 = time.time()
    raw = Path(args.data_dir) / "00_raw"
    inputs = pipeline.load_inputs(raw)
    print(f"movements: {inputs.movements.height:,} rows")

    feats = pipeline.build_features(inputs, causal=args.causal)
    split = pipeline.seasonal_split(feats, inputs.movements)
    cols = split.columns
    print(f"training {split.fit.height:,} / validation {split.val.height:,} rows, "
          f"{len(cols)} features")
    print("\nfeature family sizes:")
    print(pipeline.group_report(cols))

    seeds = tuple(range(1, args.seeds + 1))
    residual = not args.raw_target

    configs: list[tuple[str, set[str]]] = [("full model", set())]
    assigned = groups.assign(cols)
    for name in groups.GROUPS:
        if assigned[name]:  # skip a family that was not produced in this run
            configs.append((f"− {name}", {name}))

    rows, baseline = [], None
    for config, drop in configs:
        used = groups.select(cols, drop)
        pred = pipeline.train_predict(split, used, args.rounds, residual, seeds)
        scores = pipeline.evaluate(split, pred)
        if baseline is None:
            baseline = scores["total"]
        rows.append({"config": config, "n_features": len(used), **scores})
        delta = scores["total"] - baseline
        print(f"  {config:<28} n={len(used):>3}  RMSE={scores['total']:8.2f}  "
              f"({delta:+.2f})   [{time.time() - t0:,.0f} s]")

    mode = "causal (block-anchored)" if args.causal else "retrospective (departure-anchored)"
    target = "raw taxi-out" if args.raw_target else "residual over ATXOT P10"
    body = (
        f"# Ablation report\n\n"
        f"- mode: **{mode}**\n- target: **{target}**\n"
        f"- rounds: {args.rounds}, seeds: {args.seeds}\n"
        f"- validation: 2025 January + July held out, trained on the remaining 10 months\n\n"
        f"A negative Δ means **removing** that family lowered the RMSE: the family is doing\n"
        f"harm. A positive Δ means the family helps; its size measures the contribution.\n\n"
        + markdown_table(rows, baseline)
        + "\n\n## Full model by airport\n\n| airport | RMSE |\n|---|---:|\n"
        + "\n".join(
            f"| {k.removeprefix('apt_')} | {v:.2f} |"
            for k, v in sorted(rows[0].items()) if k.startswith("apt_")
        )
        + "\n"
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(f"\nreport: {out}   ({time.time() - t0:,.0f} s)")


if __name__ == "__main__":
    main()
