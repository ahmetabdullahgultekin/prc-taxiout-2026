"""METAR gozlemlerini Iowa State IEM ASOS arsivinden ceker.

Kaynak ve lisans `docs/external_data.md` dosyasinda belgelenmistir (odul uygunlugu sarti).
Arsiv Imperial birim dondurur; burada SI'ye cevrilir ve taxi-out icin anlamli
turetilmis bayraklar hesaplanir.

Neden onemli: PRC'nin resmi gostergesi AOBT sonrasi de-icing yapan ucuslari
hesaptan **atiyor** (ATXOT s.13). Bizim hedefimiz ham taxi-out oldugu icin o
satirlari atamayiz; de-icing kosullarini modellemek zorundayiz.

    python -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01 \
        --out D:/prc-taxiout-2026/00_raw/metar.parquet
"""

from __future__ import annotations

import argparse
import io
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import polars as pl

BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

AIRPORTS = [
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH",
]

FIELDS = ["tmpf", "dwpf", "vsby", "sknt", "drct", "p01i", "wxcodes", "skyc1", "skyl1"]

# METAR mevcut-hava kodlari (WMO). Donma ve kar, de-icing gerekliliginin dogrudan isareti.
FREEZING_CODES = ("FZRA", "FZDZ", "FZFG")
SNOW_CODES = ("SN", "SG", "PL", "IC", "GS", "GR")
FOG_CODES = ("FG", "BR")
THUNDER_CODES = ("TS",)


def _month_edges(start: date, end: date) -> list[tuple[date, date]]:
    """Istegi aylik parcalara boler: tek dev istek yerine arsive kibar davranir."""
    edges: list[tuple[date, date]] = []
    cur = start.replace(day=1)
    while cur < end:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        edges.append((max(cur, start), min(nxt, end)))
        cur = nxt
    return edges


def _build_url(stations: list[str], start: date, end: date) -> str:
    params = [("data", f) for f in FIELDS]
    params += [("station", s) for s in stations]
    params += [
        ("year1", start.year), ("month1", start.month), ("day1", start.day),
        ("year2", end.year), ("month2", end.month), ("day2", end.day),
        ("tz", "UTC"), ("format", "comma"), ("missing", "empty"),
        ("trace", "empty"), ("latlon", "no"),
        # report_type BILEREK gonderilmiyor: filtrelemek Avrupa'nin yarim saatlik
        # METAR yayinini saatlige dusuruyor ve SPECI raporlarini atiyor.
        # SPECI tam da kosullar aniden degistiginde yayinlanir; taxi-out icin
        # en degerli gozlemler onlardir.
    ]
    return BASE_URL + "?" + urllib.parse.urlencode(params)


def _fetch_chunk(stations: list[str], start: date, end: date, retries: int = 3) -> pl.DataFrame:
    url = _build_url(stations, start, end)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")
            # ilk satirlar '#DEBUG:' yorumlari; gercek basliga kadar atla
            body = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("#"))
            return pl.read_csv(io.StringIO(body), infer_schema_length=10_000, try_parse_dates=False)
        except Exception as exc:  # noqa: BLE001 - agdan gelen her hatada yeniden dene
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"METAR indirilemedi {start}..{end}: {last_error}")


def _wx_flag(codes: tuple[str, ...]) -> pl.Expr:
    """wxcodes alaninda verilen kodlardan herhangi biri geciyor mu."""
    expr = pl.lit(False)
    for code in codes:
        expr = expr | pl.col("wxcodes").fill_null("").str.contains(code, literal=True)
    return expr


def to_si(df: pl.DataFrame) -> pl.DataFrame:
    """Imperial -> SI cevirisi ve taxi-out icin anlamli turetilmis bayraklar."""
    numeric = ["tmpf", "dwpf", "vsby", "sknt", "drct", "p01i", "skyl1"]
    df = df.with_columns(
        [pl.col(c).cast(pl.Float64, strict=False) for c in numeric if c in df.columns]
    )
    df = df.with_columns(
        valid=pl.col("valid").str.to_datetime("%Y-%m-%d %H:%M", strict=False),
        sicaklik_c=(pl.col("tmpf") - 32.0) * 5.0 / 9.0,
        cig_noktasi_c=(pl.col("dwpf") - 32.0) * 5.0 / 9.0,
        gorus_km=pl.col("vsby") * 1.609344,
        ruzgar_ms=pl.col("sknt") * 0.514444,
        ruzgar_yon=pl.col("drct"),
        yagis_mm=pl.col("p01i") * 25.4,
        tavan_m=pl.col("skyl1") * 0.3048,
    )
    donma = _wx_flag(FREEZING_CODES)
    kar = _wx_flag(SNOW_CODES)
    return df.with_columns(
        donma_yagisi=donma,
        kar=kar,
        sis=_wx_flag(FOG_CODES),
        gok_gurultusu=_wx_flag(THUNDER_CODES),
        # De-icing vekili: donma/kar kodu, ya da sifir civari sicaklikta rutubet.
        # PRC bu ucuslari gostergeden atiyor; biz modellemek zorundayiz (ATXOT s.13).
        deicing_vekili=(
            donma
            | kar
            | ((pl.col("sicaklik_c") <= 3.0) & (pl.col("p01i").fill_null(0.0) > 0.0))
        ),
        dusuk_gorus=pl.col("vsby") * 1.609344 < 1.5,
    ).select(
        "station", "valid", "sicaklik_c", "cig_noktasi_c", "gorus_km", "ruzgar_ms",
        "ruzgar_yon", "yagis_mm", "tavan_m", "wxcodes", "skyc1",
        "donma_yagisi", "kar", "sis", "gok_gurultusu", "deicing_vekili", "dusuk_gorus",
    )


def fetch(stations: list[str], start: date, end: date, pause: float = 1.0) -> pl.DataFrame:
    frames = []
    for chunk_start, chunk_end in _month_edges(start, end):
        print(f"  {chunk_start} .. {chunk_end}", flush=True)
        frames.append(_fetch_chunk(stations, chunk_start, chunk_end))
        time.sleep(pause)  # arsive kibar ol
    return to_si(pl.concat(frames, how="vertical_relaxed"))


def main() -> None:
    ap = argparse.ArgumentParser(description="IEM ASOS METAR indirici")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (dahil)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (haric)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stations", nargs="*", default=AIRPORTS)
    args = ap.parse_args()

    df = fetch(args.stations, date.fromisoformat(args.start), date.fromisoformat(args.end))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    print(f"{df.height:,} gozlem -> {out}")


if __name__ == "__main__":
    main()
