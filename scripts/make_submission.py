"""Siralama seti icin tahmin uretir ve valid bir gonderim dosyasi yazar.

Onemli tasarim noktasi: **tikaniklik oznitelikleri her veri setinin kendi hareket
akisindan uretilir.** Siralama seti Ocak + Temmuz 2026'nin tum hareketlerini icerir
(varislar dahil, hicbiri bosaltilmamis), dolayisiyla o aylarin trafik yogunlugu oradan
hesaplanir; 2025 verisinden degil. Referans tablosu ise tam tersine 2025'ten gelir,
cunku siralama setinde kalkislarin taxi suresi yok.

Akis:

    1. 2025'in tamamiyla egit (mevsimsel dogrulama ayri bir kosudur, `train_baseline.py`)
    2. ranking.parquet uzerinde oznitelik uret, 2025 referansini uygula
    3. tahmin et, kirp, dogrula, yaz

    python scripts/make_submission.py --data-dir D:/prc-taxiout-2026 --team keen-hamburger
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np
import polars as pl

from taxiout.application import pipeline, submission
from taxiout.domain import reference
from taxiout.features import groups

TARGET = pipeline.TARGET


def main() -> None:
    ap = argparse.ArgumentParser(description="siralama seti gonderimi uret")
    ap.add_argument("--data-dir", default=os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))
    ap.add_argument("--team", required=True, help="atanan takim adi, orn keen-hamburger")
    ap.add_argument("--rounds", type=int, default=1500)
    ap.add_argument("--seeds", type=int, default=5,
                    help="tohum ortalamasi; 2024 birincisinin yontemi")
    ap.add_argument("--raw-target", action="store_true")
    ap.add_argument("--drop-groups", nargs="*", default=[],
                    help="ablation icin cikarilacak oznitelik aileleri")
    ap.add_argument("--version", type=int, default=None, help="elle surum; varsayilan bir sonraki")
    args = ap.parse_args()

    t0 = time.time()
    raw = Path(args.data_dir) / "00_raw"
    out_dir = Path(args.data_dir) / "04_submissions"
    rank_path, template_path = raw / "ranking.parquet", raw / "submitting.parquet"
    for p in (rank_path, template_path):
        if not p.exists():
            raise SystemExit(f"bulunamadi: {p}")

    # --- egitim tarafi
    inputs = pipeline.load_inputs(raw)
    print(f"egitim hareketi: {inputs.movements.height:,}")
    fit_feats = pipeline.build_features(inputs).filter(pl.col(TARGET).is_not_null())

    # referans TUM 2025'ten: siralama seti icin tutulacak bir month_num yok
    tables = reference.fit_reference(inputs.movements)
    fit = reference.apply_reference(fit_feats, tables)

    # --- siralama tarafi: oznitelikler kendi hareket akisindan
    # dis veriler egitim tarafiyla AYNI olmali; alan adiyla veriliyor cunku konumsal
    # cagri Inputs'a yeni bir alan eklendiginde sessizce eksik kalir (bir kez oldu)
    rank_inputs = pipeline.Inputs(
        movements=pipeline.prepare_movements(pl.read_parquet(rank_path)),
        metar=inputs.metar,
        coords=inputs.coords,
        runways=inputs.runways,
        atfm_daily=inputs.atfm_daily,
    )
    print(f"siralama hareketi: {rank_inputs.movements.height:,}")
    rank_feats = reference.apply_reference(pipeline.build_features(rank_inputs), tables)

    cols = [c for c in pipeline.feature_columns(fit) if c in rank_feats.columns]
    eksik = set(pipeline.feature_columns(fit)) - set(cols)
    if eksik:
        # sessizce dusurmek yerine soyle: siralama setinde uretilemeyen oznitelik varsa
        # bu, kurgu hakkinda bir sey ogrendigimiz anlamina gelir
        print(
            f"UYARI: siralama setinde uretilemeyen {len(eksik)} oznitelik atlandi: "
            f"{sorted(eksik)}"
        )
        print("  bu neredeyse her zaman bir hatadir: modelin egitimde ogrenip")
        print("  tahminde kaybettigi bilgidir. Devam etmeden once bakilmali.")
    cols = groups.select(cols, set(args.drop_groups))
    print(f"{len(cols)} oznitelik kullaniliyor")

    split = pipeline.Split(fit=fit, val=rank_feats, columns=cols)
    pred = pipeline.train_predict(
        split, cols, args.rounds,
        residual=not args.raw_target,
        seeds=tuple(range(1, args.seeds + 1)),
    )

    # --- gonderim dosyasi
    template = pl.read_parquet(template_path)
    pred_df = rank_feats.select("MVT_ID_mvt").with_columns(
        pl.Series(TARGET, np.asarray(pred, dtype=np.float64))
    )
    # sablonda olan ama oznitelik tablosunda olmayan satir kalirsa medyanla doldur:
    # eksik satirli dosya reddedilir, bir gonderim bosa gider
    eksik_satir = template.join(pred_df, on="MVT_ID_mvt", how="anti")
    if eksik_satir.height:
        dolgu = float(np.median(pred))
        print(
            f"UYARI: {eksik_satir.height:,} sablon satiri tahmin edilemedi, "
            f"medyan ({dolgu:,.0f} sn) ile dolduruldu"
        )
        pred_df = pl.concat([
            pred_df,
            eksik_satir.select("MVT_ID_mvt").with_columns(pl.lit(dolgu).alias(TARGET)),
        ])
    pred_df = pred_df.join(template.select("MVT_ID_mvt"), on="MVT_ID_mvt", how="semi")

    out_dir.mkdir(parents=True, exist_ok=True)
    version = args.version or submission.next_version(out_dir, args.team)
    out_path = out_dir / f"{args.team}_v{version}.parquet"
    uyarilar = submission.write(pred_df, template, out_path)

    print(f"\ntahmin ozeti: mean={np.mean(pred):,.0f} sn  medyan={np.median(pred):,.0f}  "
          f"p99={np.percentile(pred, 99):,.0f}  min={np.min(pred):,.0f}")
    for u in uyarilar:
        print(f"  uyari: {u}")
    print(f"\nyazildi: {out_path}   ({time.time() - t0:,.0f} sn)")
    print(f"yukle:  mc cp {out_path} opensky/prc-2026-{args.team}/")


if __name__ == "__main__":
    main()
