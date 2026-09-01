"""Fetches METAR observations from the Iowa State IEM ASOS archive.

Source and licence are documented in `docs/external_data.md`, which the prize rules
require. The archive returns imperial units; they are converted to SI here, and the
flags that matter for taxi-out are derived alongside.

Why it matters: EUROCONTROL's own indicator **discards** flights that de-ice after
off-block (ATXOT p.13). Our target is the raw taxi-out, so we cannot discard those
rows and have to model the de-icing conditions instead.

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

# METAR present-weather codes (WMO). Freezing and snow are direct evidence that
# de-icing was needed.
FREEZING_CODES = ("FZRA", "FZDZ", "FZFG")
SNOW_CODES = ("SN", "SG", "PL", "IC", "GS", "GR")
FOG_CODES = ("FG", "BR")
THUNDER_CODES = ("TS",)


def _month_edges(start: date, end: date) -> list[tuple[date, date]]:
    """Split the request into monthly chunks; kinder to the archive than one huge one."""
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
        # report_type is deliberately omitted: filtering drops Europe's
        # half-hourly METAR issue to hourly and discards the SPECI reports.
        # SPECI is issued exactly when conditions change suddenly, which makes
        # those the most valuable observations for taxi-out.
    ]
    return BASE_URL + "?" + urllib.parse.urlencode(params)


def _fetch_chunk(stations: list[str], start: date, end: date, retries: int = 3) -> pl.DataFrame:
    url = _build_url(stations, start, end)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")
            # The first lines are '#DEBUG:' comments; skip to the real header.
            body = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("#"))
            return pl.read_csv(io.StringIO(body), infer_schema_length=10_000, try_parse_dates=False)
        except Exception as exc:  # noqa: BLE001 - agdan gelen her hatada yeniden dene
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"METAR download failed for {start}..{end}: {last_error}")


def _wx_flag(codes: tuple[str, ...]) -> pl.Expr:
    """Whether any of the given codes appears in the wxcodes field."""
    expr = pl.lit(False)
    for code in codes:
        expr = expr | pl.col("wxcodes").fill_null("").str.contains(code, literal=True)
    return expr


def to_si(df: pl.DataFrame) -> pl.DataFrame:
    """Imperial to SI conversion, plus the derived flags that matter for taxi-out."""
    numeric = ["tmpf", "dwpf", "vsby", "sknt", "drct", "p01i", "skyl1"]
    df = df.with_columns(
        [pl.col(c).cast(pl.Float64, strict=False) for c in numeric if c in df.columns]
    )
    df = df.with_columns(
        valid=pl.col("valid").str.to_datetime("%Y-%m-%d %H:%M", strict=False),
        temperature_c=(pl.col("tmpf") - 32.0) * 5.0 / 9.0,
        dewpoint_c=(pl.col("dwpf") - 32.0) * 5.0 / 9.0,
        visibility_km=pl.col("vsby") * 1.609344,
        wind_ms=pl.col("sknt") * 0.514444,
        wind_dir_deg=pl.col("drct"),
        precip_mm=pl.col("p01i") * 25.4,
        ceiling_m=pl.col("skyl1") * 0.3048,
    )
    donma = _wx_flag(FREEZING_CODES)
    snow = _wx_flag(SNOW_CODES)
    return df.with_columns(
        freezing_precip=donma,
        snow=snow,
        fog=_wx_flag(FOG_CODES),
        thunderstorm=_wx_flag(THUNDER_CODES),
        # De-icing proxy: a freezing or snow code, or precipitation near zero degrees.
        # EUROCONTROL drops these flights from its indicator; we have to model them.
        deicing_proxy=(
            donma
            | snow
            | ((pl.col("temperature_c") <= 3.0) & (pl.col("p01i").fill_null(0.0) > 0.0))
        ),
        low_visibility=pl.col("vsby") * 1.609344 < 1.5,
    ).select(
        "station", "valid", "temperature_c", "dewpoint_c", "visibility_km", "wind_ms",
        "wind_dir_deg", "precip_mm", "ceiling_m", "wxcodes", "skyc1",
        "freezing_precip", "snow", "fog", "thunderstorm", "deicing_proxy", "low_visibility",
    )


def fetch(stations: list[str], start: date, end: date, pause: float = 1.0) -> pl.DataFrame:
    frames = []
    for chunk_start, chunk_end in _month_edges(start, end):
        print(f"  {chunk_start} .. {chunk_end}", flush=True)
        frames.append(_fetch_chunk(stations, chunk_start, chunk_end))
        time.sleep(pause)  # be polite to the archive
    return to_si(pl.concat(frames, how="vertical_relaxed"))


def main() -> None:
    ap = argparse.ArgumentParser(description="IEM ASOS METAR downloader")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (exclusive)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stations", nargs="*", default=AIRPORTS)
    args = ap.parse_args()

    df = fetch(args.stations, date.fromisoformat(args.start), date.fromisoformat(args.end))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    print(f"{df.height:,} observations -> {out}")


if __name__ == "__main__":
    main()
