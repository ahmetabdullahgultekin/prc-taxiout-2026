"""Canli lider tablosunu ceker.

Yarisma sayfasinda tablo gorunmuyor; siralama bir REST API'de duruyor ve sayfa onu
Observable uzerinden gomuyor. Adres `ranking.html` icinden cikarildi.

Her gonderim ayri bir kayit olarak listeleniyor, yani ayni takim birden cok kez
gorunebilir. Takim sıralaması **en iyi** skora gore (yarisma kurali F04).

    python scripts/leaderboard.py
    python scripts/leaderboard.py --team vibrant-lollipop
"""

from __future__ import annotations

import argparse
import json
import urllib.request

COMPETITION_ID = "bb3693e1-26bc-4a9e-8619-4fe78b4eab0c"
URL = f"https://datacomp.opensky-network.org/api/competitions/{COMPETITION_ID}/leaderboard"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


def fetch() -> list[dict]:
    """Tum gonderimleri ceker; sayfalama `nextCursor` ile ilerliyor."""
    items: list[dict] = []
    cursor: str | None = None
    while True:
        url = URL + (f"?cursor={cursor}" if cursor else "")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            page = json.loads(r.read())
        items.extend(page.get("items", []))
        cursor = page.get("nextCursor")
        if not cursor:
            return items


def best_per_team(items: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for it in items:
        name = it["teamName"]
        if name not in best or it["score"] < best[name]["score"]:
            best[name] = it
    return sorted(best.values(), key=lambda x: x["score"])


def main() -> None:
    ap = argparse.ArgumentParser(description="PRC 2026 lider tablosu")
    ap.add_argument("--team", default=None, help="bu takimi isaretle")
    ap.add_argument("--all", action="store_true", help="her gonderimi ayri listele")
    args = ap.parse_args()

    items = fetch()
    print(f"{len(items)} gonderim, {len({i['teamName'] for i in items})} takim gonderim yapmis\n")

    rows = sorted(items, key=lambda x: x["score"]) if args.all else best_per_team(items)
    print(f"{'#':>3}  {'takim':<26} {'skor':>10}  {'dosya':<34} islendi")
    for i, r in enumerate(rows, 1):
        mark = " <<<" if args.team and r["teamName"] == args.team else ""
        print(f"{i:>3}. {r['teamName']:<26} {r['score']:>10.4f}  {r['filename']:<34} "
              f"{r['processedAt'][:19]}{mark}")

    if args.team:
        ours = [r for r in rows if r["teamName"] == args.team]
        if ours and rows:
            fark = ours[0]["score"] - rows[0]["score"]
            print(f"\n{args.team}: {len([i for i in items if i['teamName'] == args.team])} gonderim, "
                  f"en iyi {ours[0]['score']:.4f}, lidere fark {fark:+.4f}")


if __name__ == "__main__":
    main()
