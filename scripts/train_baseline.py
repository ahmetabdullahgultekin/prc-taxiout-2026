"""Mevsimsel dogrulama kosusu: taban model ve hedef parametrelendirmesi karsilastirmasi.

2025'ten Ocak ve Temmuz cikarilir, model kalan 10 ayla egitilir, o iki ayda **ayri
ayri** degerlendirilir. Rastgele K-fold burada yalan soyler: siralama seti Ocak +
Temmuz 2026, yani iki mevsimsel uc ve bir yillik kayma.

Ayni kosuda iki hedef parametrelendirmesi karsilastirilir:

  ham    -> dogrudan TAXITIME_SEC_mvt
  artik  -> TAXITIME_SEC_mvt - reference_sec (ATXOT P10), tahminde geri eklenir

2025 birincisinin en buyuk tekil kazanci tam olarak bu turden bir yeniden
parametrelendirmeydi: yakit tuketimi yerine yakit akisi (RMSE 220.56 -> 201.04), tum
oznitelik gruplarindan buyuk bir etki (P05). O yuzden ilk kosuda olculur.

    python scripts/train_baseline.py --data-dir D:/prc-taxiout-2026
    python scripts/train_baseline.py --data-dir D:/prc-taxiout-2026 --causal
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np

from taxiout.application import pipeline
from taxiout.domain import reference


def report(name: str, split: pipeline.Split, pred: np.ndarray) -> None:
    scores = pipeline.evaluate(split, pred)
    print(f"\n=== {name} ===")
    print(f"  total RMSE: {scores['total']:8.2f} sn   (n={split.val.height:,})")
    print("  -- month_num bazinda --")
    for m in pipeline.HOLDOUT_MONTHS:
        if f"month_{m}" in scores:
            print(f"     {m:<8} RMSE={scores[f'month_{m}']:8.2f}")
    print("  -- havalimani bazinda (kotuden iyiye) --")
    per_apt = sorted(
        ((k.removeprefix("apt_"), v) for k, v in scores.items() if k.startswith("apt_")),
        key=lambda kv: -kv[1],
    )
    for apt, r in per_apt:
        print(f"     {apt:<8} RMSE={r:8.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="mevsimsel dogrulama taban kosusu")
    ap.add_argument("--data-dir", default=os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))
    ap.add_argument("--rounds", type=int, default=1500)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--causal", action="store_true",
                    help="nedensel mod: oznitelikler blok cozulme anina baglanir, "
                         "ileriye bakan pencere yok (yalnizca makale icin)")
    ap.add_argument("--max-train-sec", type=float, default=None,
                    help="hedefi bu esigi asan satirlari EGITIMDEN cikar "
                         "(dogrulama tam kalir); etiket hatasi filtresi")
    ap.add_argument("--no-aobt3", action="store_true",
                    help="NM blok saatinden turetilen ozniteligi cikar (ablation)")
    args = ap.parse_args()

    t0 = time.time()
    inputs = pipeline.load_inputs(Path(args.data_dir) / "00_raw")
    mod = "NEDENSEL (blok cipali)" if args.causal else "retrospektif (kalkis cipali)"
    print(f"hareket: {inputs.movements.height:,} satir")
    print(f"METAR: {'yok' if inputs.metar is None else f'{inputs.metar.height:,} gozlem'}")
    print(f"mod: {mod}")

    feats = pipeline.build_features(inputs, causal=args.causal, aobt3=not args.no_aobt3)
    split = pipeline.seasonal_split(feats, inputs.movements, args.max_train_sec)
    print(f"egitim {split.fit.height:,} / dogrulama {split.val.height:,} kalkis, "
          f"{len(split.columns)} oznitelik")
    if args.max_train_sec:
        print(f"egitim hedef esigi: {args.max_train_sec:,.0f} sn")
    print("\noznitelik ailesi buyuklukleri:")
    print(pipeline.group_report(split.columns))

    print("\nreferans kapsami (resmi ATXOT seviyesi vs geri dusus):")
    print(reference.official_coverage(split.val))

    seeds = tuple(range(1, args.seeds + 1))
    for name, residual in (
        ("ham hedef", False),
        ("artik hedef (taxi - ATXOT P10)", True),
    ):
        pred = pipeline.train_predict(split, split.columns, args.rounds, residual, seeds)
        report(name, split, pred)

    print(f"\ntoplam sure: {time.time() - t0:,.0f} sn")


if __name__ == "__main__":
    main()
