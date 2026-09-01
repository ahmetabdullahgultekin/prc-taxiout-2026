"""Gonderim dosyasi uretimi ve dogrulamasi.

Yarismanin dogrulama kurallari (F07, F08 - dc2026/ranking.html):

- dosya adi ``<takim-adi>_v<artan tamsayi>.parquet``
- ``submitting.parquet`` sablonundaki **tum** `MVT_ID_mvt` degerleri eslesmeli
- eksik satir olamaz, fazla satir olamaz

Bu kontroller burada, gonderimden **once** yapilir. Hatali bir dosya yuklemek
bir gonderim turunu ve saatlerce bekleme suresini bosa harcar; kontrol maliyeti
sifira yakin.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

MVT_ID = "MVT_ID_mvt"
TARGET = "TAXITIME_SEC_mvt"

FILENAME_RE = re.compile(r"^[a-z0-9-]+_v\d+\.parquet$")

# ATXOT'un resmi ust filtresi (s.13). Asan tahminler yasak degil ama neredeyse
# kesinlikle bir hatanin isaretidir; sessizce gecmesin.
SANITY_MAX_SEC = 120 * 60


class SubmissionError(ValueError):
    """Gonderim gecerlilik kurallarindan biri saglanmadi."""


def validate(pred: pl.DataFrame, template: pl.DataFrame) -> list[str]:
    """Sert kurallari uygular; ihlalde hata firlatir. Uyarilari liste olarak dondurur."""
    for name, frame in (("tahmin", pred), ("sablon", template)):
        missing = {MVT_ID, TARGET} - set(frame.columns)
        if name == "tahmin" and missing:
            raise SubmissionError(f"{name} tablosunda eksik kolon: {sorted(missing)}")

    if pred.height != template.height:
        raise SubmissionError(
            f"satir sayisi uyusmuyor: tahmin {pred.height:,}, sablon {template.height:,}"
        )

    dup = pred.height - pred[MVT_ID].n_unique()
    if dup:
        raise SubmissionError(f"{dup:,} tekrarli {MVT_ID} var")

    pred_ids = set(pred[MVT_ID].to_list())
    tmpl_ids = set(template[MVT_ID].to_list())
    if eksik := tmpl_ids - pred_ids:
        raise SubmissionError(f"{len(eksik):,} sablon satiri tahminde yok, orn: {list(eksik)[:5]}")
    if fazla := pred_ids - tmpl_ids:
        raise SubmissionError(f"{len(fazla):,} fazla satir var, orn: {list(fazla)[:5]}")

    target = pred[TARGET]
    if n := target.is_null().sum():
        raise SubmissionError(f"{n:,} bos tahmin var")
    if n := target.is_nan().sum():
        raise SubmissionError(f"{n:,} NaN tahmin var")
    if n := target.is_infinite().sum():
        raise SubmissionError(f"{n:,} sonsuz tahmin var")
    if n := (target < 0).sum():
        raise SubmissionError(f"{n:,} negatif tahmin var - taxi suresi negatif olamaz")

    uyarilar: list[str] = []
    if n := (target > SANITY_MAX_SEC).sum():
        uyarilar.append(f"{n:,} tahmin 120 dakikayi asiyor (ATXOT ust filtresi)")
    if n := (target < 60).sum():
        uyarilar.append(f"{n:,} tahmin 60 saniyenin altinda - fiziksel olarak supheli")
    ort = target.mean()
    if ort is not None and not 300 <= ort <= 1800:
        uyarilar.append(f"ortalama tahmin {ort:,.0f} sn - beklenen 5-30 dk araliginin disinda")
    return uyarilar


def write(pred: pl.DataFrame, template: pl.DataFrame, out_path: Path) -> list[str]:
    """Dogrular, sablon satir sirasini korur ve parquet yazar."""
    if not FILENAME_RE.match(out_path.name):
        raise SubmissionError(
            f"dosya adi kurala uymuyor: {out_path.name} "
            "(beklenen '<takim-adi>_v<N>.parquet', orn 'keen-hamburger_v1.parquet')"
        )
    uyarilar = validate(pred, template)
    ordered = template.select(MVT_ID).join(
        pred.select(MVT_ID, TARGET), on=MVT_ID, how="left"
    )
    if ordered[TARGET].is_null().any():  # validate'ten sonra olmamali; sessiz bozulmaya karsi
        raise SubmissionError("birlestirmeden sonra bos deger olustu")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.write_parquet(out_path)
    return uyarilar


def next_version(directory: Path, team: str) -> int:
    """Dizindeki en yuksek surumun bir fazlasi. Gonderimler artan tamsayi olmali (F07)."""
    pattern = re.compile(rf"^{re.escape(team)}_v(\d+)\.parquet$")
    versions = [
        int(m.group(1))
        for f in directory.glob("*.parquet")
        if (m := pattern.match(f.name))
    ]
    return max(versions, default=0) + 1
