"""Oznitelik ailesi ablation tablosunu uretir.

2025 birincisinin makalesinde katkinin sunumu tek bir oznitelik x RMSE tablosuydu (P06)
ve o tabloyu dogrudan siralama seti uzerinde urettiler (P04). Bu betik ayni tabloyu
yerel mevsimsel dogrulama uzerinde uretir; gonderim butcesi ise gercekten belirsiz olan
satirlara harcanir.

Cikti dogrudan `docs/experiments.md` ve JOAS makalesine yapistirilabilir markdown.

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
    head = "| yapilandirma | oznitelik | Ocak | Temmuz | toplam | Δ toplam |"
    sep = "|---|---:|---:|---:|---:|---:|"
    lines = [head, sep]
    for r in rows:
        delta = r["toplam"] - baseline
        işaret = "—" if abs(delta) < 1e-9 else f"{delta:+.2f}"
        lines.append(
            f"| {r['ad']} | {r['n_oznitelik']} | {r.get('ay_1', float('nan')):.2f} | "
            f"{r.get('ay_7', float('nan')):.2f} | {r['toplam']:.2f} | {işaret} |"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="oznitelik ailesi ablation'i")
    ap.add_argument("--data-dir", default=os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))
    ap.add_argument("--rounds", type=int, default=1200)
    ap.add_argument("--seeds", type=int, default=1, help="tohum ortalamasi icin model sayisi")
    ap.add_argument("--causal", action="store_true")
    ap.add_argument("--raw-target", action="store_true", help="artik yerine ham hedefle egit")
    ap.add_argument("--out", default="docs/ablation_report.md")
    args = ap.parse_args()

    t0 = time.time()
    raw = Path(args.data_dir) / "00_raw"
    inputs = pipeline.load_inputs(raw)
    print(f"hareket: {inputs.movements.height:,} satir")

    feats = pipeline.build_features(inputs, causal=args.causal)
    split = pipeline.seasonal_split(feats, inputs.movements)
    cols = split.columns
    print(f"egitim {split.fit.height:,} / dogrulama {split.val.height:,} satir, "
          f"{len(cols)} oznitelik")
    print("\noznitelik ailesi buyuklukleri:")
    print(pipeline.group_report(cols))

    seeds = tuple(range(1, args.seeds + 1))
    residual = not args.raw_target

    configs: list[tuple[str, set[str]]] = [("tam model", set())]
    assigned = groups.assign(cols)
    for name in groups.GROUPS:
        if assigned[name]:  # bu kosuda uretilmemis aileyi atlama
            configs.append((f"− {name}", {name}))

    rows, baseline = [], None
    for ad, drop in configs:
        used = groups.select(cols, drop)
        pred = pipeline.train_predict(split, used, args.rounds, residual, seeds)
        scores = pipeline.evaluate(split, pred)
        if baseline is None:
            baseline = scores["toplam"]
        rows.append({"ad": ad, "n_oznitelik": len(used), **scores})
        delta = scores["toplam"] - baseline
        print(f"  {ad:<28} n={len(used):>3}  RMSE={scores['toplam']:8.2f}  "
              f"({delta:+.2f})   [{time.time() - t0:,.0f} sn]")

    mod = "nedensel (blok cipali)" if args.causal else "retrospektif (kalkis cipali)"
    hedef = "ham taxi-out" if args.raw_target else "ATXOT P10 uzerinde artik"
    body = (
        f"# Ablation raporu\n\n"
        f"- mod: **{mod}**\n- hedef: **{hedef}**\n"
        f"- tur sayisi: {args.rounds}, tohum: {args.seeds}\n"
        f"- dogrulama: 2025 Ocak + Temmuz tutuldu, kalan 10 ayla egitildi\n\n"
        f"Negatif Δ o aileyi **cikarmanin** RMSE'yi dusurdugu anlamina gelir: aile\n"
        f"zarar veriyordur. Pozitif Δ aile faydalidir; buyuklugu katkisini olcer.\n\n"
        + markdown_table(rows, baseline)
        + "\n\n## Havalimani bazinda tam model\n\n| havalimani | RMSE |\n|---|---:|\n"
        + "\n".join(
            f"| {k.removeprefix('apt_')} | {v:.2f} |"
            for k, v in sorted(rows[0].items()) if k.startswith("apt_")
        )
        + "\n"
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(f"\nrapor: {out}   ({time.time() - t0:,.0f} sn)")


if __name__ == "__main__":
    main()
